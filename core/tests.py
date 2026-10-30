from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CoreViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='demo', password='demo123')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_dashboard_renders_for_authenticated_user(self):
        self.client.login(username='demo', password='demo123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ERMS Dashboard')
        self.assertContains(response, 'Recent activity')
