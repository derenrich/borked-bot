#!/bin/bash

set -euxo pipefail

for YAML_CONF in *-cron.yaml; do
    kubectl apply -f $YAML_CONF
done

echo "Done updating CronJobs."
