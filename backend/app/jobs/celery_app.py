from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ahc",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.jobs.tasks_ads",
        "app.jobs.tasks_messaging",
        "app.jobs.tasks_inventory",
        "app.jobs.tasks_reminders",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    beat_schedule={
        "low-stock-check-every-hour": {
            "task": "app.jobs.tasks_inventory.check_low_stock",
            "schedule": 3600.0,
        },
        "follow-up-reminders-every-morning": {
            "task": "app.jobs.tasks_reminders.send_follow_up_reminders",
            "schedule": 3600.0 * 6,
        },
        "maintenance-reminders-daily": {
            "task": "app.jobs.tasks_reminders.send_maintenance_reminders",
            "schedule": 3600.0 * 24,
        },
    },
)
