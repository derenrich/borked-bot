#!/bin/bash

# wrapper script to launch run.py with the correct environment and passed arguments
# meant for use in toolforge


python3 -m venv ~/venv
source ~/venv/bin/activate
pip install -U pip wheel
pip install uv

uv run "$@"


