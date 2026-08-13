from datetime import datetime, timedelta
from app.jobs.celery_app import celery_app
from app.jobs.async_helper import run_async


async def _check_low_stock():
    from app.models.inventory import InventoryItem
    from app.models.misc import Notification
    from app.models.enums import NotificationType

    items = await InventoryItem.find(InventoryItem.is_archived == False).to_list()  # noqa: E712
    low_stock = [i for i in items if i.is_low_stock]
    expiring_soon = [i for i in items if i.expiry_date and i.expiry_date <= datetime.utcnow() + timedelta(days=30)]

    created = 0
    for item in low_stock:
        await Notification(
            branch_id=item.branch_id, type=NotificationType.LOW_STOCK,
            title="Low stock alert",
            message=f"{item.name} is at {item.stock_qty} {item.unit} (reorder level {item.reorder_level})",
            link=f"/inventory/{item.id}",
        ).insert()
        created += 1

    for item in expiring_soon:
        await Notification(
            branch_id=item.branch_id, type=NotificationType.EXPIRING_INVENTORY,
            title="Inventory expiring soon",
            message=f"{item.name} expires on {item.expiry_date.strftime('%d-%b-%Y')}",
            link=f"/inventory/{item.id}",
        ).insert()
        created += 1

    return {"low_stock_alerts": len(low_stock), "expiry_alerts": len(expiring_soon), "notifications_created": created}


@celery_app.task(name="app.jobs.tasks_inventory.check_low_stock")
def check_low_stock():
    return run_async(_check_low_stock)
