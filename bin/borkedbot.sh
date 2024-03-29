#!/usr/bin/env bash
# Management script for borkedbot kubernetes processes
# Adapted from https://phabricator.wikimedia.org/F33972266

set -e

DEPLOYMENT=borkedbot.bot
POD_NAME=borkedbot.bot

CONFIG=etc/config-k8s.yaml

TOOL_DIR=$(cd $(dirname $0)/.. && pwd -P)
VENV=${TOOL_DIR}/../venv-k8s-py37
if [[ -f ${VENV}/bin/activate ]]; then
    # Enable virtualenv
    source ${VENV}/bin/activate
fi

KUBECTL=/usr/bin/kubectl

_get_pod() {
    $KUBECTL get pods \
        --output=jsonpath={.items..metadata.name} \
        --selector=name=${POD_NAME}
}

case "$1" in
    start)
        echo "Starting borkedbot k8s deployment..."
        $KUBECTL create --validate=true -f ${TOOL_DIR}/etc/deployment.yaml
        ;;
    run)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.tw_follows  #--config ${CONFIG}
        ;;
    run-fandom)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot fandom filler..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.fandom_page
        ;;
    run-yt)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot youtube filler..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.yt_chan_fill --all_items --enwiki
        ;;
    run-yt-vid)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot youtube video filler..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.yt_vid_fill
        ;;
     run-yt-fol)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot youtube subs filler..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.yt_follows
        ;;
     run-yt-fol-all)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot youtube subs filler..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.yt_follows --all_items
        ;;
     run-yt-fol-enwiki)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot youtube subs enwiki filler..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.yt_follows --enwiki
        ;;
    run-twt)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot twitter filler..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.tw_user_id
        ;;
    run-twt-fol)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot twitter follows filler..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.tw_follows
        ;;
    run-prefer-dates)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot prefer dates..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.prefer_dates
        ;;
    run-ballotpedia)
        date +%Y-%m-%dT%H:%M:%S
        echo "Running borkedbot ballotpedia..."
        cd ${TOOL_DIR}
        exec python -m borked_bot.ballotpedia_page
        ;;

    stop)
        echo "Stopping borkedbot k8s job..."
        $KUBECTL delete job ${DEPLOYMENT}
        # FIXME: wait for the pods to stop
        ;;
    restart)
        echo "Restarting borkedbot pod..."
        exec $KUBECTL delete pod $(_get_pod)
        ;;
    status)
        echo "Active pods:"
        exec $KUBECTL get pods -l name=${POD_NAME}
        ;;
    tail)
        exec $KUBECTL logs -f $(_get_pod)
        ;;
    update)
        echo "Updating git clone..."
        cd ${TOOL_DIR}
        git fetch &&
        git --no-pager log --stat HEAD..@{upstream} &&
        git rebase @{upstream}
        ;;
    attach)
        echo "Attaching to pod..."
        exec $KUBECTL exec -i -t $(_get_pod) -- /bin/bash
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|tail|update|attach}"
        exit 1
        ;;
esac

exit 0
# vim:ft=sh:sw=4:ts=4:sts=4:et:
