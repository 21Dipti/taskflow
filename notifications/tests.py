from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, Task
from .models import Notification
from .tasks import notify_task_reassigned, notify_status_changed, check_overdue_tasks


class NotificationTaskTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass1234')
        self.user2 = User.objects.create_user(username='user2', password='pass1234')
        self.project = Project.objects.create(name='P1', owner=self.user1)

    def test_reassignment_creates_notification(self):
        task = Task.objects.create(
            title='T1', project=self.project, assignee=self.user1, status='todo'
        )
        notify_task_reassigned(task.id, self.user1.id, self.user2.id)
        notif = Notification.objects.get()
        self.assertEqual(notif.recipient, self.user2)
        self.assertEqual(notif.notification_type, 'reassigned')
        self.assertIn('T1', notif.message)

    def test_status_change_creates_notification_for_assignee(self):
        task = Task.objects.create(
            title='T1', project=self.project, assignee=self.user2, status='done'
        )
        notify_status_changed(task.id, 'todo', 'done')
        notif = Notification.objects.get()
        self.assertEqual(notif.recipient, self.user2)
        self.assertEqual(notif.notification_type, 'status_changed')
        self.assertIn('todo', notif.message)
        self.assertIn('done', notif.message)

    def test_status_change_notifies_owner_when_no_assignee(self):
        task = Task.objects.create(
            title='T1', project=self.project, assignee=None, status='done'
        )
        notify_status_changed(task.id, 'todo', 'done')
        notif = Notification.objects.get()
        self.assertEqual(notif.recipient, self.user1)

    def test_overdue_check_creates_notification(self):
        Task.objects.create(
            title='T1', project=self.project, assignee=self.user1,
            status='todo', due_date=date.today() - timedelta(days=1),
        )
        check_overdue_tasks()
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, 'overdue')
        self.assertEqual(notif.recipient, self.user1)

    def test_overdue_check_skips_done_tasks(self):
        Task.objects.create(
            title='T1', project=self.project, assignee=self.user1,
            status='done', due_date=date.today() - timedelta(days=1),
        )
        check_overdue_tasks()
        self.assertEqual(Notification.objects.count(), 0)

    def test_overdue_check_no_duplicate_notifications(self):
        Task.objects.create(
            title='T1', project=self.project, assignee=self.user1,
            status='todo', due_date=date.today() - timedelta(days=1),
        )
        check_overdue_tasks()
        check_overdue_tasks()
        self.assertEqual(Notification.objects.filter(notification_type='overdue').count(), 1)

    def test_overdue_notifies_owner_when_no_assignee(self):
        Task.objects.create(
            title='T1', project=self.project, assignee=None,
            status='todo', due_date=date.today() - timedelta(days=1),
        )
        check_overdue_tasks()
        notif = Notification.objects.get()
        self.assertEqual(notif.recipient, self.user1)


class NotificationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='user1', password='pass1234')
        self.user2 = User.objects.create_user(username='user2', password='pass1234')
        self.project = Project.objects.create(name='P1', owner=self.user1)
        self.task = Task.objects.create(title='T1', project=self.project, status='todo')
        self.client.force_authenticate(user=self.user1)

    def test_list_own_notifications_only(self):
        Notification.objects.create(
            recipient=self.user1, task=self.task,
            notification_type='status_changed', message='Test1',
        )
        Notification.objects.create(
            recipient=self.user2, task=self.task,
            notification_type='status_changed', message='Test2',
        )
        res = self.client.get('/api/notifications/')
        self.assertEqual(len(res.data['results']), 1)
        self.assertEqual(res.data['results'][0]['message'], 'Test1')

    def test_mark_notification_as_read(self):
        n = Notification.objects.create(
            recipient=self.user1, task=self.task,
            notification_type='status_changed', message='Test',
        )
        res = self.client.patch(f'/api/notifications/{n.id}/', {'is_read': True})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_cannot_read_other_users_notification(self):
        n = Notification.objects.create(
            recipient=self.user2, task=self.task,
            notification_type='status_changed', message='Test',
        )
        res = self.client.get(f'/api/notifications/{n.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access(self):
        self.client.force_authenticate(user=None)
        res = self.client.get('/api/notifications/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
