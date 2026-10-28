from django.db import models
from django.conf import settings


class Notification(models.Model):
    class Type(models.TextChoices):
        OVERDUE = 'overdue'
        REASSIGNED = 'reassigned'
        STATUS_CHANGED = 'status_changed'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    task = models.ForeignKey(
        'projects.Task',
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=20, choices=Type.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type}: {self.message[:50]}"
