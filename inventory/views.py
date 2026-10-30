import datetime
import uuid
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from core.decorators import management_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render

from procurement.models import Supplier

from .models import Product, ProductCategory, StockMovement, StockReceipt, StockReceiptItem


def _dec(value, default='0'):
    try:
        return Decimal(str(value).strip() or default)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def _parse_date(value):
    if not value:
        return datetime.date.today()
    try:
        return datetime.datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return datetime.date.today()


@management_required
def product_category_list(request):
    categories = ProductCategory.objects.all().order_by('name')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can manage product categories.')
            return redirect('product_category_list')
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('product_category_list')
        category, created = ProductCategory.objects.get_or_create(name=name)
        if created:
            category.description = request.POST.get('description', '')
            category.save()
            messages.success(request, 'Category created.')
        else:
            messages.error(request, 'Category already exists.')
        return redirect('product_category_list')
    return render(request, 'inventory/product_category_list.html', {'categories': categories})


@management_required
def product_list(request):
    products = Product.objects.select_related('category').order_by('name')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can create products.')
            return redirect('product_list')
        name = request.POST.get('name', '').strip()
        sku = request.POST.get('sku', '').strip()
        if not name or not sku:
            messages.error(request, 'Product name and SKU are required.')
            return redirect('product_list')
        if Product.objects.filter(sku=sku).exists():
            messages.error(request, 'A product with that SKU already exists.')
            return redirect('product_list')
        uppu = _dec(request.POST.get('units_per_purchase_unit', '1'), '1')
        if uppu <= 0:
            messages.error(request, 'Units per purchase unit must be greater than zero.')
            return redirect('product_list')
        category_id = request.POST.get('category')
        category = ProductCategory.objects.filter(pk=category_id).first() if category_id else None
        product = Product.objects.create(
            name=name,
            sku=sku,
            category=category,
            barcode=request.POST.get('barcode', '').strip(),
            brand=request.POST.get('brand', '').strip(),
            stock_unit=(request.POST.get('stock_unit', '').strip() or 'pcs'),
            purchase_unit=(request.POST.get('purchase_unit', '').strip() or 'unit'),
            units_per_purchase_unit=uppu,
            unit_price=_dec(request.POST.get('unit_price', '0')),
            wholesale_price=_dec(request.POST.get('wholesale_price', '0')),
            current_stock=_dec(request.POST.get('current_stock', '0')),
            reorder_level=_dec(request.POST.get('reorder_level', '0')),
            description=request.POST.get('description', ''),
            is_active=True,
        )
        messages.success(request, f'Product {product.name} created.')
        return redirect('product_list')
    return render(request, 'inventory/product_list.html', {'products': products, 'categories': ProductCategory.objects.all()})


@management_required
def product_edit(request, product_id):
    product = Product.objects.get(pk=product_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can edit products.')
            return redirect('product_list')
        sku = request.POST.get('sku', '').strip()
        if not sku:
            messages.error(request, 'SKU is required.')
            return render(request, 'inventory/product_form.html', {'product': product, 'categories': ProductCategory.objects.all()})
        duplicate = Product.objects.filter(sku=sku).exclude(pk=product.pk).exists()
        if duplicate:
            messages.error(request, 'A product with that SKU already exists.')
            return render(request, 'inventory/product_form.html', {'product': product, 'categories': ProductCategory.objects.all()})
        uppu = _dec(request.POST.get('units_per_purchase_unit', product.units_per_purchase_unit), '1')
        if uppu <= 0:
            messages.error(request, 'Units per purchase unit must be greater than zero.')
            return render(request, 'inventory/product_form.html', {'product': product, 'categories': ProductCategory.objects.all()})
        category_id = request.POST.get('category')
        product.category = ProductCategory.objects.filter(pk=category_id).first() if category_id else None
        product.name = request.POST.get('name', '').strip() or product.name
        product.sku = sku
        product.barcode = request.POST.get('barcode', '').strip()
        product.brand = request.POST.get('brand', '').strip()
        product.stock_unit = (request.POST.get('stock_unit', '').strip() or product.stock_unit)
        product.purchase_unit = (request.POST.get('purchase_unit', '').strip() or product.purchase_unit)
        product.units_per_purchase_unit = uppu
        product.unit_price = _dec(request.POST.get('unit_price', product.unit_price))
        product.wholesale_price = _dec(request.POST.get('wholesale_price', product.wholesale_price))
        product.reorder_level = _dec(request.POST.get('reorder_level', product.reorder_level))
        product.average_cost = _dec(request.POST.get('average_cost', product.average_cost))
        product.cost_known = request.POST.get('cost_known') == 'on' or (product.average_cost or Decimal('0')) > 0
        product.description = request.POST.get('description', '')
        product.is_active = request.POST.get('is_active') == 'on'
        product.save()
        messages.success(request, 'Product updated.')
        return redirect('product_list')
    return render(request, 'inventory/product_form.html', {'product': product, 'categories': ProductCategory.objects.all()})


@management_required
def product_deactivate(request, product_id):
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can deactivate products.')
            return redirect('product_list')
        product = Product.objects.get(pk=product_id)
        product.is_active = False
        product.save(update_fields=['is_active'])
        messages.success(request, 'Product deactivated.')
    return redirect('product_list')


@management_required
def stock_movement_list(request):
    movements = StockMovement.objects.select_related('product', 'performed_by').order_by('-created_at')
    return render(request, 'inventory/stock_movement_list.html', {'movements': movements})


@management_required
def stock_movement_create(request):
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can record stock movements.')
            return redirect('stock_movement_list')
        product_id = request.POST.get('product')
        product = Product.objects.filter(pk=product_id).first()
        quantity = _dec(request.POST.get('quantity', '0'))
        movement_type = request.POST.get('movement_type', '').upper()
        if not product or quantity <= 0 or movement_type not in ['IN', 'OUT', 'ADJUSTMENT']:
            messages.error(request, 'Valid product, quantity, and movement type are required.')
            return redirect('stock_movement_list')
        try:
            with transaction.atomic():
                if movement_type == 'OUT':
                    product.validate_stock_for_issue(quantity)
                    product.current_stock -= quantity
                elif movement_type == 'IN':
                    product.current_stock += quantity
                else:
                    adjustment = _dec(request.POST.get('adjustment_value', '0'))
                    if adjustment == 0:
                        raise ValidationError('Adjustment value is required for stock adjustments.')
                    product.current_stock += adjustment
                    if product.current_stock < 0:
                        raise ValidationError('Stock adjustment cannot result in negative inventory.')
                product.save(update_fields=['current_stock'])
                StockMovement.objects.create(
                    product=product,
                    movement_type=movement_type,
                    quantity=quantity,
                    reason=request.POST.get('reason', 'Manual stock movement').strip() or 'Manual stock movement',
                    reference=request.POST.get('reference', '').strip(),
                    performed_by=request.user,
                )
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect('stock_movement_list')
        messages.success(request, 'Stock movement recorded.')
        return redirect('stock_movement_list')
    return render(request, 'inventory/stock_movement_form.html', {'products': Product.objects.filter(is_active=True)})


@management_required
def stock_receipt_list(request):
    receipts = StockReceipt.objects.select_related('supplier', 'received_by').prefetch_related('items__product').order_by('-created_at')
    return render(request, 'inventory/stock_receipt_list.html', {'receipts': receipts})


@management_required
def stock_receipt_create(request):
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can receive goods.')
            return redirect('stock_receipt_create')
        product_ids = request.POST.getlist('product')
        pqs = request.POST.getlist('purchase_quantity')
        costs = request.POST.getlist('cost_per_purchase_unit')
        lines = []
        for i, pid in enumerate(product_ids):
            if not pid:
                continue
            pq_raw = (pqs[i] if i < len(pqs) else '').strip()
            cost_raw = (costs[i] if i < len(costs) else '').strip()
            if not pq_raw or not cost_raw:
                continue
            try:
                pq = Decimal(pq_raw)
                cost = Decimal(cost_raw)
            except InvalidOperation:
                messages.error(request, 'Purchase quantity and cost must be valid numbers.')
                return redirect('stock_receipt_create')
            if pq <= 0 or cost < 0:
                messages.error(request, 'Purchase quantity must be greater than zero and cost cannot be negative.')
                return redirect('stock_receipt_create')
            product = Product.objects.filter(pk=pid, is_active=True).first()
            if not product:
                messages.error(request, 'One of the selected products is invalid or inactive.')
                return redirect('stock_receipt_create')
            uppu = product.units_per_purchase_unit or Decimal('1')
            if uppu <= 0:
                messages.error(request, f'{product.name} has an invalid purchase conversion factor.')
                return redirect('stock_receipt_create')
            sqr = (pq * uppu).quantize(Decimal('0.001'))
            cpu = (cost / uppu).quantize(Decimal('0.0001'))
            total = (pq * cost).quantize(Decimal('0.01'))
            lines.append((product, pq, uppu, sqr, cost, cpu, total))
        if not lines:
            messages.error(request, 'Add at least one product line with quantity and cost.')
            return redirect('stock_receipt_create')
        supplier_id = request.POST.get('supplier')
        supplier = Supplier.objects.filter(pk=supplier_id).first() if supplier_id else None
        try:
            with transaction.atomic():
                receipt = StockReceipt.objects.create(
                    reference='GRN-' + uuid.uuid4().hex[:10].upper(),
                    supplier=supplier,
                    receipt_date=_parse_date(request.POST.get('receipt_date')),
                    notes=request.POST.get('notes', '').strip(),
                    invoice_reference=request.POST.get('invoice_reference', '').strip(),
                    received_by=request.user,
                )
                for (product, pq, uppu, sqr, cost, cpu, total) in lines:
                    StockReceiptItem.objects.create(
                        receipt=receipt, product=product,
                        purchase_quantity=pq, purchase_unit=product.purchase_unit or 'unit',
                        units_per_purchase_unit=uppu, stock_quantity_received=sqr,
                        cost_per_purchase_unit=cost, cost_per_stock_unit=cpu, total_cost=total,
                    )
                receipt.confirm(user=request.user)
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect('stock_receipt_create')
        messages.success(request, f'Goods receipt {receipt.reference} recorded; stock updated.')
        return redirect('stock_receipt_list')
    suppliers = Supplier.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True).select_related('category').order_by('name')
    return render(request, 'inventory/stock_receipt_form.html', {'suppliers': suppliers, 'products': products})


@management_required
def stock_receipt_confirm(request, receipt_id):
    if request.method != 'POST':
        return redirect('stock_receipt_list')
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'Only managers can process goods receipts.')
        return redirect('stock_receipt_list')
    receipt = StockReceipt.objects.get(pk=receipt_id)
    try:
        receipt.confirm(user=request.user)
        messages.success(request, f'Goods receipt {receipt.reference} processed.')
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('stock_receipt_list')


@management_required
def stock_summary(request):
    products = Product.objects.select_related('category').order_by('name')
    total_units = Decimal('0')
    stock_value = Decimal('0')
    low = 0
    unknown_cost = 0
    for p in products:
        cs = p.current_stock or Decimal('0')
        total_units += cs
        if p.cost_known and (p.average_cost or Decimal('0')) > 0:
            stock_value += cs * p.average_cost
        else:
            unknown_cost += 1
        if p.is_low_stock:
            low += 1
    return render(request, 'inventory/stock_summary.html', {
        'products': products,
        'total_units': total_units,
        'stock_value': stock_value.quantize(Decimal('0.01')),
        'low_stock_count': low,
        'unknown_cost_count': unknown_cost,
    })
