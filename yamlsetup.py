#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Importing this makes PyYAML read On/Off/Yes/No (and o/y/n...) as plain
strings instead of booleans, which matters for ISV words used as YAML keys
and values. Import it before loading any course YAML."""

from yaml.resolver import Resolver

# remove resolver entries for On/Off/Yes/No
# https://stackoverflow.com/a/36470466/52023
for ch in "OoYyNn":
    if len(Resolver.yaml_implicit_resolvers[ch]) == 1:
        del Resolver.yaml_implicit_resolvers[ch]
    else:
        Resolver.yaml_implicit_resolvers[ch] = [x for x in
                                                Resolver.yaml_implicit_resolvers[ch] if
                                                x[0] != 'tag:yaml.org,2002:bool']
