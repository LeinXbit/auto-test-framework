# -*- coding: utf-8 -*-
"""
YAML test data reader
    - Loads a YAML file and returns parsed Python objects
    - Used by data-driven test cases (Phase 3+) to externalize case data
"""
import io

import yaml


def load_yaml(path):
    """
    Load a YAML file and return the parsed content.
    :param path: absolute or relative path to the YAML file
    :return: parsed Python object (dict / list / scalar)
    """
    with io.open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
