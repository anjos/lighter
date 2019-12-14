#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Functions that handle discussion with the deconz gateway"""

import os
import re
import ssl
import json
import time
import requests
import itertools
import datetime
import threading


import logging

logger = logging.getLogger(__name__)

import dateutil.parser

from . import color


def _id_predicate(actual_id, actual_name, target_id):
    """Predicate to test actual identifiers and names against a target one"""

    return (
        (isinstance(target_id, str) and actual_name.lower() == target_id)
        or (isinstance(target_id, int) and int(actual_id) == target_id)
        or (isinstance(target_id, re.Pattern) and target_id.match(actual_name))
    )


def _handle_id(id):
    """Handles None, integer, string or regexp identifiers with minimal
    input"""

    # avoids a second conversion attempt
    if not isinstance(id, (str)):
        return id

    # it is a string
    try:
        id = int(id)
    except ValueError:
        # it is a string
        if id.startswith("/") and id.endswith("/"):
            id = re.compile(id[1:-1], flags=re.IGNORECASE)
        else:
            id = id.lower()

    return id


def _uniq(seq, idfun=None):
    """Very fast, order preserving uniq function for sequences"""

    # order preserving
    if idfun is None:

        def idfun(x):
            return x

    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        if marker in seen:
            continue
        seen[marker] = 1
        result.append(item)
    return result


def setup_server():
    """Sets up a connection to a deconz ReST API server"""

    from .config import load as config_load

    config = config_load()
    if not config:
        raise RuntimeError("No configuration file loaded - cannot proceed")

    return Server(
        host=config["host"],
        port=config["port"],
        api_key=config.get("api_key"),
        transitiontime=config.get("transitiontime", 0),
        timeout=config.get("timeout", 10),
    )


class Server:
    """A running connection to a deconz server, using the v1 API


    Parameters
    ----------

    host : str
        IP or name of host

    port : str
        Port number to use for the deconz API

    api_key : str
        A previously obtained API key (optional)

    transitiontime : int
        Transition time in 1/10 seconds between two (light) states.

    timeout : int, float
        Timeout in seconds or fractions of to wait for light change operations.
        If set to ``None``, then wait forever.

    """

    def __init__(self, host, port, api_key=None, transitiontime=0, timeout=10):
        self.host = host
        self.port = port
        self.api_key = api_key
        self.transitiontime = transitiontime
        self.timeout = timeout

        # to cache server information
        self.cache = dict()
        self._hook_socket()

    def _hook_socket(self):
        """Hooks a websocket to allow waiting for actions to take place"""

        _ws_waiting = dict(lights={}, groups={})
        _ws_lock = threading.RLock()  # allows multiple messages to be recv
        _ws_can_terminate = threading.Event()
        _ws_can_terminate.set()  # by default, we can terminate

        def _on_message(socket, message):
            """Processes a message from the socket"""
            with _ws_lock:
                message = json.loads(message)
                if message["e"] == "changed":
                    if message["r"] in _ws_waiting:
                        if message["id"] in _ws_waiting[message["r"]]:
                            logger.debug(
                                "Detected change in /%s/%s: %s",
                                message["r"],
                                message["id"],
                                message["state"],
                            )
                            del _ws_waiting[message["r"]][message["id"]]
                            waiting_on = len(_ws_waiting["lights"]) + len(
                                _ws_waiting["groups"]
                            )
                            logger.debug("Waiting on %d elements", waiting_on)
                            if waiting_on == 0:
                                logger.debug("OK to terminate")
                                _ws_can_terminate.set()

        self._ws_waiting = _ws_waiting
        self._ws_lock = _ws_lock
        self._ws_can_terminate = _ws_can_terminate

        config = self.get_config()
        assert config["config"]["websocketnotifyall"]

        import websocket

        websocket.enableTrace(True)
        server = (
            "ws://"
            + config["config"]["ipaddress"]
            + ":"
            + str(config["config"]["websocketport"])
        )
        self.ws = websocket.WebSocketApp(server, on_message=_on_message)

        self._ws_thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs=dict(
                sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
            ),
        )
        self._ws_thread.daemon = True
        self._ws_thread.start()

    def wait_for_changes(self, timeout=None):
        """Waits until all changes have been performed

        This method works as a synchronization point to ensure that state
        changes have been perceived by the devices connected to the network.
        It will unblock when changes are done (reported by the websocket).


        Parameters
        ----------

        timeout : :obj:`int`, optional
            Number of seconds to wait for, at most.  If set, overrides the
            internal default
        """
        logger.debug("Waiting for terminate OK")
        self._ws_can_terminate.wait(timeout=(timeout or self.timeout))

    def _cache_config(self):
        """Reloads the configuration information from the server, if needs be
        """

        parts = [self.api_key]

        if "config" not in self.cache:
            response = self._get(parts)
            self.cache["config"] = response.json()
            self.cache["config-etag"] = response.headers["ETag"]
        else:
            response = self._get(parts, etag=self.cache["config-etag"])
            if response.status_code == 304:  # not modified
                assert response.headers["ETag"] == self.cache["config-etag"]
            else:  # state was updated
                self.cache["config"] = response.json()
                self.cache["config-etag"] = response.headers["ETag"]

        return self.cache["config"]

    def _cache_lights(self):
        """Reloads the lights information from the server, if needs be
        """

        parts = [self.api_key, "lights"]

        if "lights" not in self.cache:
            response = self._get(parts)
            self.cache["lights"] = response.json()
            self.cache["lights-etag"] = response.headers["ETag"]
        else:
            response = self._get(parts, etag=self.cache["lights-etag"])
            if response.status_code == 304:  # not modified
                assert response.headers["ETag"] == self.cache["lights-etag"]
            else:  # state was updated
                self.cache["lights"] = response.json()
                self.cache["lights-etag"] = response.headers["ETag"]

        return self.cache["lights"]

    def _cache_groups(self):
        """Reloads the group information from the server
        """

        parts = [self.api_key, "groups"]

        if "groups" not in self.cache:
            response = self._get(parts)
            self.cache["groups"] = response.json()
            self.cache["groups-etag"] = response.headers["ETag"]
        else:
            response = self._get(parts, etag=self.cache["groups-etag"])
            if response.status_code == 304:  # not modified
                assert response.headers.get("ETag") == self.cache["groups-etag"]
            else:  # state was updated
                self.cache["groups"] = response.json()
                self.cache["groups-etag"] = response.headers["ETag"]

        return self.cache["groups"]

    def get_api_key(self):
        """Tries to fetch an API key from the deconz host

        You must click on the appropriate button from the Phoscon-gateway
        interface to allow this momentarily.

        See: http://dresden-elektronik.github.io/deconz-rest-doc/authorization/
        """

        while True:
            r = self._post([], dict(devicetype="lighter"))
            if r.status_code == 403:
                logger.error(
                    "Server %s responded with a 403 (Forbidden) error - "
                    "link button not pressed.  Please click on Authenticate "
                    "app ' at the gateway web interface" % api
                )
                logger.info("Sleeping for 1 second...")
                time.sleep(1)
            else:
                self.api_key = r.json()[0]["success"]["username"]
                return self.api_key
                break

    def _api(self, parts):
        """Returns the wrapped address of the API

        Parameters
        ----------

        parts : :obj:`list` of :obj:`str`
            A list of strings to join forming an url like
            ``parts[0]/parts[1]/...``


        Returns
        -------

        url : str
            A string representing the final API URL, built from a common prefix
            and the parts.
        """

        return "http://%s:%d/api/%s" % (self.host, self.port, "/".join(parts))

    def _post(self, parts, data):
        """POST an API request

        Parameters
        ----------

        parts : :obj:`list` of :obj:`str`
            A list of strings to join forming an url like
            ``parts[0]/parts[1]/...``

        data : dict
            A dictionary with string -> string mappings that is transmitted
            with the request.
        """
        url = self._api(parts)
        data = json.dumps(data)
        logger.debug("POST '%s' data: %s", url, data)
        response = requests.post(url, data=data)
        if not response.ok:
            logger.error("Unable to POST '%s' data: %s", url, data)
            logger.error(
                "Returned %d (%s)", response.status_code, response.reason
            )
        data = response.json()
        logger.debug("Response:\n%s", json.dumps(data, indent=2))

    def _get(self, parts, etag=None):
        """GET an API request

        Parameters
        ----------

        parts : :obj:`list` of :obj:`str`
            A list of strings to join forming an url like
            ``parts[0]/parts[1]/...``

        etag : str
            If set, transmit the ETag header to the host


        Returns
        -------

        response : requests.Response
            An object containing the server response
        """

        url = self._api(parts)
        logger.debug("GET '%s'", url)
        headers = {}
        if etag is not None:
            headers["If-None-Match"] = etag
        response = requests.get(url, headers=headers)
        if not response.ok:
            logger.error("Unable to GET '%s'", url)
            logger.error(
                "Returned %d (%s)", response.status_code, response.reason
            )
        return response

    def _put(self, parts, data):
        """PUT an API request

        Parameters
        ----------

        parts : :obj:`list` of :obj:`str`
            A list of strings to join forming an url like
            ``parts[0]/parts[1]/...``

        data : dict
            A dictionary with string -> string mappings that is transmitted
            with the request.
        """

        url = self._api(parts)
        data = json.dumps(data)
        logger.debug("PUT '%s' data: %s", url, data)
        response = requests.put(url, data=data)
        if not response.ok:
            logger.error("Unable to PUT '%s' data: %s", url, data)
            logger.error(
                "Returned %d (%s)", response.status_code, response.reason
            )
        data = response.json()
        logger.debug("Response:\n%s", json.dumps(data, indent=2))

    def _delete(self, parts):
        """DELETE an API request

        Parameters
        ----------

        parts : :obj:`list` of :obj:`str`
            A list of strings to join forming an url like
            ``parts[0]/parts[1]/...``
        """

        url = self._api(parts)
        logger.debug("DELETE '%s'", url)
        response = requests.delete(url)
        if not response.ok:
            logger.error("Unable to DELETE '%s'", url)
            logger.error(
                "Returned %d (%s)", response.status_code, response.reason
            )
        data = response.json()
        logger.debug("Response:\n%s", json.dumps(data, indent=2))

    def _translate_light_state(self, state, ct_bounds, values):
        """Translates light state from a string with rough details

        Parameters
        ----------

        state : dict
            The current light state

        ct_bounds : :obj:`list` of :obj:`int`
            A list of exactly two integers indicating the minimum and maximum
            color temperatures the light accepts.  Not all lights accept the
            same range.

        values : :obj:`list` of :obj:`str`
            A list of strings containing the "human-readable" values to set to
            the light in question.  From this list, this function will generate
            the correct settings for the type of light being affected.

            Here are possible values that can be set on this list of strings:

            * ``on`` or ``off``: light or switch is turned ON or OFF
            * ``0%`` to ``100%``: brightness
            * ``2000K`` to 6500K``: white temperature
            * ``candle|warm|warm+|soft|natural|cool|day-|day``: white
              temperature in the following ranges candle=2000K, warm=2700K,
              warm+=3000K, soft=3500K, natural=3700K, cool=4000K, day-=5000K,
              day=6500K
            * ``alert``: turns lamp alert mode ON (for a few seconds)


        Returns
        -------

        values : dict
            A dictionary of values that can be set for the type of light being
            affected.

        """

        def _bri(perc):
            """Converts to brightness scale from percentage"""
            return int(round(255 * perc / 100.0))

        def _ct(kelvin):
            """Converts to CT scale from Kelvins"""
            value = color.color_temperature_kelvin_to_mired(kelvin)

            # we respect the maximum boundaries of the light - return
            # whatever we can actually set.
            if value < ct_bounds[0]:
                logger.warning(
                    "Cannot set light color temperature to %d (minimum is %d)",
                    value,
                    ct_bounds[0],
                )
                value = ct_bounds[0]
            if value > ct_bounds[1]:
                logger.warning(
                    "Cannot set light color temperature to %d (maximum is %d)",
                    value,
                    ct_bounds[1],
                )
                value = ct_bounds[1]

            return value

        def _hs(kelvin):
            """Converts to HS from Kelvins"""
            return color.color_temperature_to_hs(kelvin)

        def _xy(kelvin):
            """Converts to XY from Kelvins"""
            h, s = _hs(kelvin)
            return color.color_hs_to_xy(h, s)

        # consumes keywords one by one, and set internal elements
        retval = {"transitiontime": self.transitiontime}

        temp = None
        for key in values:

            if key in ["off", "0", "0%"]:
                retval["on"] = False

            elif key in ["on"]:
                retval["on"] = True

            elif key.endswith("%"):  # brightness
                retval["bri"] = _bri(int(key[:-1]))

            elif key.endswith("k"):  # temperature
                temp = int(key[:-1])
            elif key in ["candle"]:
                temp = 2000  # 2600 is min for IKEA/Philips lights?
            elif key in ["warm"]:
                temp = 2700
            elif key in ["warm+"]:
                temp = 3000
            elif key in ["soft"]:
                temp = 3500
            elif key in ["natural"]:
                temp = 3700
            elif key in ["cool"]:
                temp = 4000
            elif key in ["day-"]:
                temp = 5000  # 5190 is max for IKEA lights?
            elif key in ["day"]:
                temp = 6500  # 6500 is max for Philips lights?

            elif key in ["alert"]:
                retval["alert"] = "lselect"

            else:
                raise RuntimeError(
                    'keyword "%s" is not recognized '
                    "when setting the light state" % key
                )

        if state.get("colormode") is None:
            return {"on": retval["on"]}
        else:
            # if the light is turned on, and the user wants to turn it off,
            # then only set its brightness to zero
            if state["on"]:
                if "on" in retval and not retval["on"]:
                    retval["bri"] = 0
                    del retval["on"]
            retval["transitiontime"] = self.transitiontime

        if temp is not None:  # user wants to set light temperature
            if state["colormode"] == "hs":
                h, s = _hs(temp)
                retval["hue"] = h
                retval["sat"] = s
            elif state["colormode"] == "xy":
                x, y = _xy(temp)
                retval["xy"] = [x, y]
            else:  # mired color temperature
                retval["ct"] = _ct(temp)

        return retval

    def get_config(self):
        """Grabs the current server configuration

        Returns
        -------

        config : dict
            A dictionary containing the complete server configuration
        """

        return self._cache_config()

    def remove_old_apikeys(self, days_unused=30):
        """Removes all API keys that have not been used by a number of days

        Parameters
        ----------

        days_unused : :obj:`int`, optional
            Number of days to consider last usage before removing the key
        """

        config = self._cache_config()
        whitelist = config["config"]["whitelist"]
        now = datetime.datetime.now()
        for key, info in whitelist.items():
            last_used = dateutil.parser.parse(info["last use date"])
            delta = now - last_used
            if delta.days > days_unused:
                logger.info(
                    "Erasing API key '%s' that was last used %s (%d days ago)",
                    key,
                    last_used,
                    delta.days,
                )
                self._delete([self.api_key, "config", "whitelist", key])

    def get_lights(self, id):
        """Returns all lights configured, or a specific one


        Parameters
        ----------

        id : int, str
            The light/switch identifier (:obj:`int`), its name (:obj:`str`) or
            a regular expression (:obj:`str`, prefixed and suffixed by ``/``)
            to match names of lights/switches on the server


        Returns
        -------

        lights : dict
            A dictionary in which keys are string-integer identifiers for the
            lights selected and values correspond to light information and
            state.
        """

        data = self._cache_lights()
        id = _handle_id(id)  # converts to str, int or re.Pattern

        if id is None:
            return data

        # otherwise, apply filtering
        candidates = dict(
            [(k, v) for k, v in data.items() if _id_predicate(k, v["name"], id)]
        )
        logger.debug(
            "Returning %d out of %d total lights/switches",
            len(candidates),
            len(data),
        )
        return candidates

    def set_light_name(self, id, name):
        """Set the light/switch name

        Parameters
        ----------

        id : int, str
            The light/switch identifier (:obj:`int`), its name (:obj:`str`) or
            a regular expression (:obj:`str`, prefixed and suffixed by ``/``)
            to match names of lights/switches on the server

        name : :obj:`str`, optional
            The new name to set for the light

        """

        affected = self.get_lights(id)  # all lights matching id
        if not len(affected):
            logger.warning("No lights affected by name change")
            return

        for k, v in affected.items():
            parts = [self.api_key, "lights", str(k)]
            self._put(parts, data={"name": name})

    def _set_single_light(self, id, data):
        """Internal method to set a single light to a given state

        Parameters
        ----------

        id : str
            Integer identifier for the light to be set

        data : dict
            A dictionary mapping key to values as accepted by the deCONZ
            interface

        """
        parts = [self.api_key, "lights", str(id), "state"]
        with self._ws_lock:
            self._ws_waiting["lights"][id] = data
            self._ws_can_terminate.clear()
        self._put(parts, data=data)

    def _get_light_state_dict(self, d, values):
        """Internal method, returns to-be-set light state from dictionary


        Parameters
        ----------

        d : dict
            A dictionary, e.g. as returned by :py:meth:`get_lights`.

        values : :obj:`list` of :obj:`str`
            A list of strings that can be absorbed by
            :py:meth:`_translate_light_state`, that will be analyzed in
            sequence and applied to each light matched.


        Returns
        -------

        states : dict
            A dictionary containing the final settable state of each light
            defined in ``d``
        """

        state = dict()
        for k, v in d.items():
            state[k] = self._translate_light_state(
                v["state"], (v.get("ctmin", 250), v.get("ctmax", 454)), values
            )
        return state

    def _set_light_state_dict(self, d, values):
        """Internal method, set light state from dictionary

        This method will apply the stage change defined by ``values`` to all
        lights in the dictionary ``d``.  It is similar to
        :py:meth:`set_light_state`, but acts on precalculated lights only, as
        provided by ``d``.


        Parameters
        ----------

        d : dict
            A dictionary, e.g. as returned by :py:meth:`get_lights`.

        values : :obj:`list` of :obj:`str`
            A list of strings that can be absorbed by
            :py:meth:`_translate_light_state`, that will be analyzed in
            sequence and applied to each light matched.
        """

        for k, v in self._get_light_state_dict(d, values).items():
            self._set_single_light(k, v)

    def set_light_state(self, id, values):
        """Set light state

        This method will apply the stage change defined by ``values`` to all
        lights matching ``id``


        Parameters
        ----------

        id : int, str
            The light/switch identifier (:obj:`int`), its name (:obj:`str`) or
            a regular expression (:obj:`str`, prefixed and suffixed by ``/``)
            to match names of lights/switches on the server

        values : :obj:`list` of :obj:`str`
            A list of strings that can be absorbed by
            :py:meth:`_translate_light_state`, that will be analyzed in
            sequence and applied to each light matched.
        """

        affected = self.get_lights(id)

        if not len(affected):
            logger.warning("No lights affected by state change")
            return

        self._set_light_state_dict(affected, values)

    def get_groups(self, id=None):
        """Returns all groups configured, or a specific one


        Parameters
        ----------

        id : int, str
            The group identifier (:obj:`int`), its name (:obj:`str`) or
            a regular expression (:obj:`str`, prefixed and suffixed by ``/``)
            to match names of groups on the server


        Returns
        -------

        groups : dict
            A dictionary in which keys are string-integer identifiers for the
            groups selected and values correspond to group information and
            state.
        """

        data = self._cache_groups()
        id = _handle_id(id)  # converts to str, int or re.Pattern

        if id is None:
            return data

        # otherwise, apply filtering
        candidates = dict(
            [(k, v) for k, v in data.items() if _id_predicate(k, v["name"], id)]
        )
        logger.debug(
            "Returning %d out of %d total groups", len(candidates), len(data)
        )
        return candidates

    def _resolve_light_ids(self, ids):
        """Resolve identifiers for lights in the server

        This method receives a list of light identifiers (integers, names or
        regular expressions) and returns a set of identifiers by **additively**
        building this list.


        Parameters
        ----------

        ids : :obj:`list` of :obj:`str` or :obj:`int`
            The list of lights that should be returned.  You may pass
            individual identifiers (:obj:`int`), names to match (:obj:`str`) or
            regular expressions to match names of lights on the server
            (:obj:`str`, prefixed and suffixed by ``/``).

        Returns
        -------

        lights : :obj:`list` of :obj:`str`
            A list of string-integer identifiers for the lights, generated by
            **additively** building the list scanning each of the input ``ids``
            in order.
        """

        return _uniq(
            itertools.chain.from_iterable(
                [j for k in ids for j in self.get_lights(k)]
            )
        )

    def set_group_attrs(self, id, name=None, lights=None, hidden=None):
        """Set (some) group attributes, such as name, grouped lights and/or if
        it is hidden.

        Parameters with value == ``None`` will **not** be set.

        This method change attributes of the group.  Currently, we can only set
        its name, light membership and if it is hidden or not.


        Parameters
        ----------

        id : int, str
            The group identifier (:obj:`int`), its name (:obj:`str`) or a
            regular expression (:obj:`str`, prefixed and suffixed by ``/``) to
            match names of groups on the server

        name : :obj:`str`, optional
            The new name to set for the group.  If not set, do not change the
            group name.

        lights : :obj:`list` of :obj:`str` or :obj:`int`, optional
            The list of lights that should be part of the group.  You may pass
            individual identifiers (:obj:`int`), names to match (:obj:`str`) or
            regular expressions to match names of lights on the server
            (:obj:`str`, prefixed and suffixed by ``/``) to match names of
            lights/switches on the server.  If not set, then does not change
            current light membership for this group.

        hidden : :obj:`bool`, optional
            If the group should be hidden.  If not set, does not set
            hidden-status for the group

        """

        affected = self.get_groups(id)  # all groups matching id
        if not len(affected):
            logger.warning("No groups affected by attribute change")
            return

        if lights is not None:  # resolve
            logger.debug("Resolving %d light identity items", len(lights))
            lights = self._resolve_light_ids(lights)
            logger.debug("%d lights will be assigned to the group", len(lights))

        for k in affected:
            parts = [self.api_key, "groups", str(k)]
            data = {}
            if name is not None:
                data["name"] = name
            if lights is not None:
                data["lights"] = lights
            if hidden is not None:
                data["hidden"] = hidden
            self._put(parts, data=data)

    def set_group_state(self, id, values):
        """Set group to a **single** state

        This method will apply the stage change defined by ``values`` to all
        lights within the group.


        Parameters
        ----------

        id : int, str
            The group identifier (:obj:`int`), its name (:obj:`str`) or a
            regular expression (:obj:`str`, prefixed and suffixed by ``/``) to
            match names of groups on the server

        values : :obj:`list` of :obj:`str`
            A list of strings that can be absorbed by
            :py:meth:`_translate_light_state`, that will be analyzed in
            sequence and applied to each group matched.
        """

        affected = self.get_groups(id)

        if not len(affected):
            logger.warning("No groups affected by state change")
            return

        # for groups, we respect max/min color temperature for the
        # most restrictive lights (IKEA bulbs)
        for k, v in affected.items():
            parts = [self.api_key, "groups", str(k), "action"]
            data = self._translate_light_state(v["action"], (250, 454), values)
            self._put(parts, data=data)

    def _select_lights_by_integer_id(self, ids):
        """Selects all relevant group lights

        This method is similar to :py:meth:`get_group_lights`, except it only
        takes as input string-integer identifiers instead of :obj:`str` and
        :obj:`re.Pattern`.


        Parameters
        ----------

        ids : :obj:`list` of :obj:`str`
            List of integer identifiers for light/switches in the format of a
            string.


        Returns
        -------

        lights : dict
            A dictionary mapping :obj:`str` (actually integers) to :obj:`dict`
            containing the light inputs for the group/groups identified by
            each of the ``ids``.
        """

        lights = self.get_lights(None)  # gets all lights
        return dict([(k, v) for k, v in lights.items() if k in ids])

    def get_group_lights(self, id):
        """Set the state of a specific light inside the group

        Parameters
        ----------

        id : int, str
            The group identifier (:obj:`int`), its name (:obj:`str`) or a
            regular expression (:obj:`str`, prefixed and suffixed by ``/``) to
            match names of group on the server


        Returns
        -------

        lights : dict
            A dictionary mapping :obj:`str` (actually integers) to :obj:`dict`
            containing the light inputs for the group/groups identified by
            ``id``.

        """

        affected = self.get_groups(id)

        if not len(affected):
            return {}

        retval = {}
        for k, v in affected.items():
            retval.update(self._select_lights_by_integer_id(v["lights"]))

        return retval

    def _set_group_light_state(self, id, light_id, values):
        """Set the state of a specific light inside the group

        Parameters
        ----------

        id : int, str
            The group identifier (:obj:`int`) or its name (:obj:`str`)

        light_id : int, str
            The light/switch identifier (:obj:`int`), its name (:obj:`str`) or
            a regular expression (:obj:`str`, prefixed and suffixed by ``/``)
            to match names of lights/switches on the specific group.  Notice
            this will act as a sub-selector for the existing group lights.  For
            example, a value of ``/.*/`` will select all group lights and
            **not** all server lights.

        values : :obj:`list` of :obj:`str`
            A list of strings that can be absorbed by
            :py:meth:`_translate_light_state`, that will be analyzed and
            applied in sequence to the referred light/lights

        """

        affected = self.get_groups(id)

        if not len(affected):
            logger.warning("No groups affected by state change")
            return

        for gk, gv in affected.items():
            # select light identifiers that match, from the group lights
            group_lights = self._select_lights_by_integer_id(gv["lights"])
            light_id = _handle_id(light_id)
            affected_lights = dict(
                [
                    (k, v)
                    for k, v in group_lights.items()
                    if _id_predicate(k, v["name"], light_id)
                ]
            )
            self._set_light_state_dict(affected_lights, values)

    def set_group_lights(self, id, config):
        """Set the states of lights in a group from a dictionary configuration


        Parameters
        ----------

        id : str, int
            The group identifier (:obj:`int`) or its name (:obj:`str`)

        config : dict
            A dictionary mapping light identifiers (int, str) to state values
            to which they will be set

        """

        for k, v in config.items():
            k = _handle_id(k)
            self._set_group_light_state(id, k, v.split())
            if not self.wait_for_changes():
                logger.error(
                    "Timed-out while waiting for light changes (%s -> %s)", k, v
                )
            else:
                logger.info(
                    "Server acknowledged light state change (%s -> %s)", k, v
                )

    def store_scene(self, id, scene):
        """Stores the given scene


        Parameters
        ----------

        id : str, int
            The group identifier (:obj:`int`) or its name (:obj:`str`)

        scene : str, int
            The scene identifier (:obj:`int`) or its name (:obj:`str`), within
            the group

        """

        group = self.get_groups(id)
        if len(group) == 0:
            logger.error("No group being affected by scene storage")
            return
        if len(group) > 1:
            raise RuntimeError(
                "Scene storage can only affect one group "
                "at a time.  You selected %d groups instead" % (len(group),)
            )
        for k, v in group.items():
            scene = _handle_id(scene)
            candidates = [
                s
                for s in v["scenes"]
                if _id_predicate(s["id"], s["name"], scene)
            ]
            if len(candidates) == 0:
                logger.error("No scene being affected by scene storage")
                continue
            if len(candidates) > 1:
                raise RuntimeError(
                    "Scene storage can only affect one scene "
                    "at the time.  You selected %d scenes instead"
                    % (len(candidates),)
                )
            for s in candidates:
                parts = [
                    self.api_key,
                    "groups",
                    str(k),
                    "scenes",
                    s["id"],
                    "store",
                ]
                self._put(parts, data={"transitiontime": self.transitiontime})

    def store_scene2(self, id, scene, config):
        """Stores the given scene, given its desired properties


        Parameters
        ----------

        id : str, int
            The group identifier (:obj:`int`) or its name (:obj:`str`)

        scene : str, int
            The scene identifier (:obj:`int`) or its name (:obj:`str`), within
            the group

        config : dict
            A dictionary mapping light identifiers (int, str) to state values
            to which they should be set
        """

        groups = self.get_groups(id)

        if len(groups) == 0:
            raise RuntimeError(
                "Did not find any groups with id == '%s'" % (id,)
            )

        for gk, gv in groups.items():
            # select light identifiers that match, from the group lights
            group_lights = self._select_lights_by_integer_id(gv["lights"])

            # the resulting state to set lights in this scene/group is the
            # cumulative state by applying all changes listed, in the sequence
            # they were found
            state_lights = dict()
            for ck, cv in config.items():
                light_id = _handle_id(ck)
                affected_lights = dict(
                    [
                        (k, v)
                        for k, v in group_lights.items()
                        if _id_predicate(k, v["name"], light_id)
                    ]
                )
                state_lights.update(self._get_light_state_dict(affected_lights,
                    cv.split()))

            scenes = self.get_scenes(gk, scene)
            if len(scenes) == 0:
                raise RuntimeError(
                    "Did not find any scenes with id "
                    "== '%s' in group '%s'" % (scene, gv["name"])
                )

            for sk, sv in scenes.items():
                # sets each light in the scene
                for lk, lv in state_lights.items():
                    parts = [self.api_key, 'groups', gk, 'scenes', sk,
                            'lights', lk, 'state']
                    self._put(parts, data=lv)

    def restore_light_state(self, d):
        """Restores the state of lights given an input dictionary

        Parameters
        ----------

        d : dict
            A dictionary mapping light identifiers (int, str) to state values
            to which they will be reset
        """

        for k, v in d.items():
            state = v["state"]
            if "alert" in state:
                del state["alert"]
            if "reachable" in state:
                del state["reachable"]
            if "effect" in state:
                del state["effect"]
            if "on" in state and not state["on"]:
                state = dict(on=False)
            if "colormode" in state:
                cm = state["colormode"]
                del state["colormode"]
                if cm == "ct":
                    if "xy" in state:
                        del state["xy"]
                    if "hue" in state:
                        del state["hue"]
                    if "sat" in state:
                        del state["sat"]
                if cm == "xy":
                    if "ct" in state:
                        del state["ct"]
                    if "hue" in state:
                        del state["hue"]
                    if "sat" in state:
                        del state["sat"]
                if cm == "hs":
                    if "ct" in state:
                        del state["ct"]
                    if "xy" in state:
                        del state["xy"]
            state["transitiontime"] = self.transitiontime
            self._set_single_light(k, state)
        if not self.wait_for_changes():
            logger.error("Timed-out while waiting for light changes")
        else:
            logger.info("Server acknowledged light state change")

    def get_scenes(self, group, id=None):
        """Returns one or more scenes from a given group


        Parameters
        ----------

        group : str
            The group identifier (integer wrapped as a string)

        id : str, int
            The scene identifier (:obj:`int`), its name (:obj:`str`) or a
            regular expression (:obj:`str`, prefixed and suffixed by ``/``) to
            match names of group on the server.  If not set, returns data from
            all scenes


        Returns
        -------

        scenes : dict
            A dictionary mapping :obj:`str` (actually integers) to :obj:`dict`
            containing the scenes the group identified by ``group``.

        """

        id = _handle_id(id)

        parts = [self.api_key, "groups", group, "scenes"]
        candidates = self._get(parts).json()
        if id is not None:
            candidates = dict(
                [
                    (k, v)
                    for k, v in candidates.items()
                    if _id_predicate(k, v["name"], id)
                ]
            )

        retval = {}
        for k in candidates:
            parts_scenes = parts + [k]
            retval[k] = self._get(parts_scenes).json()
        return retval

    def recall_scene(self, group, scene):
        """Recalls a given scene from a given group


        Parameters
        ----------

        group : str
            The group identifier (:obj:`int`), its name (:obj:`str`) or a
            regular expression (:obj:`str`, prefixed and suffixed by ``/``) to
            match names of group on the server.

        id : str, int
            The scene identifier (:obj:`int`), its name (:obj:`str`) or a
            regular expression (:obj:`str`, prefixed and suffixed by ``/``) to
            match names of group on the server.
        """

        group = _handle_id(group)
        scene = _handle_id(scene)

        groups = self.get_groups(group)

        recalled = 0
        for gk, gv in groups.items():
            parts = [self.api_key, "groups", gk, "scenes"]
            scenes = self.get_scenes(gk, scene)
            for sk, sv in scenes.items():
                parts_scene = parts + [sk, "recall"]
                self._put(parts_scene, data={})
                recalled += 1

        if recalled == 0:
            raise RuntimeError(
                "Did not find scene '%s' at group '%s'" % (scene, group)
            )
