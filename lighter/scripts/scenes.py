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
    server.refresh_cache()
    old_state = server.get_group_lights(id)  # gets all group lights

    # loads the input YAML file
    with open(file, "rb") as f:
        states = ordered_yaml_load(f)

    server.set_group_lights(id, states)
    server.store_scene(id, scene)
    server.restore_light_state(old_state)


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

    # store current light state, so it can be recovered
    server.refresh_cache()

    # loads the input YAML file
    with open(file, "rb") as f:
        groups = ordered_yaml_load(f)

    for group, scenes in groups.items():
        for scene, lights in scenes.items():
            old_state = server.get_group_lights(group)
            server.set_group_lights(group, lights)
            server.store_scene(group, scene)
            server.restore_light_state(old_state)
