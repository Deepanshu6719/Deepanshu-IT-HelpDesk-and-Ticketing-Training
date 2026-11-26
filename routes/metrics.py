import os

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)

router = APIRouter(tags=["Monitoring"])


@router.get("/metrics", include_in_schema=False)
def get_metrics():
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()

        multiprocess.MultiProcessCollector(registry)

        metrics_data = generate_latest(registry)

    else:
        metrics_data = generate_latest()

    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST,
    )
