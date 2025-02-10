import logging
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Iterable

from homeassistant.components.logbook import async_log_entry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry
from homeassistant.helpers.issue_registry import IssueSeverity

from .client.modbus_client import ModbusClient
from .client.modbus_client import ModbusClientFailedError
from .common.types import RegisterPollType
from .const import DOMAIN
from .const import ENTITY_ID_PREFIX
from .const import FRIENDLY_NAME
from .inverter_profiles import InverterModelConnectionTypeProfile
from .vendor.pymodbus import ConnectionException

_LOGGER = logging.getLogger(__name__)

# How many failed polls before we mark sensors as Unavailable
_NUM_FAILED_POLLS_FOR_DISCONNECTION = 5


class ConnectionState(Enum):
    INITIAL = 0
    DISCONNECTED = 1
    CONNECTED = 2


class ModbusRegisterInterface:
    def __init__(
        self,
        hass: HomeAssistant,
        client: ModbusClient,
        connection_type_profile: InverterModelConnectionTypeProfile,
        inverter_details: dict[str, Any],
        slave: int,
        max_read: int,
    ) -> None:
        self._hass = hass
        self._client = client
        self._connection_type_profile = connection_type_profile
        self._inverter_details = inverter_details
        self._slave = slave
        self._max_read = max_read
        # To start, we're neither connected nor disconnected
        self._connection_state = ConnectionState.INITIAL
        self._num_failed_poll_attempts = 0
        self._current_connection_error: str | None = None

    @property
    def is_connected(self) -> bool:
        # Only tell things we're not connected if we're actually disconnected
        return self._connection_state == ConnectionState.INITIAL or self._connection_state == ConnectionState.CONNECTED

    @property
    def current_connection_error(self) -> str | None:
        return self._current_connection_error

    async def refresh(self, _time: datetime) -> None:
        """Refresh modbus data"""

        # List of (start address, [read values starting at that address])
        read_values: list[tuple[int, list[int]]] = []
        exception: Exception | None = None
        try:
            read_ranges = self._create_read_ranges(
                self._max_read, is_initial_connection=self._connection_state != ConnectionState.CONNECTED
            )
            for start_address, num_reads in read_ranges:
                _LOGGER.debug(
                    "Reading addresses on %s %s: (%s, %s)",
                    self._client,
                    self._slave,
                    start_address,
                    num_reads,
                )
                reads = await self._client.read_registers(
                    start_address,
                    num_reads,
                    self._connection_type_profile.register_type,
                    self._slave,
                )
                read_values.append((start_address, reads))

            # If we made it to here, then all reads succeeded. Write them to _data and notify the sensors.
            # This avoids recording reads if poll failed partway through (ensuring that we don't record potentially
            # inconsistent data)
            changed_addresses = set()
            for start_address, reads in read_values:
                for i, value in enumerate(reads):
                    address = start_address + i
                    # We might be reading a register we don't care about (for efficiency). Discard it if so
                    register_value = self._data.get(address)
                    if register_value is not None:
                        register_value.read_value = value
                        changed_addresses.add(address)

            _LOGGER.debug(
                "Refresh of %s %s complete - notifying sensors: %s",
                self._client,
                self._slave,
                changed_addresses,
            )
            self._notify_update(changed_addresses)
        except ConnectionException as ex:
            exception = ex
            _LOGGER.debug(
                "Failed to connect to %s %s: %s",
                self._client,
                self._slave,
                ex,
            )
        except ModbusClientFailedError as ex:
            exception = ex
            _LOGGER.debug(
                "Modbus error when polling %s %s: %s",
                self._client,
                self._slave,
                ex.response,
            )
        except Exception as ex:
            exception = ex
            _LOGGER.warning(
                "General exception when polling %s %s: %s",
                self._client,
                self._slave,
                repr(ex),
                exc_info=True,
            )

        # Do this after recording new values in _data. That way the sensors show the new values when they
        # become available after a disconnection
        if exception is None:
            self._num_failed_poll_attempts = 0
            if self._connection_state == ConnectionState.INITIAL:
                self._connection_state = ConnectionState.CONNECTED
            elif self._connection_state == ConnectionState.DISCONNECTED:
                _LOGGER.info(
                    "%s %s - poll succeeded: now connected",
                    self._client,
                    self._slave,
                )
                self._connection_state = ConnectionState.CONNECTED
                self._current_connection_error = None
                self._log_message("Connection restored")
                issue_registry.async_delete_issue(
                    self._hass,
                    domain=DOMAIN,
                    issue_id=f"connection_error_{self._inverter_details[ENTITY_ID_PREFIX]}",
                )
                await self._notify_is_connected_changed(is_connected=True)
        elif self._connection_state != ConnectionState.DISCONNECTED:
            self._num_failed_poll_attempts += 1
            if self._num_failed_poll_attempts >= _NUM_FAILED_POLLS_FOR_DISCONNECTION:
                _LOGGER.warning(
                    "%s %s - %s failed poll attempts: now not connected. Last error: %s",
                    self._client,
                    self._slave,
                    self._num_failed_poll_attempts,
                    exception,
                )
                self._connection_state = ConnectionState.DISCONNECTED
                self._current_connection_error = str(exception)
                self._log_message(f"Connection error: {exception}")
                issue_registry.async_create_issue(
                    self._hass,
                    domain=DOMAIN,
                    issue_id=f"connection_error_{self._inverter_details[ENTITY_ID_PREFIX]}",
                    is_fixable=False,
                    is_persistent=False,
                    severity=IssueSeverity.ERROR,
                    translation_key="connection_error",
                    translation_placeholders={
                        "friendly_name": self._inverter_details[FRIENDLY_NAME],
                        "error": str(exception),
                    },
                )
                await self._notify_is_connected_changed(is_connected=False)

    def _log_message(self, message: str) -> None:
        friendly_name = self._inverter_details[FRIENDLY_NAME]
        if friendly_name:
            name = f"FoxESS - Modbus ({friendly_name})"
        else:
            name = "FoxESS - Modbus"
        async_log_entry(self._hass, name=name, message=message, domain=DOMAIN)

    def _create_read_ranges(self, max_read: int, is_initial_connection: bool) -> Iterable[tuple[int, int]]:
        """
        Generates a set of read ranges to cover the addresses of all registers on this inverter,
        respecting the maxumum number of registers to read at a time

        :returns: Sequence of tuples of (start_address, num_registers_to_read)
        """

        # The idea here is that read operations are expensive (there seems to be a large round-trip time at least
        # with the W610), but reading additional unneeded registers is relatively cheap (probably < 1ms).

        # To give some intuition, here are some examples of the groupings we want to achieve, assuming max_read = 5
        # 1,2 / 4,5 -> 1,2,3,4,5 (i.e. to read the registers 1, 2, 4 and 5, we'll do a single read spanning 1-5)
        # 1,2 / 5,6,7,8 -> 1,2 / 5,6,7,8
        # 1,2 / 5,6,7,8,9 -> 1,2 / 5,6,7,8,9
        # 1,2 / 5,6,7,8,9,10 -> 1,2,3,4,5 / 6,7,8,9,10
        # 1,2,3 / 5,6,7 / 9,10 -> 1,2,3,4,5 / 6,7,8,9,10

        # The problem as a whole looks like it's NP-hard (although I can't find a name for it).
        # We're therefore going to use a fairly simple algorithm which just makes each read as large as it can be.

        start_address: int | None = None
        read_size = 0
        # TODO: Do we want to cache the result of this?
        for address, register_value in sorted(self._data.items()):
            if register_value.poll_type == RegisterPollType.ON_CONNECTION and not is_initial_connection:
                continue

            # This register must be read in a single individual read. Yield any ranges we've found so far,
            # and yield just this register on its own
            if self._connection_type_profile.is_individual_read(address):
                if start_address is not None:
                    yield (start_address, read_size)
                    start_address, read_size = None, 0
                yield (address, 1)
            elif start_address is None:
                start_address, read_size = address, 1
            # If we're just increasing the previous read size by 1, then don't test whether we're extending
            # the read over an invalid range (as we assume that registers we're reading to read won't be
            # inside invalid ranges, tested in __init__). This also assumes that read_size != max_read here.
            elif address == start_address + 1 or (
                address <= start_address + max_read - 1
                and not self._connection_type_profile.overlaps_invalid_range(start_address, address - 1)
            ):
                # There's a previous read which we can extend
                read_size = address - start_address + 1
            else:
                # There's a previous read, and we can't extend it to cover this address
                yield (start_address, read_size)
                start_address, read_size = address, 1

            if read_size == max_read:
                # (can't get here if start_address is None, as read_size would be 0
                yield (start_address, read_size)  # type: ignore
                start_address, read_size = None, 0

        if start_address is not None:
            yield (start_address, read_size)
