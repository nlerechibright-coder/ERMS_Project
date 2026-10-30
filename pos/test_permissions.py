from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile


class CashierManagementAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username="permission-manager",
            password="TestPass123!",
            is_staff=True,
        )
        UserProfile.objects.create(user=self.manager, role="manager")

        self.cashier = User.objects.create_user(
            username="permission-cashier",
            password="TestPass123!",
            is_staff=False,
        )
        UserProfile.objects.create(user=self.cashier, role="sales_staff")

    def cashier_client(self):
        client = Client()
        client.login(username="permission-cashier", password="TestPass123!")
        return client

    def manager_client(self):
        client = Client()
        client.login(username="permission-manager", password="TestPass123!")
        return client

    def test_cashier_cannot_access_inventory_products(self):
        response = self.cashier_client().get(reverse("product_list"))
        self.assertEqual(response.status_code, 302)

    def test_cashier_cannot_access_stock_receipts(self):
        response = self.cashier_client().get(reverse("stock_receipt_list"))
        self.assertEqual(response.status_code, 302)

    def test_cashier_cannot_access_stock_summary(self):
        response = self.cashier_client().get(reverse("stock_summary"))
        self.assertEqual(response.status_code, 302)

    def test_cashier_cannot_access_suppliers(self):
        response = self.cashier_client().get(reverse("supplier_list"))
        self.assertEqual(response.status_code, 302)

    def test_cashier_cannot_access_purchase_orders(self):
        response = self.cashier_client().get(reverse("purchase_order_list"))
        self.assertEqual(response.status_code, 302)

    def test_cashier_cannot_access_sales_orders(self):
        response = self.cashier_client().get(reverse("sales_order_list"))
        self.assertEqual(response.status_code, 302)

    def test_cashier_can_access_pos(self):
        response = self.cashier_client().get(reverse("pos_interface"))
        self.assertEqual(response.status_code, 200)

    def test_manager_can_access_staff_accounts(self):
        response = self.manager_client().get(reverse("staff_list"))
        self.assertEqual(response.status_code, 200)
