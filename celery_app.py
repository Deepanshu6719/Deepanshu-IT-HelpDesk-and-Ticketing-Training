from celery import Celery
from celery.signals import (
    before_task_publish,
    setup_logging,
    task_postrun,
    task_prerun,
)
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
)

from core.config import settings
from core.logging import configure_logging

celery_app = Celery(
    "helpdesk",
    broker=settings.CELERY_BROKER_URL,
    include=["tasks.notification"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    worker_redirect_stdouts=False,
)


@setup_logging.connect
def initialize_worker_logging(**kwargs):
    configure_logging()


@before_task_publish.connect
def attach_request_context(headers=None, **kwargs):
    if headers is None:
        return

    request_id = get_contextvars().get("request_id")

    if request_id:
        headers["request_id"] = request_id


@task_prerun.connect
def bind_task_context(
    task_id=None,
    task=None,
    **kwargs,
):
    clear_contextvars()

    bind_contextvars(task_id=task_id)

    if task is not None:
        headers = task.request.headers or {}

        request_id = headers.get("request_id")

        if request_id:
            bind_contextvars(request_id=request_id)


@task_postrun.connect
def clear_task_context(**kwargs):
    clear_contextvars()
