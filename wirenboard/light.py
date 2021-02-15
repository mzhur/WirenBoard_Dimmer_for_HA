"""
Home Assistant support for WirenBoard Dimmer.

Date:     2021-02-01
Homepage: 
Author:   Maxim Zhuravlev
"""
import asyncio
import logging
import socket
from struct import pack
from homeassistant.const import (CONF_DEVICES, CONF_HOST, CONF_NAME, CONF_PORT,
                                 CONF_TYPE, STATE_ON, STATE_OFF)
try:
  from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                              ATTR_HS_COLOR,
                                              ATTR_TRANSITION,
                                              ATTR_WHITE_VALUE,
                                              ATTR_COLOR_TEMP,
                                              LightEntity,
                                              PLATFORM_SCHEMA,
                                              SUPPORT_BRIGHTNESS,
                                              SUPPORT_COLOR,
                                              SUPPORT_WHITE_VALUE,
                                              SUPPORT_TRANSITION,
                                              SUPPORT_COLOR_TEMP
                                              )
except ImportError:
  from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                              ATTR_HS_COLOR,
                                              ATTR_TRANSITION,
                                              ATTR_WHITE_VALUE,
                                              ATTR_COLOR_TEMP,
                                              Light as LightEntity,
                                              PLATFORM_SCHEMA,
                                              SUPPORT_BRIGHTNESS,
                                              SUPPORT_COLOR,
                                              SUPPORT_WHITE_VALUE,
                                              SUPPORT_TRANSITION,
                                              SUPPORT_COLOR_TEMP)
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
_LOGGER = logging.getLogger(__name__)

CONF_ADDRESS = 'address'
CONF_REGISTER = 'register'
CONF_DEFAULT_TYPE = 'default_type'
CONF_MAX_VALUE = 'max_value'
CHANNEL_COUNT_MAP, FEATURE_MAP, COLOR_MAP = {}, {}, {}
CONF_LIGHT_TYPE_DIMMER = 'dimmer'
CONF_LIGHT_TYPES = [CONF_LIGHT_TYPE_DIMMER]
CHANNEL_COUNT_MAP[CONF_LIGHT_TYPE_DIMMER] = 1
FEATURE_MAP[CONF_LIGHT_TYPE_DIMMER] = (SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION)
COLOR_MAP[CONF_LIGHT_TYPE_DIMMER] = None

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Optional(CONF_DEFAULT_TYPE, default=CONF_LIGHT_TYPE_DIMMER): cv.string,
    vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [
        {
           vol.Required(CONF_NAME): cv.string,
           vol.Required(CONF_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=1,max=255)),
           vol.Required(CONF_REGISTER): cv.string,
           vol.Optional(CONF_MAX_VALUE, default=255): vol.All(vol.Coerce(int), vol.Range(min=50,max=255)),
        }
       ]),
    })

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    default_light_type = config.get(CONF_DEFAULT_TYPE)
    udp_gateway = UDPGateway(host, port)
    lights = (UDPLight(light, udp_gateway, default_light_type) for light in
              config[CONF_DEVICES])
    async_add_devices(lights)

    return True

class UDPLight(LightEntity):
    """Representation of a wiringboard dimmer"""

    def __init__(self, light, udp_gateway, default_type):
        """Initialize wirenboard Light"""
        self._udp_gateway = udp_gateway
        self._address = light.get(CONF_ADDRESS)
        self._register = [int(i) for i in light.get(CONF_REGISTER).split(':')]
        _LOGGER.debug(f"Several register {self._register}")
        self._name = light.get(CONF_NAME)
        self._max_v = light.get(CONF_MAX_VALUE)
        self._m_coef = self._max_v/255
        self._type = light.get(CONF_TYPE, default_type)
        self._fade_time = 100
        self._brightness = self._udp_gateway.get_level(self._address, self._register, self._m_coef)
        self._rgb = None
        self._white_value = 0
        self._color_temp = int((self.min_mireds + self.max_mireds) / 2)
        self._channel_setup =''
        self._channel_count =1
        self._features = FEATURE_MAP.get(self._type)
        if self._brightness > 0:
             self._state = STATE_ON
             self._last_brightness = self._brightness
        else:
             self._state = STATE_OFF
             self._last_brightness = 100
        _LOGGER.debug(f"Init Light with {self._name}, address {self._address}, register {self._register}, type {self._type} features {self._features} ")

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        _LOGGER.debug(f"change brigtness from {self._last_brightness} to {self._brightness}")
        if self._brightness > 0:
                self._last_brightness = self._brightness
        
        return self._brightness
    @property
    def device_state_attributes(self):
        data = {}
        data['address'] = self._address
        data['register'] = self._register
        return data


    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state == STATE_ON

    @property
    def hs_color(self):
        """Return the HS color value."""
        return None

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return None

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 192

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 448

    @property
    def color_temp(self):
        """Flag supported features."""
        return self._color_temp

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def should_poll(self):
        return True

    @property
    def fade_time(self):
        return self._fade_time

    def update(self):
        """Fetch update state."""
        _LOGGER.debug("Update...")
        asked_info = self._udp_gateway.get_level(self._address, self._register, self._m_coef)
        if (asked_info == 0) and (self.is_on):
             self._state = STATE_OFF
        elif (asked_info > 0) and (self.is_on == False):
             self._brightness = asked_info
             self._state = STATE_ON
        _LOGGER.debug(f"Update with {self._name}, address {self._address}, register {self._register}, type {self._type} features {self._features} brightness {self._brightness}")
        # Nothing to return



    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Instruct the light to turn on.

        Move to using one method on the UDP class to set/fade either a single
        channel or group of channels
        """

        self._state = STATE_ON
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self._brightness = self._last_brightness
        temp = round(self._brightness*self._m_coef)
        if temp > self._max_v:
              temp = self._max_v
        asyncio.ensure_future(
            self._udp_gateway.set_value_async(
                self._address, self._register, temp))
        self.async_schedule_update_ha_state()
        _LOGGER.debug(f"Set turn on {temp}")
        


    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Instruct the light to turn off.

        If a transition time has been specified in
        seconds the controller will fade.
        """
        _LOGGER.debug("Set turn off")
        self._last_brightness = self._brightness
        asyncio.ensure_future(self._udp_gateway.set_value_async(
            self._address, self._register, 0))
        self._state = STATE_OFF
        self.async_schedule_update_ha_state()
        


class UDPGateway(object):
    """
    Class to keep track of the values of DMX channels.
    """

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _LOGGER.debug("initiate sended class")
        
        
     
    def get_level(self, address, register, m_coef):
        """
        Send the current state to the gateway via UDP packet.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(10)
            try:
                sock.bind(('', 8586))
            except socket.error as err:
                _LOGGER.error("Unable to bind on port")
                return
            self._socket.sendto(bytearray([2, address, register[0]]), (self._host, self._port))
            temp_data, addr = sock.recvfrom(1)
        if (temp_data[0]/m_coef) > 255:
              r_t = 255
        else:
              r_t = int(round(temp_data[0]/m_coef))
        _LOGGER.debug(f"Ask curent level {temp_data[0]}, {r_t}")
        return r_t


    @asyncio.coroutine
    def set_value_async(self, address, register, value):
         for reg in register:
              self._socket.sendto(bytearray([1, address, reg, value]), (self._host, self._port))
              _LOGGER.debug(f"Sended new value for {address} register {register} :  {value}")
         yield from asyncio.sleep(1. / 40)

 
    @property
    def default_level(self):
        _LOGGER.debug("ask default level")
        return self._default_level


