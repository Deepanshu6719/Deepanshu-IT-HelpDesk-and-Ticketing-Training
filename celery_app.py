from celery import Celery

from core.config import settings

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
)
