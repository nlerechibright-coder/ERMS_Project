from decimal import Decimal

from django.contrib import messages
from core.decorators import management_required
from django.shortcuts import redirect, render

from .models import Expense, ExpenseCategory, PaymentEntry


@management_required
def expense_list(request):
    expenses = Expense.objects.select_related('category', 'submitted_by', 'approved_by').order_by('-expense_date', '-id')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only authorized users can submit expenses.')
            return redirect('expense_list')
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Expense title is required.')
            return redirect('expense_list')
        category_id = request.POST.get('category')
        category = ExpenseCategory.objects.filter(pk=category_id).first() if category_id else None
        expense = Expense.objects.create(
            title=title,
            category=category,
            amount=request.POST.get('amount', '0'),
            description=request.POST.get('description', ''),
            submitted_by=request.user,
            status='PENDING',
        )
        messages.success(request, f'Expense {expense.title} submitted.')
        return redirect('expense_list')
    return render(request, 'finance/expense_list.html', {'expenses': expenses, 'categories': ExpenseCategory.objects.all()})


@management_required
def expense_category_list(request):
    categories = ExpenseCategory.objects.all().order_by('name')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can manage expense categories.')
            return redirect('expense_category_list')
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('expense_category_list')
        ExpenseCategory.objects.get_or_create(name=name)
        messages.success(request, 'Expense category saved.')
        return redirect('expense_category_list')
    return render(request, 'finance/expense_category_list.html', {'categories': categories})


@management_required
def expense_approve(request, expense_id):
    if request.method == 'POST':
        expense = Expense.objects.get(pk=expense_id)
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only authorized users can approve expenses.')
            return redirect('expense_list')
        expense.status = 'APPROVED'
        expense.approved_by = request.user
        expense.save(update_fields=['status', 'approved_by'])
        messages.success(request, 'Expense approved.')
    return redirect('expense_list')


@management_required
def expense_reject(request, expense_id):
    if request.method == 'POST':
        expense = Expense.objects.get(pk=expense_id)
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only authorized users can reject expenses.')
            return redirect('expense_list')
        expense.status = 'REJECTED'
        expense.save(update_fields=['status'])
        messages.success(request, 'Expense rejected.')
    return redirect('expense_list')


@management_required
def payment_entry_create(request, expense_id):
    expense = Expense.objects.get(pk=expense_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can record payments.')
            return redirect('expense_list')
        payment = Decimal(request.POST.get('amount', '0'))
        if payment <= 0:
            messages.error(request, 'Payment amount must be greater than zero.')
            return redirect('expense_list')
        PaymentEntry.objects.create(
            expense=expense,
            amount=payment,
            reference=request.POST.get('reference', ''),
            notes=request.POST.get('notes', ''),
        )
        if expense.status != 'PAID':
            expense.status = 'PAID'
            expense.payment_reference = request.POST.get('reference', '')
            expense.save(update_fields=['status', 'payment_reference'])
        messages.success(request, 'Payment entry recorded.')
    return redirect('expense_list')
