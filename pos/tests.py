from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from inventory.models import Product, ProductCategory, StockMovement

from .models import PosReceipt


class PosTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="pos-manager", password="TestPass123!", is_staff=True)
        UserProfile.objects.create(user=self.manager, role="manager")

        self.cashier = User.objects.create_user(username="pos-cashier", password="TestPass123!", is_staff=False)
        UserProfile.objects.create(user=self.cashier, role="sales_staff")

        cat = ProductCategory.objects.create(name="Test Cat")
        self.product = Product.objects.create(
            name="Indomie Test",
            sku="POS-ND-1",
            category=cat,
            stock_unit="pack",
            purchase_unit="carton",
            units_per_purchase_unit=Decimal("40"),
            unit_price=Decimal("650.00"),
            current_stock=Decimal("100.000"),
            average_cost=Decimal("500.0000"),
            cost_known=True,
        )

    def _cashier_client(self):
        c = Client()
        c.login(username="pos-cashier", password="TestPass123!")
        return c

    def _manager_client(self):
        c = Client()
        c.login(username="pos-manager", password="TestPass123!")
        return c

    def test_cashier_cannot_access_management_page(self):
        response = self._cashier_client().get(reverse("product_list"))
        self.assertEqual(response.status_code, 302)

    def test_manager_can_access_staff_page(self):
        response = self._manager_client().get(reverse("staff_list"))
        self.assertEqual(response.status_code, 200)

    def test_manager_can_create_sales_staff_account(self):
        response = self._manager_client().post(reverse("staff_create"), {
            "username": "newcashier",
            "password": "Cashier123!",
            "first_name": "New",
            "last_name": "Cashier",
            "email": "new@example.com",
            "phone": "080",
            "department": "Till",
            "role": "sales_staff",
        })
        self.assertEqual(response.status_code, 302)
        User = get_user_model()
        user = User.objects.get(username="newcashier")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.profile.role, "sales_staff")

    def test_pos_interface_renders_for_cashier(self):
        response = self._cashier_client().get(reverse("pos_interface"))
        self.assertEqual(response.status_code, 200)

    def test_unpriced_product_is_not_offered_for_sale(self):
        cat = ProductCategory.objects.create(name="Unpriced")
        Product.objects.create(
            name="No Price Product",
            sku="NP-1",
            category=cat,
            stock_unit="pack",
            purchase_unit="carton",
            units_per_purchase_unit=Decimal("10"),
            unit_price=Decimal("0"),
            current_stock=Decimal("10"),
        )
        response = self._cashier_client().get(reverse("pos_interface"), {"q": "No Price"})
        self.assertEqual(response.status_code, 200)
        skus = [p.sku for p in response.context["results"]]
        self.assertNotIn("NP-1", skus)

    def test_sale_deducts_stock_once_and_creates_movement(self):
        client = self._cashier_client()
        add = client.post(reverse("pos_add_to_cart"), {
            "product_id": self.product.pk,
            "quantity": "5",
            "sale_unit": "stock",
        })
        self.assertEqual(add.status_code, 302)

        response = client.post(reverse("pos_complete_sale"), {
            "idempotency_key": "unique-key-1",
            "payment_method": "CASH",
            "amount_tendered": "5000",
        })
        self.assertEqual(response.status_code, 302)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("95.000"))
        self.assertEqual(PosReceipt.objects.count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(product=self.product, movement_type="OUT", quantity=Decimal("5.000")).count(),
            1,
        )

        receipt = PosReceipt.objects.get(idempotency_key="unique-key-1")
        self.assertEqual(receipt.grand_total, Decimal("3250.00"))
        self.assertEqual(receipt.change_due, Decimal("1750.00"))

    def test_duplicate_idempotency_key_does_not_create_second_sale(self):
        client = self._cashier_client()
        client.post(reverse("pos_add_to_cart"), {
            "product_id": self.product.pk,
            "quantity": "5",
            "sale_unit": "stock",
        })

        first = client.post(reverse("pos_complete_sale"), {
            "idempotency_key": "duplicate-key",
            "payment_method": "CASH",
            "amount_tendered": "5000",
        })
        self.assertEqual(first.status_code, 302)

        second = client.post(reverse("pos_complete_sale"), {
            "idempotency_key": "duplicate-key",
            "payment_method": "CASH",
            "amount_tendered": "5000",
        })
        self.assertEqual(second.status_code, 302)

        self.assertEqual(PosReceipt.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("95.000"))

    def test_sale_cannot_reduce_stock_below_zero(self):
        client = self._cashier_client()
        client.post(reverse("pos_add_to_cart"), {
            "product_id": self.product.pk,
            "quantity": "1000",
            "sale_unit": "stock",
        })

        response = client.post(reverse("pos_complete_sale"), {
            "idempotency_key": "too-much-key",
            "payment_method": "CASH",
            "amount_tendered": "1000000",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PosReceipt.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("100.000"))
