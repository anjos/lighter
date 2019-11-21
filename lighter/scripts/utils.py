#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""Helpers for our command-line interface"""

import yaml
import collections


def ordered_yaml_load(
    stream, Loader=yaml.Loader, object_pairs_hook=collections.OrderedDict
):
    """Loads a YAML data source, preserving dictionary order

    From: https://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
    """

    class OrderedLoader(Loader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))

    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
    )

    return yaml.load(stream, OrderedLoader)
