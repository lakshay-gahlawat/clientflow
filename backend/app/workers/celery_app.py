"""
Celery application instance. Task modules and Beat schedule are added
in Phase 7 (Redis + Celery + follow-up notifications).
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "clientflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "scan-due-followups-every-minute": {
            "task": "app.workers.tasks.scan_due_followups",
            "schedule": 60.0,
        },
    },
)
