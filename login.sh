#!/bin/bash
kubectl run login-shell --restart=Never --rm -i --tty --image docker-registry.tools.wmflabs.org/toolforge-python37-sssd-base:latest --labels="name=borkedbot.bot-twit,toolforge=tool" -- bash -c "cd /data/project/borkedbot/borked-bot/; rm pywikibot.lwp; . ../venv-k8s-py37/bin/activate; python login.py"
