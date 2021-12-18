#!/usr/bin/env python3

import click
import json
from collections import OrderedDict

def setKey(obj, path, value):
    key = path[0] if isinstance(obj, dict) else int(path[0])
    if len(path) == 1:
        obj[key] = value
        return
    setKey(obj[key], path[1:], value)

@click.command()
@click.argument("input", type=click.File("r"))
@click.argument("output", type=click.File("w"))
@click.option("--property", "-s", type=str, multiple=True, help="<path>=<value>")
def run(input, output, property):
    """
    Set a key to a value in JSON.
    """
    obj = json.load(input, object_pairs_hook=OrderedDict)
    for p in property:
        path, value = tuple(p.split("="))
        path = path.split(".")
        value = json.loads(value, object_pairs_hook=OrderedDict)
        setKey(obj, path, value)

    json.dump(obj, output, indent=4)

if __name__ == "__main__":
    run()
