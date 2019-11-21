#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

import json

import click
import pkg_resources
from click_plugins import with_plugins

from . import lighter

from ..config import load as config_load
from ..deconz import Server

from ..log import verbosity_option, get_logger, echo_normal
logger = get_logger(__name__)


@with_plugins(pkg_resources.iter_entry_points("lighter.config.cli"))
@click.group(cls=lighter.AliasedGroup)
def config():
    """Commands for dealing with the global configuration
    """
    pass


@config.command(
    epilog="""
Examples:

  1. Gets the whole device configuration as a JSON file

     $ lighter -vv config get

"""
)
@verbosity_option()
@lighter.raise_on_error
def get():
    """Gets the whole webserver configuration in JSON format
    """

    config = config_load()
    if not config:
        raise RuntimeError("No configuration file loaded - cannot proceed")

    server = Server(
            host=config["host"],
            port=config["port"],
            api_key=config.get("api_key"),
            transitiontime=config.get("transitiontime", 10),
            )

    data = server.config_pull()
    if args["<path>"]:
        with open(args["<path>"], "wt") as f:
            f.write(json.dumps(data, indent=4))
    else:
        print(json.dumps(data, indent=4))


@config.command(
    epilog="""
Examples:

  1. Gets a new API key from the server

     $ lighter -vv config apikey

"""
)
@verbosity_option()
@lighter.raise_on_error
def apikey():
    """Gets a new API key from the server
    """

    config = config_load()
    if not config:
        raise RuntimeError("No configuration file loaded - cannot proceed")

    server = Server(host=config["host"], port=config["port"])
    key = server.get_api_key()
    echo_normal("API key: %s" % key)
