#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

import json

import yaml
import click
import pkg_resources
from click_plugins import with_plugins

from . import lighter
from .utils import ordered_yaml_load

from ..log import verbosity_option, get_logger, echo_normal
from ..deconz import setup_server

logger = get_logger(__name__)


@with_plugins(pkg_resources.iter_entry_points("lighter.groups.cli"))
@click.group(cls=lighter.AliasedGroup)
def groups():
    """Commands for dealing with individual light/switch groups
    """
    pass


@groups.command(
    epilog="""
Examples:

  1. Gets information on all groups available (sort by id):

     $ lighter -vv groups get

  2. Gets information on all groups available (sort by name):

     $ lighter -vv groups get --sort-name

  3. Gets information about one specific group (includes its state):

     $ lighter -vv groups get 1

"""
)
@click.argument("id", required=False, default=None)
@click.option(
    "-s",
    "--summary/--no-summary",
    default=False,
    help="If set, then summarize in a human readable way, information from "
    "all groups available instead of outputing the JSON response",
)
@click.option(
    "-n",
    "--sort-name/--no-sort-name",
    default=False,
    help="If set and outputting information for all installed groups, "
    "then sort information by asset name instead of using their "
    "(integer) identifier",
)
@verbosity_option()
@lighter.raise_on_error
def get(id, summary, sort_name):
    """Gets information from some or all groups in the server
    """

    server = setup_server()
    data = server.get_groups(id)

    if not summary:
        print(json.dumps(data, indent=4))
    else:  # just print overview
        if sort_name:
            sorting = sorted(data.keys(), key=lambda x: data[x]["name"])
        else:
            sorting = sorted(data.keys(), key=lambda x: int(x))

        lights = server.get_lights(None)  # cross match all lights

        for k in sorting:
            state = "OFF"
            if data[k]["state"]["any_on"]:
                state = "PARTIALLY ON"
            if data[k]["state"]["all_on"]:
                state = "ON"
            state = "ON" if data[k]["state"]["any_on"] else "OFF"
            echo_normal(
                "%s: %s (%s scenes, %d lights) [%s]"
                % (
                    k,
                    data[k]["name"],
                    len(data[k]["scenes"]),
                    len(data[k]["lights"]),
                    state,
                )
            )

            # print scene information
            echo_normal("  Scenes:")
            scenes = data[k]["scenes"]
            if sort_name:
                scenes_sorting = sorted(scenes, key=lambda x: x["name"])
            else:
                scenes_sorting = sorted(scenes, key=lambda x: int(x["id"]))
            for sk in scenes_sorting:
                echo_normal("    %s: %s" % (sk["id"], sk["name"]))

            # print light information
            echo_normal("  Lights:")
            group_lights = dict(
                [
                    (lk, lv)
                    for lk, lv in lights.items()
                    if lk in data[k]["lights"]
                ]
            )
            if sort_name:
                light_sorting = sorted(
                    group_lights.keys(), key=lambda x: group_lights[x]["name"]
                )
            else:
                light_sorting = sorted(
                    group_lights.keys(), key=lambda x: int(x)
                )

            for k in light_sorting:
                state = "ON" if group_lights[k]["state"]["on"] else "OFF"
                echo_normal(
                    "    %s: %s (%s, %s) [%s]"
                    % (
                        k,
                        group_lights[k]["name"],
                        group_lights[k]["type"],
                        group_lights[k]["manufacturername"],
                        state,
                    )
                )


@groups.command(
    epilog="""
Examples:

  1. Renames a particular group by integer identifier:

     $ lighter -vv groups name 1 "new name"

  2. Renames a particular group by name (from "old name" to "new name"):

     $ lighter -vv groups name "old name" "new name"

\b
  3. Renames a particular group by regular expression (notice this may
     affect multiple groups at once):

     $ lighter -vv groups name "/^old.*/" "new name"

"""
)
@click.argument("id", required=True)
@click.argument("value", type=str, required=True)
@verbosity_option()
@lighter.raise_on_error
def name(id, value):
    """Sets the name of particular group
    """

    server = setup_server()
    server.set_group_attrs(id, name=value)


@groups.command(
    epilog="""
Examples:

\b
  1. Adds devices 1, 2 and 3 to group 32:

     $ lighter -vv groups member 32 1 2 3

  2. Adds all devices with names starting with "Office" to the "Office" group:

     $ lighter -vv groups member "Office" "/Office.*/"

\b
  3. Membership is set cumulatively.  This command sets all lights with names
     starting with "Living" and "Corridor" to the group "Living room":

     $ lighter -vv groups member "Living room" "/Living.*/" "/Corridor.*/"

  4. Remove all lights from a given group:

     $ lighter -vv groups member "Living room"

"""
)
@click.argument("id", required=True)
@click.argument("value", type=str, required=False, nargs=-1)
@verbosity_option()
@lighter.raise_on_error
def member(id, value):
    """Sets the membership of a particular group
    """

    server = setup_server()
    server.set_group_attrs(id, lights=value)


@groups.command(
    epilog="""
Examples:

  1. Turns on a particular group:

     $ lighter -vv groups state 1 on

  2. Turns off a particular group:

     $ lighter -vv groups state 1 off

  3. Turns a particular group (that supports it) on with a given brigthness and
     color temperature setting:

     $ lighter -vv groups state 1 on 90% cool

  4. Turns all groups matching a given regular expression off:

     $ lighter -vv groups state '/.*/' off

"""
)
@click.argument("id", required=True)
@click.argument("values", type=str, required=True, nargs=-1)
@verbosity_option()
@lighter.raise_on_error
def state(id, values):
    """Sets the state of particular group

    Through this command, you can only set the state of the whole group at
    once.  Discrete light assignements are not possible.

    Valid values are among the following (that could be given in any order):

    \b
    * value="on" or "off": light or switch is turned ON or OFF
    * value="0%" to "100%": brightness
    * value="2000K" to 6500K": white temperature
    * value="candle|warm|warm+|soft|natural|cool|day-|day": white temperature
      in the following ranges candle=2000K, warm=2700K, warm+=3000K,
      soft=3500K, natural=3700K, cool=4000K, day-=5000K, day=6500K
    * value="alert": turns lamp alert mode ON (for a few seconds)
    """

    server = setup_server()
    server.set_group_state(id, values)


@groups.command(
    epilog="""
Examples:

  1. Sets-up multiple lights in a group to a particular state:

     $ lighter -vv groups setup 1 file.yaml

  2. Sets-up multiple lights in a group by name:

     $ lighter -vv groups setup Office file.yaml

"""
)
@click.argument("id", required=True)
@click.argument(
    "file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
)
@verbosity_option()
@lighter.raise_on_error
def scene(id, file):
    """Sets the state of particular group to a particular scene

    Through this command, you can set the state of the whole group discretely,
    light by light.  The input file must be a YAML dictionary mapping the state
    of the various ligths.  Keys must be light identifiers (name or integer
    id), or even a regular expression (prefix/suffix it with the character
    '/').  Order matters. Example:

    \b
    /.*/: off
    Office Window: on 60% natural
    /Office ceiling.*/: on 100% cool

    \b
    This would first turn off all lights, and then turn on the light named
    `Office Window` to 60% on natural lighting, then it would turn on all
    lights in the group matching the regular expression "Office ceiling.*" to
    100% on cool lighting.

    Valid values are among the following (that could be given in any order):

    \b
    * value="on" or "off": light or switch is turned ON or OFF
    * value="0%" to "100%": brightness
    * value="2000K" to 6500K": white temperature
    * value="candle|warm|warm+|soft|natural|cool|day-|day": white temperature
      in the following ranges candle=2000K, warm=2700K, warm+=3000K,
      soft=3500K, natural=3700K, cool=4000K, day-=5000K, day=6500K
    * value="alert": turns lamp alert mode ON (for a few seconds)
    """

    server = setup_server()
    with open(file, "rb") as f:
        states = ordered_yaml_load(f)
    server.set_group_lights(id, states)
