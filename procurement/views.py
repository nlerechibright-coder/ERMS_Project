from decimal import Decimal

from django.contrib import messages
from core.decorators import management_required
from django.db import models, transaction
from django.shortcuts import redirect, render

from inventory.models import Product, StockMovement
from .models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseOrderLineItem, Supplier


@management_required
def supplier_list(request):
    suppliers = Supplier.objects.order_by('name')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can manage suppliers.')
            return redirect('supplier_list')
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Supplier name is required.')
            return redirect('supplier_list')
        supplier, created = Supplier.objects.get_or_create(name=name)
        if created:
            supplier.contact_person = request.POST.get('contact_person', '')
            supplier.email = request.POST.get('email', '')
            supplier.phone = request.POST.get('phone', '')
            supplier.address = request.POST.get('address', '')
            supplier.save()
            messages.success(request, 'Supplier created.')
        else:
            messages.error(request, 'Supplier already exists.')
        return redirect('supplier_list')
    return render(request, 'procurement/supplier_list.html', {'suppliers': suppliers})


@management_required
def supplier_edit(request, supplier_id):
    supplier = Supplier.objects.get(pk=supplier_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can update suppliers.')
            return redirect('supplier_list')
        supplier.name = request.POST.get('name', supplier.name).strip()
        supplier.contact_person = request.POST.get('contact_person', '')
        supplier.email = request.POST.get('email', '')
        supplier.phone = request.POST.get('phone', '')
        supplier.address = request.POST.get('address', '')
        supplier.is_active = request.POST.get('is_active') == 'on'
        supplier.save()
        messages.success(request, 'Supplier updated.')
        return redirect('supplier_list')
    return render(request, 'procurement/supplier_form.html', {'supplier': supplier})


@management_required
def supplier_delete(request, supplier_id):
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can delete suppliers.')
            return redirect('supplier_list')
        supplier = Supplier.objects.get(pk=supplier_id)
        supplier.is_active = False
        supplier.save(update_fields=['is_active'])
        messages.success(request, 'Supplier deactivated.')
    return redirect('supplier_list')


@management_required
def purchase_order_list(request):
    purchase_orders = PurchaseOrder.objects.select_related('supplier').order_by('-order_date', '-id')
    return render(request, 'procurement/purchase_order_list.html', {'purchase_orders': purchase_orders})


@management_required
def purchase_order_create(request):
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only authorized users can create purchase orders.')
            return redirect('purchase_order_list')
        supplier_id = request.POST.get('supplier')
        supplier = Supplier.objects.filter(pk=supplier_id).first()
        if not supplier:
            messages.error(request, 'Supplier is required.')
            return redirect('purchase_order_list')
        order_number = request.POST.get('order_number', '').strip() or f'PO-{supplier.id}-{PurchaseOrder.objects.count() + 1}'
        order = PurchaseOrder.objects.create(
            supplier=supplier,
            order_number=order_number,
            status='DRAFT',
            submitted_by=request.user,
            notes=request.POST.get('notes', ''),
        )
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        prices = request.POST.getlist('unit_price')
        for idx, product_value in enumerate(product_ids):
            if not product_value:
                continue
            product = Product.objects.filter(pk=product_value).first()
            if not product:
                continue
            qty = int(quantities[idx] or 0)
            price = Decimal(prices[idx] or '0')
            if qty > 0:
                PurchaseOrderLineItem.objects.create(
                    purchase_order=order,
                    product=product,
                    quantity=qty,
                    unit_price=price,
                )
        order.recalculate_total()
        messages.success(request, 'Purchase order draft created.')
        return redirect('purchase_order_list')
    return render(request, 'procurement/purchase_order_form.html', {'suppliers': Supplier.objects.filter(is_active=True), 'products': Product.objects.filter(is_active=True)})


@management_required
def purchase_order_edit(request, order_id):
    order = PurchaseOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only authorized users can edit purchase orders.')
            return redirect('purchase_order_list')
        order.notes = request.POST.get('notes', '')
        order.save(update_fields=['notes'])
        order.line_items.all().delete()
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        prices = request.POST.getlist('unit_price')
        for idx, product_value in enumerate(product_ids):
            if not product_value:
                continue
            product = Product.objects.filter(pk=product_value).first()
            if not product:
                continue
            qty = int(quantities[idx] or 0)
            price = Decimal(prices[idx] or '0')
            if qty > 0:
                PurchaseOrderLineItem.objects.create(purchase_order=order, product=product, quantity=qty, unit_price=price)
        order.recalculate_total()
        messages.success(request, 'Purchase order updated.')
        return redirect('purchase_order_list')
    return render(request, 'procurement/purchase_order_form.html', {'order': order, 'suppliers': Supplier.objects.filter(is_active=True), 'products': Product.objects.filter(is_active=True)})


@management_required
def purchase_order_submit(request, order_id):
    order = PurchaseOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'You are not allowed to submit purchase orders.')
            return redirect('purchase_order_list')
        if not order.line_items.exists():
            messages.error(request, 'A purchase order must include at least one line item.')
            return redirect('purchase_order_list')
        order.status = 'SUBMITTED'
        order.submitted_by = request.user
        order.save(update_fields=['status', 'submitted_by'])
        messages.success(request, 'Purchase order submitted for approval.')
    return redirect('purchase_order_list')


@management_required
def purchase_order_approve(request, order_id):
    order = PurchaseOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only authorized users can approve purchase orders.')
            return redirect('purchase_order_list')
        if order.status not in ['SUBMITTED', 'DRAFT']:
            messages.error(request, 'Only submitted or draft orders can be approved.')
            return redirect('purchase_order_list')
        order.status = 'APPROVED'
        order.approved_by = request.user
        order.save(update_fields=['status', 'approved_by'])
        messages.success(request, 'Purchase order approved.')
    return redirect('purchase_order_list')


@management_required
def purchase_order_reject(request, order_id):
    order = PurchaseOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only authorized users can reject purchase orders.')
            return redirect('purchase_order_list')
        order.status = 'REJECTED'
        order.save(update_fields=['status'])
        messages.success(request, 'Purchase order rejected.')
    return redirect('purchase_order_list')


@management_required
def goods_receipt_create(request, order_id):
    order = PurchaseOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can receive goods.')
            return redirect('purchase_order_list')
        if order.status not in ['APPROVED', 'PARTIALLY_RECEIVED']:
            messages.error(request, 'Goods can only be received for approved orders.')
            return redirect('purchase_order_list')
        with transaction.atomic():
            receipt = GoodsReceipt.objects.create(
                purchase_order=order,
                receipt_number=f'GR-{order.order_number}-{GoodsReceipt.objects.count() + 1}',
                received_by=request.user,
            )
            for line in order.line_items.all():
                received_value = request.POST.get(f'received_{line.pk}', '0')
                qty = int(received_value or 0)
                if qty <= 0:
                    continue
                if qty > line.outstanding_quantity:
                    raise ValueError(f'{line.product.name} exceeds the outstanding quantity.')
                GoodsReceiptLine.objects.create(receipt=receipt, line_item=line, quantity_received=qty)
                line.received_quantity += qty
                line.save(update_fields=['received_quantity'])
                product = line.product
                product.current_stock += qty
                product.save(update_fields=['current_stock'])
                StockMovement.objects.create(
                    product=product,
                    movement_type='IN',
                    quantity=qty,
                    reason='Goods receipt',
                    reference=receipt.receipt_number,
                    performed_by=request.user,
                )
            if order.line_items.filter(received_quantity__gte=models.F('quantity')).exists():
                order.status = 'RECEIVED'
            else:
                order.status = 'PARTIALLY_RECEIVED'
            order.save(update_fields=['status'])
        messages.success(request, 'Goods received and inventory updated.')
        return redirect('purchase_order_list')
    return render(request, 'procurement/goods_receipt_form.html', {'order': order})
