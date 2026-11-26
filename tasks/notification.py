import structlog

from celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task
def send_notification(
    recipient_email: str,
    subject: str,
    message: str,
) -> None:
    logger.info(
        "notification_simulated",
        channel="email",
    )
