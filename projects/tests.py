from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from .models import Project, Task


class ProjectTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='user1', password='pass1234')
        self.user2 = User.objects.create_user(username='user2', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def test_create_project(self):
        res = self.client.post('/api/projects/', {'name': 'My Project', 'description': 'Test'})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], 'My Project')
        self.assertEqual(res.data['owner'], self.user.id)

    def test_list_own_projects_only(self):
        Project.objects.create(name='P1', owner=self.user)
        Project.objects.create(name='P2', owner=self.user2)
        res = self.client.get('/api/projects/')
        names = [p['name'] for p in res.data['results']]
        self.assertIn('P1', names)
        self.assertNotIn('P2', names)

    def test_cannot_access_other_users_project(self):
        p = Project.objects.create(name='P2', owner=self.user2)
        res = self.client.get(f'/api/projects/{p.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_users_project(self):
        p = Project.objects.create(name='P2', owner=self.user2)
        res = self.client.put(f'/api/projects/{p.id}/', {'name': 'Hacked'})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_users_project(self):
        p = Project.objects.create(name='P2', owner=self.user2)
        res = self.client.delete(f'/api/projects/{p.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Project.objects.filter(id=p.id).exists())

    def test_update_own_project(self):
        p = Project.objects.create(name='P1', owner=self.user)
        res = self.client.put(f'/api/projects/{p.id}/', {'name': 'Updated', 'description': 'New'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['name'], 'Updated')

    def test_delete_own_project(self):
        p = Project.objects.create(name='P1', owner=self.user)
        res = self.client.delete(f'/api/projects/{p.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(id=p.id).exists())

    def test_unauthenticated_access(self):
        self.client.force_authenticate(user=None)
        res = self.client.get('/api/projects/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class TaskTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='user1', password='pass1234')
        self.user2 = User.objects.create_user(username='user2', password='pass1234')
        self.client.force_authenticate(user=self.user)
        self.project = Project.objects.create(name='P1', owner=self.user)
        self.project2 = Project.objects.create(name='P2', owner=self.user2)
        cache.clear()

    def test_create_task(self):
        res = self.client.post('/api/tasks/', {
            'title': 'Task 1',
            'project': self.project.id,
            'status': 'todo',
            'due_date': '2026-12-01',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], 'Task 1')

    def test_create_task_with_assignee(self):
        res = self.client.post('/api/tasks/', {
            'title': 'Task 1',
            'project': self.project.id,
            'assignee': self.user2.id,
            'status': 'todo',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['assignee'], self.user2.id)

    def test_cannot_create_task_in_other_users_project(self):
        res = self.client.post('/api/tasks/', {
            'title': 'Task 1',
            'project': self.project2.id,
            'status': 'todo',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_see_other_users_tasks(self):
        Task.objects.create(title='T2', project=self.project2, status='todo')
        res = self.client.get('/api/tasks/')
        titles = [t['title'] for t in res.data['results']]
        self.assertNotIn('T2', titles)

    def test_filter_by_status(self):
        Task.objects.create(title='T1', project=self.project, status='todo')
        Task.objects.create(title='T2', project=self.project, status='done')
        res = self.client.get('/api/tasks/?status=todo')
        titles = [t['title'] for t in res.data['results']]
        self.assertIn('T1', titles)
        self.assertNotIn('T2', titles)

    def test_filter_by_assignee(self):
        Task.objects.create(title='T1', project=self.project, assignee=self.user, status='todo')
        Task.objects.create(title='T2', project=self.project, assignee=self.user2, status='todo')
        res = self.client.get(f'/api/tasks/?assignee={self.user.id}')
        titles = [t['title'] for t in res.data['results']]
        self.assertIn('T1', titles)
        self.assertNotIn('T2', titles)

    def test_filter_by_due_date_range(self):
        Task.objects.create(title='T1', project=self.project, status='todo', due_date='2026-06-01')
        Task.objects.create(title='T2', project=self.project, status='todo', due_date='2026-12-01')
        res = self.client.get('/api/tasks/?due_date_from=2026-01-01&due_date_to=2026-07-01')
        titles = [t['title'] for t in res.data['results']]
        self.assertIn('T1', titles)
        self.assertNotIn('T2', titles)

    def test_pagination(self):
        for i in range(15):
            Task.objects.create(title=f'T{i}', project=self.project, status='todo')
        res = self.client.get('/api/tasks/')
        self.assertEqual(len(res.data['results']), 10)
        self.assertIsNotNone(res.data['next'])

    @patch('notifications.tasks.notify_status_changed.delay')
    def test_status_change_triggers_notification(self, mock_notify):
        task = Task.objects.create(
            title='T1', project=self.project, status='todo', assignee=self.user
        )
        res = self.client.put(f'/api/tasks/{task.id}/', {
            'title': 'T1',
            'project': self.project.id,
            'status': 'done',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_notify.assert_called_once_with(task.id, 'todo', 'done')

    @patch('notifications.tasks.notify_task_reassigned.delay')
    def test_reassignment_triggers_notification(self, mock_notify):
        task = Task.objects.create(
            title='T1', project=self.project, status='todo', assignee=self.user
        )
        res = self.client.put(f'/api/tasks/{task.id}/', {
            'title': 'T1',
            'project': self.project.id,
            'assignee': self.user2.id,
            'status': 'todo',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_notify.assert_called_once_with(task.id, self.user.id, self.user2.id)


class TaskCacheTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='user1', password='pass1234')
        self.client.force_authenticate(user=self.user)
        self.project = Project.objects.create(name='P1', owner=self.user)
        cache.clear()

    def test_task_list_is_cached(self):
        Task.objects.create(title='T1', project=self.project, status='todo')
        res1 = self.client.get('/api/tasks/')
        self.assertEqual(len(res1.data['results']), 1)

        Task.objects.create(title='T2', project=self.project, status='todo')
        res2 = self.client.get('/api/tasks/')
        self.assertEqual(len(res2.data['results']), 1)

    @patch('notifications.tasks.notify_status_changed.delay')
    def test_cache_invalidated_on_update(self, mock_notify):
        task = Task.objects.create(title='T1', project=self.project, status='todo')
        self.client.get('/api/tasks/')

        self.client.put(f'/api/tasks/{task.id}/', {
            'title': 'T1',
            'project': self.project.id,
            'status': 'done',
        })

        Task.objects.create(title='T2', project=self.project, status='todo')
        res = self.client.get('/api/tasks/')
        self.assertEqual(len(res.data['results']), 2)

    def test_cache_invalidated_on_create(self):
        Task.objects.create(title='T1', project=self.project, status='todo')
        self.client.get('/api/tasks/')

        self.client.post('/api/tasks/', {
            'title': 'T2',
            'project': self.project.id,
            'status': 'todo',
        })

        res = self.client.get('/api/tasks/')
        self.assertEqual(len(res.data['results']), 2)

    def test_cache_invalidated_on_delete(self):
        t1 = Task.objects.create(title='T1', project=self.project, status='todo')
        Task.objects.create(title='T2', project=self.project, status='todo')
        self.client.get('/api/tasks/')

        self.client.delete(f'/api/tasks/{t1.id}/')
        res = self.client.get('/api/tasks/')
        self.assertEqual(len(res.data['results']), 1)
