#!/bin/sh

set -eu

export PROMETHEUS_MULTIPROC_DIR="$(mktemp -d /tmp/helpdesk_metrics.XXXXXX)"

exec gunicorn main:app \
    --worker-class uvicorn_worker.UvicornWorker \
    --logger-class core.gunicorn_logger.JSONGunicornLogger \
    --workers 2 \
    --bind 0.0.0.0:8000