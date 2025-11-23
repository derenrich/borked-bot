#!/bin/bash

# wrapper script to launch run.py with the correct environment and passed arguments
# meant for use in toolforge


python3 -m venv ~/venv
source ~/venv/bin/activate
pip install -U pip wheel
pip install uv

cd ~/borked-bot

uv run "$@"

# to test this do 
# jobs run test --image python3.13 --mount all --command "~/borked-bot/run.sh python -m borked_bot.run bsky_did" --filelog
# or you can run it directly in a shell by doing 
# toolforge webservice python3.13 shell --mount all

# schedluing the job would look like 
# toolforge jobs run fandom-cron --command "~/borked-bot/run.sh python -m borked_bot.run fandom_page" --image python3.13 --mount all --schedule "@daily" --timeout 3600 --filelog
# check status with 
# toolforge jobs list