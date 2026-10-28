import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def notify_task_reassigned(task_id, old_assignee_id, new_assignee_id):
    from projects.models import Task
    from notifications.models import Notification

    task = Task.objects.select_related('project').get(id=task_id)
    notification = Notification.objects.create(
        recipient_id=new_assignee_id,
        task=task,
        notification_type=Notification.Type.REASSIGNED,
        message=f'You have been assigned to task "{task.title}" in project "{task.project.name}".',
    )
    logger.info(f"[NOTIFICATION] Reassignment: {notification.message}")


@shared_task
def notify_status_changed(task_id, old_status, new_status):
    from projects.models import Task
    from notifications.models import Notification

    task = Task.objects.select_related('project').get(id=task_id)
    recipient_id = task.assignee_id or task.project.owner_id

    notification = Notification.objects.create(
        recipient_id=recipient_id,
        task=task,
        notification_type=Notification.Type.STATUS_CHANGED,
        message=f'Task "{task.title}" status changed from {old_status} to {new_status}.',
    )
    logger.info(f"[NOTIFICATION] Status change: {notification.message}")


@shared_task
def check_overdue_tasks():
    from projects.models import Task
    from notifications.models import Notification

    today = timezone.now().date()
    overdue_tasks = Task.objects.filter(
        due_date__lt=today,
        status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS],
    ).exclude(
        notifications__notification_type=Notification.Type.OVERDUE,
    ).select_related('project')

    for task in overdue_tasks:
        if task.assignee_id is None:
            recipient_id = task.project.owner_id
        else:
            recipient_id = task.assignee_id

        notification = Notification.objects.create(
            recipient=task.assignee or task.project.owner,
            task=task,
            notification_type=Notification.Type.OVERDUE,
            message=f'Task "{task.title}" in project "{task.project.name}" is overdue (due {task.due_date}).',
        )
        logger.info(f"[NOTIFICATION] Overdue: {notification.message}")
