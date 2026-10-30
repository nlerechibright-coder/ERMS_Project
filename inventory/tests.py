from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from .models import Product, ProductCategory, StockMovement, StockReceipt, StockReceiptItem


class SeedCatalogueTests(TestCase):
    def test_seed_creates_and_is_idempotent(self):
        call_command('seed_supermarket_catalogue', verbosity=0)
        first_products = Product.objects.count()
        first_cats = ProductCategory.objects.count()
        call_command('seed_supermarket_catalogue', verbosity=0)
        self.assertEqual(Product.objects.count(), first_products)
        self.assertEqual(ProductCategory.objects.count(), first_cats)
        skus = list(Product.objects.values_list('sku', flat=True))
        self.assertEqual(len(skus), len(set(skus)))

    def test_seed_adds_no_stock(self):
        call_command('seed_supermarket_catalogue', verbosity=0)
        self.assertEqual(
            Product.objects.filter(is_sample_catalogue=True).exclude(current_stock=Decimal('0')).count(), 0
        )

    def test_seed_does_not_overwrite_edited_price_or_stock(self):
        call_command('seed_supermarket_catalogue', verbosity=0)
        p = Product.objects.filter(is_sample_catalogue=True).first()
        Product.objects.filter(pk=p.pk).update(unit_price=Decimal('650.00'), current_stock=Decimal('12.50'))
        call_command('seed_supermarket_catalogue', verbosity=0)
        p.refresh_from_db()
        self.assertEqual(p.unit_price, Decimal('650.00'))
        self.assertEqual(p.current_stock, Decimal('12.50'))


class ReceiptConversionTests(TestCase):
    def _product(self, uppu, stock_unit='pack', purchase_unit='carton', tag=''):
        cat, _ = ProductCategory.objects.get_or_create(name='Test')
        return Product.objects.create(
            name='Test ' + tag, sku='T-' + tag + '-' + str(uppu), category=cat,
            stock_unit=stock_unit, purchase_unit=purchase_unit,
            units_per_purchase_unit=Decimal(uppu), unit_price=Decimal('0'), current_stock=Decimal('0'),
        )

    def test_10_cartons_40_adds_400(self):
        p = self._product(40, tag='a')
        r = StockReceipt.objects.create(reference='GRN-TEST1')
        StockReceiptItem.objects.create(
            receipt=r, product=p, purchase_quantity=Decimal('10'), purchase_unit='carton',
            units_per_purchase_unit=Decimal('40'), cost_per_purchase_unit=Decimal('2000.00'),
        )
        r.confirm()
        p.refresh_from_db()
        self.assertEqual(p.current_stock, Decimal('400'))
        self.assertEqual(StockMovement.objects.filter(product=p, movement_type='IN', quantity=Decimal('400')).count(), 1)
        self.assertEqual(r.total_cost, Decimal('20000.00'))

    def test_receipt_not_double_processed(self):
        p = self._product(40, tag='b')
        r = StockReceipt.objects.create(reference='GRN-TEST2')
        StockReceiptItem.objects.create(
            receipt=r, product=p, purchase_quantity=Decimal('1'), purchase_unit='carton',
            units_per_purchase_unit=Decimal('40'), cost_per_purchase_unit=Decimal('2000.00'),
        )
        r.confirm()
        p.refresh_from_db()
        stock_after = p.current_stock
        with self.assertRaises(ValidationError):
            r.confirm()
        p.refresh_from_db()
        self.assertEqual(p.current_stock, stock_after)
        self.assertEqual(StockMovement.objects.filter(product=p).count(), 1)

    def test_moving_average_cost(self):
        p = self._product(40, tag='c')
        r1 = StockReceipt.objects.create(reference='GRN-MA1')
        StockReceiptItem.objects.create(
            receipt=r1, product=p, purchase_quantity=Decimal('10'), purchase_unit='carton',
            units_per_purchase_unit=Decimal('40'), cost_per_purchase_unit=Decimal('2000.00'),
        )
        r1.confirm()
        p.refresh_from_db()
        self.assertEqual(p.average_cost, Decimal('50.0000'))
        r2 = StockReceipt.objects.create(reference='GRN-MA2')
        StockReceiptItem.objects.create(
            receipt=r2, product=p, purchase_quantity=Decimal('10'), purchase_unit='carton',
            units_per_purchase_unit=Decimal('40'), cost_per_purchase_unit=Decimal('2200.00'),
        )
        r2.confirm()
        p.refresh_from_db()
        self.assertEqual(p.average_cost, Decimal('52.5000'))
        self.assertEqual(p.current_stock, Decimal('800'))

    def test_decimal_receipt_kg(self):
        p = self._product(1, stock_unit='kg', purchase_unit='kg', tag='d')
        r = StockReceipt.objects.create(reference='GRN-DEC1')
        StockReceiptItem.objects.create(
            receipt=r, product=p, purchase_quantity=Decimal('2.5'), purchase_unit='kg',
            units_per_purchase_unit=Decimal('1'), cost_per_purchase_unit=Decimal('100.00'),
        )
        r.confirm()
        p.refresh_from_db()
        self.assertEqual(p.current_stock, Decimal('2.5'))
        self.assertEqual(StockMovement.objects.get(product=p).quantity, Decimal('2.5'))

    def test_validate_no_negative(self):
        p = self._product(1, tag='e')
        with self.assertRaises(ValidationError):
            p.validate_stock_for_issue(Decimal('5'))
