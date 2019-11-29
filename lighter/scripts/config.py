#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

import json

import click
import pkg_resources
from click_plugins import with_plugins

from . import lighter

from ..deconz import setup_server

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

    server = setup_server()
    data = server.get_config()
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

    server = setup_server()
    key = server.get_api_key()
    echo_normal("API key: %s" % key)



@config.command(
    epilog="""
Examples:

  1. Cleans-up old API keys from the server

     $ lighter -vv config cleanup

"""
)
@verbosity_option()
@lighter.raise_on_error
def cleanup():
    """Cleans-up old API keys from the server
    """

    server = setup_server()
    server.remove_old_apikeys(days_unused=30)
