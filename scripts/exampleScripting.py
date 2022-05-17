#!/usr/bin/env python3

"""
Generate previews of the available scripts
"""

import sys
from kikit.doc import runScriptingExample, runBoardExampleJoin

counter = 0

def autoName():
    global counter
    counter += 1
    return f"scriptingPanel{counter}"

SRC = "doc/resources/conn.kicad_pcb"

print(
"""
# Scripting examples

""")

print(
"""
# Basic panels & layout

Let's start with our first panel.
""")

runBoardExample(autoName(),
    [["panelize"],
        ["--layout", "grid; rows: 2; cols: 2;"],
        ["--tabs", "full"],
        ["--cuts", "vcuts"],
        [SRC]])

runExampleJoin()