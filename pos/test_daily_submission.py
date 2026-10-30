from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from inventory.models import Product, ProductCategory, StockMovement

from .models import DailySalesSubmission, PosReceipt
from .services import compute_daily_summary
from .utils import business_today


class DailySalesSubmissionTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username="daily-manager",
            password="TestPass123!",
            is_staff=True,
        )
        UserProfile.objects.create(user=self.manager, role="manager")

        self.cashier = User.objects.create_user(
            username="daily-cashier",
            password="TestPass123!",
            is_staff=False,
        )
        UserProfile.objects.create(user=self.cashier, role="sales_staff")

        self.category = ProductCategory.objects.create(name="Noodles")
        self.product = Product.objects.create(
            name="Indomie Test",
            sku="DAILY-ND-1",
            category=self.category,
            stock_unit="pack",
            purchase_unit="carton",
            units_per_purchase_unit=Decimal("40"),
            unit_price=Decimal("650.00"),
            current_stock=Decimal("100.000"),
            average_cost=Decimal("500.0000"),
            cost_known=True,
        )

    def cashier_client(self):
        client = Client()
        client.login(username="daily-cashier", password="TestPass123!")
        return client

    def manager_client(self):
        client = Client()
        client.login(username="daily-manager", password="TestPass123!")
        return client

    def make_sale(self, client, quantity="2", key="daily-key-1"):
        client.post(reverse("pos_add_to_cart"), {
            "product_id": self.product.pk,
            "quantity": quantity,
            "sale_unit": "stock",
        })
        response = client.post(reverse("pos_complete_sale"), {
            "idempotency_key": key,
            "payment_method": "CASH",
            "amount_tendered": "10000",
        })
        self.assertEqual(response.status_code, 302)
        return PosReceipt.objects.get(staff_user=client.user if hasattr(client, "user") else self.cashier)

    def test_staff_daily_sales_page_renders(self):
        response = self.cashier_client().get(reverse("pos_daily_sales"))
        self.assertEqual(response.status_code, 200)

    def test_submit_without_sales_does_not_create_submission(self):
        response = self.cashier_client().post(reverse("pos_daily_sales_submit"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DailySalesSubmission.objects.count(), 0)

    def test_submit_creates_submission_and_links_receipt(self):
        client = self.cashier_client()
        receipt = self.make_sale(client, quantity="2", key="daily-submit-1")

        response = client.post(reverse("pos_daily_sales_submit"))
        self.assertEqual(response.status_code, 302)

        submission = DailySalesSubmission.objects.get(staff_user=self.cashier, business_date=business_today())
        self.assertEqual(submission.status, "SUBMITTED")
        self.assertEqual(submission.transaction_count, 1)
        self.assertEqual(submission.sales_total, Decimal("1300.00"))
        self.assertEqual(submission.item_quantity_total, Decimal("2.000"))
        self.assertTrue(submission.events.filter(action="SUBMITTED").exists())

        receipt.refresh_from_db()
        self.assertEqual(receipt.daily_submission, submission)

    def test_duplicate_submission_is_prevented(self):
        client = self.cashier_client()
        self.make_sale(client, quantity="1", key="daily-duplicate-1")

        client.post(reverse("pos_daily_sales_submit"))
        client.post(reverse("pos_daily_sales_submit"))

        self.assertEqual(DailySalesSubmission.objects.count(), 1)

    def test_category_totals_are_calculated(self):
        client = self.cashier_client()
        self.make_sale(client, quantity="3", key="daily-category-1")

        summary = compute_daily_summary(self.cashier, business_today())
        self.assertEqual(summary["by_category"][0]["category"], "Noodles")
        self.assertEqual(summary["by_category"][0]["quantity"], Decimal("3.000"))
        self.assertEqual(summary["by_category"][0]["amount"], Decimal("1950.00"))

    def test_manager_accept_does_not_change_stock(self):
        client = self.cashier_client()
        self.make_sale(client, quantity="2", key="daily-accept-1")
        client.post(reverse("pos_daily_sales_submit"))

        submission = DailySalesSubmission.objects.get(staff_user=self.cashier)
        self.product.refresh_from_db()
        stock_after_sale = self.product.current_stock
        self.assertEqual(stock_after_sale, Decimal('98.000'))


        response = self.manager_client().post(reverse("manager_daily_sales_accept", args=[submission.pk]))
        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(submission.status, "ACCEPTED")
        self.assertTrue(submission.events.filter(action="ACCEPTED").exists())
        self.assertEqual(self.product.current_stock, stock_after_sale)

    def test_manager_reject_then_staff_resubmit(self):
        client = self.cashier_client()
        self.make_sale(client, quantity="2", key="daily-reject-1")
        client.post(reverse("pos_daily_sales_submit"))

        submission = DailySalesSubmission.objects.get(staff_user=self.cashier)

        response = self.manager_client().post(reverse("manager_daily_sales_reject", args=[submission.pk]), {
            "reason": "Please check cash count.",
        })
        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.status, "REJECTED")
        self.assertEqual(submission.rejection_reason, "Please check cash count.")

        response = client.post(reverse("pos_daily_sales_submit"))
        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.status, "SUBMITTED")
        self.assertEqual(DailySalesSubmission.objects.count(), 1)
        self.assertTrue(submission.events.filter(action="RESUBMITTED").exists())
