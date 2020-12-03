"""Support for Home Easy thermostats."""
from typing import List

from homeeasy.DeviceState import Mode, FanMode, HorizontalFlowMode, VerticalFlowMode
from homeeasy.HomeEasyLib import HomeEasyLib, DeviceState

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from .const import DOMAIN

SUPPORT_FAN = ["Auto", "Lowest", "Low", "Mid-low", "Mid-high", "High", "Highest", "Quite", "Turbo"]

SUPPORT_HVAC = [
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT
]

HA_STATE_TO_MODE_MAP = {
    HVAC_MODE_AUTO: Mode.Auto,
    HVAC_MODE_COOL: Mode.Cool,
    HVAC_MODE_DRY: Mode.Dry,
    HVAC_MODE_FAN_ONLY: Mode.Fan,
    HVAC_MODE_HEAT: Mode.Heat
}

MODE_TO_HA_STATE_MAP = {value: key for key, value in HA_STATE_TO_MODE_MAP.items()}

SWING_MODES = {
    "Stop": (HorizontalFlowMode.Stop, VerticalFlowMode.Stop),
    "Horizontal": (HorizontalFlowMode.Swing, VerticalFlowMode.Stop),
    "Vertical": (HorizontalFlowMode.Stop, VerticalFlowMode.Swing),
    "Both": (HorizontalFlowMode.Swing, VerticalFlowMode.Swing),
    "Custom": (HorizontalFlowMode.Stop, VerticalFlowMode.Stop)}


async def async_setup_entry(hass, config, async_add_entities):
    """Initialize a Spider thermostat."""
    mac: str = hass.data[DOMAIN][config.entry_id]
    pull: bool = config.options.get("should_pull")

    entities = [HomeEasyThermostat(mac, pull)]

    async_add_entities(entities)


class HomeEasyThermostat(ClimateEntity):
    """Representation of a thermostat."""

    _mac: str
    _lib: HomeEasyLib
    _state: DeviceState

    def __init__(self, mac: str, pool: bool):
        """Initialize the thermostat."""
        self._pool = pool
        self._mac = mac
        self._lib = HomeEasyLib()
        self._lib.connect()
        self._lib.request_status(mac, self.status_update)
        data = bytes([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        self._state = DeviceState(data)

    def status_update(self, _mac: str, state: DeviceState) -> None:
        self._state = state
        super().schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return self._pool

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE

    @property
    def unique_id(self) -> str:
        """Return the id of the thermostat, if any."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the name of the thermostat, if any."""
        return f"Home Easy HVAC({self._mac})"

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS if not self._state.temperatureScale else TEMP_FAHRENHEIT

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._state.indoorTemperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._state.desiredTemperature

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._state.desiredTemperature = temperature
        self._lib.send(self._mac, self._state)

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 1

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 16

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 31

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        if not self._state.power:
            return HVAC_MODE_OFF

        mode = self._state.mode
        return MODE_TO_HA_STATE_MAP[mode]

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self._state.power = False
        else:
            self._state.power = True
            self._state.mode = HA_STATE_TO_MODE_MAP[hvac_mode]
        self._lib.send(self._mac, self._state)

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return SUPPORT_HVAC

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        mode = int(self._state.fanMode)
        return SUPPORT_FAN[mode]

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        index = SUPPORT_FAN.index(fan_mode)
        self._state.fanMode = FanMode(index)
        self._lib.send(self._mac, self._state)

    @property
    def fan_modes(self) -> List[str]:
        """List of available fan modes."""
        return SUPPORT_FAN

    @property
    def swing_mode(self) -> str:
        """Return the swing setting."""
        for (key, value) in SWING_MODES.items():
            h, v = value
            if h == self._state.flowHorizontalMode and v == self._state.flowVerticalMode:
                return key
        return list(SWING_MODES.keys())[-1]

    @property
    def swing_modes(self) -> List[str]:
        """Return the list of available swing modes."""
        return list(SWING_MODES.keys())

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        h, v = SWING_MODES[swing_mode]
        self._state.flowHorizontalMode = h
        self._state.flowVerticalMode = v
        self._lib.send(self._mac, self._state)

    async def async_update(self) -> None:
        await self._lib.request_status_async(self._mac)


