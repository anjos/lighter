#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''Utilities for searching and loading the right configuration file'''

import os
import json


def load():
  '''Loads the configuration file from either the home dir or local dir

  Returns:

    dict: A dictionary with loaded options

  '''

  # list of candidates in order of preference
  candidates = [
      os.path.realpath('.lighter.json'),
      os.path.expanduser('~/.lighter.json'),
      ]

  for k in candidates:
    if not os.path.exists(k): continue
    with open(k) as f:
      return json.load(f)

  # if you get to this point, no configuration is available, return empty
  return {}
