from datetime import datetime, timedelta
from app.jobs.celery_app import celery_app
from app.jobs.async_helper import run_async


async def _send_follow_up_reminders():
    from app.models.lead import FollowUp
    from app.models.misc import Notification
    from app.models.enums import NotificationType, FollowUpStatus

    now = datetime.utcnow()
    overdue = await FollowUp.find(
        FollowUp.status == FollowUpStatus.PENDING, FollowUp.due_date < now
    ).to_list()

    created = 0
    for fu in overdue:
        await Notification(
            user_id=fu.assigned_to_user_id, branch_id=fu.branch_id,
            type=NotificationType.OVERDUE_FOLLOW_UP, title="Overdue follow-up",
            message=f"Follow-up due {fu.due_date.strftime('%d-%b-%Y')} is overdue",
            link=f"/follow-ups/{fu.id}",
        ).insert()
        created += 1
    return {"overdue_count": len(overdue), "notifications_created": created}


async def _send_maintenance_reminders():
    from app.models.service import HairSystemInstallation
    from app.models.misc import Notification
    from app.models.enums import NotificationType

    cutoff = datetime.utcnow() + timedelta(days=7)
    due_soon = await HairSystemInstallation.find(
        HairSystemInstallation.is_active == True,  # noqa: E712
        HairSystemInstallation.next_maintenance_due != None,  # noqa: E711
        HairSystemInstallation.next_maintenance_due <= cutoff,
    ).to_list()

    created = 0
    for installation in due_soon:
        await Notification(
            branch_id=installation.branch_id, type=NotificationType.UPCOMING_APPOINTMENT,
            title="Maintenance due soon",
            message=f"Customer {installation.customer_id} has maintenance due "
                    f"{installation.next_maintenance_due.strftime('%d-%b-%Y')}",
            link=f"/customers/{installation.customer_id}",
        ).insert()
        created += 1
    return {"due_soon_count": len(due_soon), "notifications_created": created}


@celery_app.task(name="app.jobs.tasks_reminders.send_follow_up_reminders")
def send_follow_up_reminders():
    return run_async(_send_follow_up_reminders)


@celery_app.task(name="app.jobs.tasks_reminders.send_maintenance_reminders")
def send_maintenance_reminders():
    return run_async(_send_maintenance_reminders)
