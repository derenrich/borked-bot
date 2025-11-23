#!/bin/bash

# wrapper script to launch run.py with the correct environment and passed arguments
# meant for use in toolforge

python3 -m pip install --user uv

uv run "$@"


