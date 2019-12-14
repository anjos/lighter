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


@with_plugins(pkg_resources.iter_entry_points("lighter.scenes.cli"))
@click.group(cls=lighter.AliasedGroup)
def scenes():
    """Commands for dealing with individual scenes
    """
    pass


@scenes.command(
    epilog="""
Examples:

  1. Gets information on all scenes available for a group (sort by id):

     $ lighter -vv scenes get 1

  2. Gets information on all scenes available for a group (sort by name):

     $ lighter -vv scenes get --sort-name Office

  3. Gets information about one specific scene (1) of a group (1):

     $ lighter -vv scenes get 1 1

"""
)
@click.argument("id", required=True)
@click.argument("scene", required=False, default=None)
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
def get(id, scene, sort_name):
    """Gets information from some or all scenes in a group in the server
    """

    server = setup_server()
    groups = server.get_groups(id)

    for k in groups:
        print("Group: %s" % k)
        data = server.get_scenes(k, scene)
        print(json.dumps(data, indent=4))


@scenes.command(
    epilog="""
Examples:

  1. Sets scene 2 from group 1 to the values indicated in the YAML file

     $ lighter -vv scenes set 1 2 file.yaml

  2. Sets scene "Relax" on "Living room":

     $ lighter -vv scenes set "Living room" "Relax" file.yaml

"""
)
@click.argument("id", required=True)
@click.argument("scene", required=True)
@click.argument(
    "file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
)
@verbosity_option()
@lighter.raise_on_error
def set(id, scene, file):
    """Resets a scene by id or name

    For more details about the YAML file input, please consult the command
    ``groups scene``.

    After setting the scene, the previous state of lights in the group is
    recovered.
    """

    server = setup_server()

    # store current light state, so it can be recovered
    old_state = server.get_group_lights(id)

    # loads the input YAML file
    with open(file, "rb") as f:
        states = ordered_yaml_load(f)

    server.store_scene2(id, scene, states)


@scenes.command(
    epilog="""
Examples:

  1. Sets multiple scenes at once:

     $ lighter -vv scenes setmany file.yaml

     The "scene" file should be organized as this:

         \b
         <group 0>:
            <scene 0>:
                <light>: <values>
                <light>: <values>
                ...
            <scene 1>:
                <light>: <values>
                <light>: <values>
                ...
            ...
         <group 1>:
            <scene 0>:
                <light>: <values>
                <light>: <values>
                ...
            <scene 1>:
                <light>: <values>
                <light>: <values>
                ...
            ...
        ...

    Keys for groups and scenes may be integer or string identifiers.  Keys for
    each light may be integer, string or regular expressions.

"""
)
@click.argument(
    "file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
)
@verbosity_option()
@lighter.raise_on_error
def setmany(file):
    """Resets all listed scenes

    After setting the scene, the previous state of lights is recovered
    """

    server = setup_server()

    # loads the input YAML file
    with open(file, "rb") as f:
        groups = ordered_yaml_load(f)

    for group, scenes in groups.items():
        for scene, lights in scenes.items():
            server.store_scene2(group, scene, lights)


@scenes.command(
    epilog="""
Examples:

  1. Recalls scene 2 from group 1:

     $ lighter -vv scenes recall 1 2

  2. Recalls scene "Relax" on "Living room":

     $ lighter -vv scenes recall "Living room" "Relax"

"""
)
@click.argument("id", required=True)
@click.argument("scene", required=True)
@verbosity_option()
@lighter.raise_on_error
def recall(id, scene):
    """Recalls a scene by id or name
    """

    server = setup_server()
    server.recall_scene(id, scene)
