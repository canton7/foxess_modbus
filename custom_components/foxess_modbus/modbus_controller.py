"""Modbus controller"""

import logging
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Iterator

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .client.modbus_client import ModbusClient
from .common.entity_controller import EntityController
from .common.entity_controller import EntityRemoteControlManager
from .common.entity_controller import ModbusControllerEntity
from .common.exceptions import AutoconnectFailedError
from .common.exceptions import UnsupportedInverterError
from .common.types import RegisterPollType
from .common.types import RegisterType
from .common.unload_controller import UnloadController
from .const import INVERTER_MODEL
from .const import MAX_READ
from .inverter_profiles import INVERTER_PROFILES
from .inverter_profiles import InverterModelConnectionTypeProfile
from .modbus_register_interface import ModbusRegisterInterface
from .remote_control_manager import RemoteControlManager

_LOGGER = logging.getLogger(__name__)

_MODEL_START_ADDRESS = 30000
_MODEL_LENGTH = 15

_INT16_MIN = -32768
_UINT16_MAX = 65535

_INVERTER_WRITE_DELAY_SECS = 5


@dataclass
class RegisterValue:
    poll_type: RegisterPollType
    read_value: int | None = None
    written_value: int | None = None
    written_at: float | None = None  # From time.monotonic()


@contextmanager
def _acquire_nonblocking(lock: threading.Lock) -> Iterator[bool]:
    locked = lock.acquire(False)
    try:
        yield locked
    finally:
        if locked:
            lock.release()


class ModbusController(EntityController, UnloadController):
    """Class to manage forecast retrieval"""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ModbusClient,
        connection_type_profile: InverterModelConnectionTypeProfile,
        inverter_details: dict[str, Any],
        slave: int,
        poll_rate: int,
        max_read: int,
    ) -> None:
        """Init"""
        self._hass = hass
        self._update_listeners: set[ModbusControllerEntity] = set()
        self._data: dict[int, RegisterValue] = {}
        self._client = client
        self._connection_type_profile = connection_type_profile
        self._inverter_details = inverter_details
        self._slave = slave
        self._poll_rate = poll_rate
        self._refresh_lock = threading.Lock()

        self._inverter_capacity = connection_type_profile.inverter_model_profile.inverter_capacity(
            self.inverter_details[INVERTER_MODEL]
        )

        self._register_interface = ModbusRegisterInterface(
            hass, client, connection_type_profile, inverter_details, max_read
        )

        # Setup mixins
        EntityController.__init__(self)
        UnloadController.__init__(self)

        self.charge_periods = connection_type_profile.create_charge_periods(self)
        # This will call back into us to register its addresses
        remote_control_config = connection_type_profile.create_remote_control_config(self)
        self._remote_control_manager = (
            RemoteControlManager(self, remote_control_config, poll_rate) if remote_control_config is not None else None
        )

        if self._hass is not None:
            refresh = async_track_time_interval(
                self._hass,
                self._refresh,
                timedelta(seconds=self._poll_rate),
            )

            self._unload_listeners.append(refresh)

    @property
    def hass(self) -> HomeAssistant:
        return self._hass

    @property
    def is_connected(self) -> bool:
        return self._register_interface.is_connected

    @property
    def current_connection_error(self) -> str | None:
        return self._register_interface.current_connection_error

    @property
    def remote_control_manager(self) -> EntityRemoteControlManager | None:
        return self._remote_control_manager

    @property
    def inverter_capacity(self) -> int:
        return self._inverter_capacity

    @property
    def inverter_details(self) -> dict[str, Any]:
        return self._inverter_details

    def read(self, address: int | list[int], *, signed: bool) -> int | None:
        # There can be a delay between writing a register, and actually reading that value back (presumably the delay
        # is on the inverter somewhere). If we've recently written a value, use that value, rather than the latest-read
        # value
        now = time.monotonic()

        def _read_value(address: int) -> int | None:
            register_value = self._data.get(address)
            if register_value is None:
                return None

            value: int | None
            if (
                register_value.written_value is not None
                and register_value.written_at is not None
                and now - register_value.written_at < _INVERTER_WRITE_DELAY_SECS
            ):
                value = register_value.written_value
            else:
                value = register_value.read_value

            return value

        if isinstance(address, int):
            address = [address]

        value = 0
        for i, a in enumerate(address):
            val = _read_value(a)
            if val is None:
                return None
            value |= (val & 0xFFFF) << (i * 16)

        if signed:
            sign_bit = 1 << (len(address) * 16 - 1)
            value = (value & (sign_bit - 1)) - (value & sign_bit)

        return value

    async def read_registers(self, start_address: int, num_registers: int, register_type: RegisterType) -> list[int]:
        """Read one of more registers, used by the read_registers_service"""
        return await self._client.read_registers(start_address, num_registers, register_type, self._slave)

    async def write_register(self, address: int, value: int) -> None:
        await self.write_registers(address, [value])

    async def write_registers(self, start_address: int, values: list[int]) -> None:
        """Write multiple registers"""
        _LOGGER.debug(
            "Writing registers for %s %s: (%s, %s)",
            self._client,
            self._slave,
            start_address,
            values,
        )
        try:
            for i, value in enumerate(values):
                value = int(value)  # Ensure that we've been given an int
                if not (_INT16_MIN <= value <= _UINT16_MAX):
                    raise ValueError(f"Value {value} must be between {_INT16_MIN} and {_UINT16_MAX}")
                # pymodbus doesn't like negative values
                if value < 0:
                    value = _UINT16_MAX + value + 1
                values[i] = value

            await self._client.write_registers(start_address, values, self._slave)

            changed_addresses = set()
            for i, value in enumerate(values):
                address = start_address + i
                # Only store the result of the write if it's a register we care about ourselves
                register_value = self._data.get(address)
                if register_value is not None:
                    register_value.written_value = value
                    register_value.written_at = time.monotonic()
                    changed_addresses.add(address)
            if len(changed_addresses) > 0:
                self._notify_update(changed_addresses)
        except Exception as ex:
            # Failed writes are always bad
            _LOGGER.exception("Failed to write registers")
            raise ex

    async def _refresh(self, _time: datetime) -> None:
        """Refresh modbus data"""
        # Make sure that we don't do two refreshes at the same time, if one is too slow
        with _acquire_nonblocking(self._refresh_lock) as acquired:
            if not acquired:
                _LOGGER.warning(
                    "Aborting refresh of %s %s as a previous refresh is still in progress. Is your poll rate '%s' too "
                    "high?",
                    self._client,
                    self._slave,
                    self._poll_rate,
                )
                return

            await self._register_interface.refresh()

        # TODO

        if self._remote_control_manager is not None:
            await self._remote_control_manager.poll_complete_callback()

    def register_modbus_entity(self, listener: ModbusControllerEntity) -> None:
        self._update_listeners.add(listener)
        for address in listener.addresses:
            assert not self._connection_type_profile.overlaps_invalid_range(address, address), (
                f"Entity {listener} address {address} overlaps an invalid range in "
                f"{self._connection_type_profile.special_registers.invalid_register_ranges}"
            )
            if address not in self._data:
                self._data[address] = RegisterValue(poll_type=listener.register_poll_type)
            else:
                # We could handle this (removing gets harder), but it shouldn't happen in practice anyway
                assert self._data[address].poll_type == listener.register_poll_type

    def remove_modbus_entity(self, listener: ModbusControllerEntity) -> None:
        self._update_listeners.discard(listener)
        # If this was the only entity listening on this address, remove it from self._data
        other_addresses = {address for entity in self._update_listeners for address in entity.addresses}
        for address in listener.addresses:
            if address not in other_addresses and address in self._data:
                del self._data[address]

    def _notify_update(self, changed_addresses: set[int]) -> None:
        """Notify listeners"""
        for listener in self._update_listeners:
            listener.update_callback(changed_addresses)

    async def _notify_is_connected_changed(self, is_connected: bool) -> None:
        """Notify listeners that the availability states of the inverter changed"""
        for listener in self._update_listeners:
            listener.is_connected_changed_callback()

        if is_connected and self._remote_control_manager is not None:
            await self._remote_control_manager.became_connected_callback()

    @staticmethod
    async def autodetect(client: ModbusClient, slave: int, adapter_config: dict[str, Any]) -> tuple[str, str]:
        """
        Attempts to auto-detect the inverter type at the other end of the given connection

        :returns: Tuple of (inverter type name e.g. "H1", inverter full name e.g. "H1-3.7-E")
        """
        # Annoyingly pymodbus logs the important stuff to its logger, and doesn't add that info to the exceptions it
        # throws
        spy_handler = _SpyHandler()
        pymodbus_logger = logging.getLogger("pymodbus")

        try:
            pymodbus_logger.addHandler(spy_handler)

            # All known inverter types expose the model number at holding register 30000 onwards.
            # (The H1 series additionally expose some model info in input registers))
            # Holding registers 30000-300015 seem to be all used for the model, with registers
            # after the model containing 32 (an ascii space) or 0. Input registers 10008 onwards
            # are for the serial number (and there doesn't seem to be enough space to hold all models!)
            # The H3 starts the model number with a space, annoyingly.
            # Some models (H1-5.0-E-G2 and H3-PRO) pack two ASCII chars into each register.
            register_values: list[int] = []
            start_address = _MODEL_START_ADDRESS
            while len(register_values) < _MODEL_LENGTH:
                register_values.extend(
                    await client.read_registers(
                        start_address,
                        min(adapter_config[MAX_READ], _MODEL_LENGTH - len(register_values)),
                        RegisterType.HOLDING,
                        slave,
                    )
                )
                start_address += adapter_config[MAX_READ]

            # If they've packed 2 ASCII chars into each register, unpack them
            if (register_values[0] & 0xFF00) != 0:
                model_chars = []
                # High byte, then low byte
                for register in register_values:
                    model_chars.append((register >> 8) & 0xFF)
                    model_chars.append(register & 0xFF)
            else:
                model_chars = register_values

            # Stop as soon as we find something non-printable-ASCII
            full_model = ""
            for char in model_chars:
                if 0x20 <= char < 0x7F:
                    full_model += chr(char)
                else:
                    break
            # Take off tailing spaces and H3's leading space
            full_model = full_model.strip()
            for model in INVERTER_PROFILES.values():
                if re.match(model.model_pattern, full_model):
                    # Make sure that we can parse the capacity out
                    capacity = model.inverter_capacity(full_model)
                    _LOGGER.info("Autodetected inverter as '%s' (%s, %sW)", model.model, full_model, capacity)
                    return model.model, full_model

            # We've read the model type, but been unable to match it against a supported model
            _LOGGER.error("Did not recognise inverter model '%s' (%s)", full_model, register_values)
            raise UnsupportedInverterError(full_model)
        except Exception as ex:
            _LOGGER.exception("Autodetect: failed to connect to (%s)", client)
            raise AutoconnectFailedError(spy_handler.records) from ex
        finally:
            pymodbus_logger.removeHandler(spy_handler)
            await client.close()


class _SpyHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
