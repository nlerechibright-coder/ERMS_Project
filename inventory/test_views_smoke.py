from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Product, ProductCategory, StockMovement, StockReceipt


class InventoryViewSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(
            username='phase1-manager',
            password='TestPass123!',
            is_staff=True,
        )
        self.client = Client()
        self.client.login(username='phase1-manager', password='TestPass123!')

    def test_inventory_get_pages_render(self):
        names = [
            'product_list',
            'product_category_list',
            'stock_movement_list',
            'stock_movement_create',
            'stock_receipt_list',
            'stock_receipt_create',
            'stock_summary',
        ]
        for name in names:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, msg=name)

    def test_product_edit_page_renders(self):
        cat = ProductCategory.objects.create(name='Smoke Cat')
        product = Product.objects.create(
            name='Smoke Product',
            sku='SMOKE-1',
            category=cat,
            stock_unit='pack',
            purchase_unit='carton',
            units_per_purchase_unit=40,
        )
        response = self.client.get(reverse('product_edit', args=[product.pk]))
        self.assertEqual(response.status_code, 200)

    def test_product_create_post_sets_zero_stock_when_omitted(self):
        response = self.client.post(reverse('product_list'), {
            'name': 'UI Product',
            'sku': 'UI-1',
            'stock_unit': 'pack',
            'purchase_unit': 'carton',
            'units_per_purchase_unit': '40',
            'unit_price': '650',
            'wholesale_price': '0',
            'reorder_level': '10',
        })
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(sku='UI-1')
        self.assertEqual(product.current_stock, 0)

    def test_stock_receipt_post_updates_stock_once(self):
        cat = ProductCategory.objects.create(name='Receipt Cat')
        product = Product.objects.create(
            name='Indomie',
            sku='UI-ND-1',
            category=cat,
            stock_unit='pack',
            purchase_unit='carton',
            units_per_purchase_unit=40,
        )
        response = self.client.post(reverse('stock_receipt_create'), {
            'product': [str(product.pk)],
            'purchase_quantity': ['10'],
            'cost_per_purchase_unit': ['2000'],
            'receipt_date': '2026-01-01',
            'notes': 'smoke',
            'invoice_reference': 'INV-1',
        })
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.current_stock, 400)
        self.assertEqual(
            StockMovement.objects.filter(product=product, movement_type='IN', reference__startswith='GRN-').count(),
            1,
        )
        receipt = StockReceipt.objects.get(items__product=product)
        self.assertTrue(receipt.is_processed)
