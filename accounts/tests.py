from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_success(self):
        res = self.client.post('/api/auth/signup/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'strongpass123',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', res.data)
        self.assertNotIn('password', res.data)

    def test_signup_short_password(self):
        res = self.client.post('/api/auth/signup/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'short',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_duplicate_username(self):
        self.client.post('/api/auth/signup/', {
            'username': 'existing',
            'email': 'a@example.com',
            'password': 'strongpass123',
        })
        res = self.client.post('/api/auth/signup/', {
            'username': 'existing',
            'email': 'b@example.com',
            'password': 'strongpass123',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        User.objects.create_user(username='testuser', password='testpass123')
        res = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)

    def test_login_wrong_password(self):
        User.objects.create_user(username='testuser', password='testpass123')
        res = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpass',
        })
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        User.objects.create_user(username='testuser', password='testpass123')
        login = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        res = self.client.post('/api/auth/token/refresh/', {
            'refresh': login.data['refresh'],
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)

    def test_password_not_in_response(self):
        res = self.client.post('/api/auth/signup/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'strongpass123',
        })
        self.assertNotIn('password', res.data)
        user = User.objects.get(username='newuser')
        self.assertTrue(user.check_password('strongpass123'))
        self.assertNotEqual(user.password, 'strongpass123')

    def test_user_list_requires_auth(self):
        res = self.client.get('/api/auth/users/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_list_authenticated(self):
        user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.force_authenticate(user=user)
        res = self.client.get('/api/auth/users/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
