import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


class ProductCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=60, unique=True)
    category = models.ForeignKey('ProductCategory', on_delete=models.PROTECT, related_name='products', null=True, blank=True)
    barcode = models.CharField(max_length=100, blank=True, default='')
    brand = models.CharField(max_length=120, blank=True, default='')
    stock_unit = models.CharField(max_length=20, default='pcs', help_text='Sellable unit, e.g. pack, bottle, kg, litre.')
    purchase_unit = models.CharField(max_length=20, default='unit', help_text='Buying unit, e.g. carton, bag, crate.')
    units_per_purchase_unit = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('1'), validators=[MinValueValidator(Decimal('0.001'))], help_text='How many stock units are in one purchase unit, e.g. 40 packs per carton.')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True)
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    average_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, help_text='Moving weighted-average cost per stock unit.')
    cost_known = models.BooleanField(default=False, help_text='True once a real purchase cost is recorded; profit is hidden while False.')
    is_sample_catalogue = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level

    def validate_stock_for_issue(self, quantity):
        if quantity < 0:
            raise ValidationError('Quantity must be positive.')
        if self.current_stock < quantity:
            raise ValidationError(f'{self.name} does not have enough stock to issue {quantity} units.')


class StockMovement(models.Model):
    MOVEMENT_TYPE_CHOICES = [
        ('IN', 'Receipt'),
        ('OUT', 'Issue'),
        ('ADJUSTMENT', 'Adjustment'),
    ]

    product = models.ForeignKey('Product', on_delete=models.PROTECT, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0, validators=[MinValueValidator(Decimal('0'))])
    reason = models.CharField(max_length=200)
    reference = models.CharField(max_length=100, blank=True)
    performed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_movements')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} {self.movement_type} {self.quantity}'


class StockReceipt(models.Model):
    reference = models.CharField(max_length=60, unique=True)
    supplier = models.ForeignKey('procurement.Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_receipts')
    receipt_date = models.DateField(default=datetime.date.today)
    received_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_receipts')
    notes = models.TextField(blank=True)
    invoice_reference = models.CharField(max_length=120, blank=True)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference

    def confirm(self, user=None):
        if self.is_processed:
            raise ValidationError('This goods receipt has already been processed.')
        with transaction.atomic():
            items = list(self.items.order_by('id'))
            if not items:
                raise ValidationError('A goods receipt must contain at least one item.')
            running_total = Decimal('0')
            for item in items:
                if item.is_processed:
                    continue
                if item.units_per_purchase_unit is None or item.units_per_purchase_unit <= 0:
                    raise ValidationError(f'Invalid conversion factor for {item.product.name}.')
                product = Product.objects.select_for_update().get(pk=item.product_id)
                sqr = (item.purchase_quantity * item.units_per_purchase_unit).quantize(Decimal('0.001'))
                cpu = (item.cost_per_purchase_unit / item.units_per_purchase_unit).quantize(Decimal('0.0001'))
                old_stock = product.current_stock or Decimal('0')
                old_avg = product.average_cost or Decimal('0')
                new_stock = old_stock + sqr
                denom = old_stock + sqr
                new_avg = cpu if denom == 0 else (((old_stock * old_avg) + (sqr * cpu)) / denom)
                product.current_stock = new_stock
                product.average_cost = new_avg.quantize(Decimal('0.0001'))
                if cpu > 0:
                    product.cost_known = True
                product.save(update_fields=['current_stock', 'average_cost', 'cost_known'])
                StockMovement.objects.create(
                    product=product, movement_type='IN', quantity=sqr,
                    reason='Goods receipt', reference=self.reference,
                    performed_by=user or self.received_by,
                )
                item.stock_quantity_received = sqr
                item.cost_per_stock_unit = cpu
                item.total_cost = (item.purchase_quantity * item.cost_per_purchase_unit).quantize(Decimal('0.01'))
                item.is_processed = True
                item.processed_at = timezone.now()
                item.save(update_fields=['stock_quantity_received', 'cost_per_stock_unit', 'total_cost', 'is_processed', 'processed_at'])
                running_total += item.total_cost
            self.total_cost = running_total.quantize(Decimal('0.01'))
            self.is_processed = True
            if user and not self.received_by:
                self.received_by = user
            self.save(update_fields=['total_cost', 'is_processed', 'received_by'])
        return self


class StockReceiptItem(models.Model):
    receipt = models.ForeignKey(StockReceipt, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.PROTECT, related_name='receipt_items')
    purchase_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    purchase_unit = models.CharField(max_length=20)
    units_per_purchase_unit = models.DecimalField(max_digits=12, decimal_places=3)
    stock_quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cost_per_purchase_unit = models.DecimalField(max_digits=12, decimal_places=2)
    cost_per_stock_unit = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.receipt.reference} - {self.product.name}'
