#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

import json

import click
import pkg_resources
from click_plugins import with_plugins

from . import lighter

from ..log import verbosity_option, get_logger, echo_normal, echo_info
from ..deconz import setup_server

logger = get_logger(__name__)


@with_plugins(pkg_resources.iter_entry_points("lighter.lights.cli"))
@click.group(cls=lighter.AliasedGroup)
def lights():
    """Commands for dealing with individual lights
    """
    pass


@lights.command(
    epilog="""
Examples:

  1. Gets information on all lights/switches available (sort by id):

     $ lighter -vv lights get

\b
  2. Gets information on all lights/switches available (sort by id, prints
     summary only):

     $ lighter -vv lights get --summary

  3. Gets information on all lights/switches available (sort by name):

     $ lighter -vv lights get --sort-name

  4. Gets information about one specific light (includes its state):

     $ lighter -vv lights get 1

  5. Gets information about one or more lights by regular expression, print
     summary:

     $ lighter -vv lights get '/^Entrance.*$/' --summary

"""
)
@click.argument("id", required=False, default=None)
@click.option(
    "-s",
    "--summary/--no-summary",
    default=False,
    help="If set, then summarize in a human readable way, information from "
    "all lights/switches available instead of outputing the JSON response",
)
@click.option(
    "-n",
    "--sort-name/--no-sort-name",
    default=False,
    help="If set and outputting information for all installed lights and "
    "switches, then sort information by asset name instead of using their "
    "(integer) identifier",
)
@verbosity_option()
@lighter.raise_on_error
def get(id, summary, sort_name):
    """Gets information from some or all lights in the server
    """

    server = setup_server()
    data = server.get_lights(id)

    if not summary:
        echo_normal(json.dumps(data, indent=4))
    else:  # just print overview
        if sort_name:
            sorting = sorted(data.keys(), key=lambda x: data[x]["name"])
        else:
            sorting = sorted(data.keys(), key=lambda x: int(x))

        for k in sorting:
            state = "ON" if data[k]["state"]["on"] else "OFF"
            echo_normal(
                "%s: %s (%s, %s) [%s]"
                % (
                    k,
                    data[k]["name"],
                    data[k]["type"],
                    data[k]["manufacturername"],
                    state,
                )
            )


@lights.command(
    epilog="""
Examples:

  1. Renames a particular light/switch by integer identifier:

     $ lighter -vv lights name 1 "new name"

  2. Renames a particular light/switch by name (from "old name" to "new name"):

     $ lighter -vv lights name "old name" "new name"

\b
  3. Renames a particular light/switch by regular expression (notice this may
     affect multiple lights at once):

     $ lighter -vv lights name "/^old.*/" "new name"

"""
)
@click.argument("id", required=True)
@click.argument("value", type=str, required=True)
@verbosity_option()
@lighter.raise_on_error
def name(id, value):
    """Sets the name of particular light/switch
    """

    server = setup_server()
    server.set_light_name(id, value)


@lights.command(
    epilog="""
Examples:

  1. Turns on a particular light/switch:

     $ lighter -vv lights state 1 on

  2. Turns off a particular light/switch:

     $ lighter -vv lights state 1 off

  3. Turns a particular light (that supports it) on with a given brigthness and
     color temperature setting:

     $ lighter -vv lights state 1 on 90% cool

  4. Turns all lights matching a given regular expression off:

     $ lighter -vv lights state '/^Entrance.*/' off

"""
)
@click.argument("id", required=True)
@click.argument("values", type=str, required=True, nargs=-1)
@verbosity_option()
@lighter.raise_on_error
def state(id, values):
    """Sets the state of particular light/switch

    \b
    Valid values are among the following (that could be given in any order):

    * value="on" or "off": light or switch is turned ON or OFF
    * value="0%" to "100%": brightness
    * value="2000K" to 6500K": white temperature
    * value="candle|warm|warm+|soft|natural|cool|day-|day": white temperature
      in the following ranges candle=2000K, warm=2700K, warm+=3000K,
      soft=3500K, natural=3700K, cool=4000K, day-=5000K, day=6500K
    * value="alert": turns lamp alert mode ON (for a few seconds)
    """

    server = setup_server()
    server.set_light_state(id, values)
