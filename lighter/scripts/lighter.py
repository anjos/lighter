#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""Controls the setup inside a deconz server

Usage: %(prog)s [-v...] pull [<path>]
       %(prog)s [-v...] push <path>
       %(prog)s --help
       %(prog)s --version


Commands:

  pull  Retrieves the configuration from the deCONZ REST-ful server
  push  Pushes a new configuration to the deCONZ REST-ful server


Arguments:

  <path>  A JSON formatted configuration file containing the configuration to
          push (or the result of the pull operation)


Options:
  -h, --help                   Shows this help message and exits
  -V, --version                Prints the version and exits
  -v, --verbose                Increases the output verbosity level. May be
                               used multiple times


Examples:

  To use this program, you must first configure the server information and your
  credentials (token) to a file named ${PWD}/.lighter.json or
  ${HOME}/.lighter.json, that will be used for the pull and push operations.
  This file should look like the following:

    {
    # example
    }

  1. Pulls current configuration from server, writes to the screen:

     $ %(prog)s -vv pull


  2. Pulls current configuration from server, writes to file:

     $ %(prog)s -vv pull config.json


  3. Push configuration (possibly after local changes) back to server:

     $ %(prog)s -vv push config.json

"""


import os
import sys

import logging
logger = logging.getLogger(__name__)

import pkg_resources
import docopt


def main(user_input=None):

  if user_input is not None:
    argv = user_input
  else:
    argv = sys.argv[1:]

  completions = dict(
      prog=os.path.basename(sys.argv[0]),
      version=pkg_resources.require('baker')[0].version,
      hostname=socket.gethostname(),
      )

  args = docopt.docopt(
      __doc__ % completions,
      argv=argv,
      version=completions['version'],
      )

  return 0
