from celery import Celery

celery_app = Celery(
    "helpdesk",
    broker="redis://localhost:6379/1",
    include=["tasks.notification"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
)