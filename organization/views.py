from django.contrib import messages
from core.decorators import management_required
from django.db.models import Q
from django.shortcuts import redirect, render

from .models import Department, Employee


@management_required
def department_list(request):
    departments = Department.objects.all().order_by('name')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can create departments.')
            return redirect('department_list')
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Department name is required.')
        else:
            dept, created = Department.objects.get_or_create(name=name)
            if created:
                dept.description = request.POST.get('description', '')
                dept.save()
                messages.success(request, 'Department created successfully.')
            else:
                messages.error(request, 'A department with that name already exists.')
        return redirect('department_list')
    return render(request, 'organization/department_list.html', {'departments': departments})


@management_required
def department_edit(request, department_id):
    department = Department.objects.get(pk=department_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can update departments.')
            return redirect('department_list')
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Department name is required.')
            return render(request, 'organization/department_form.html', {'department': department, 'mode': 'edit'})
        duplicate = Department.objects.filter(Q(name=name) & ~Q(pk=department.pk)).exists()
        if duplicate:
            messages.error(request, 'A department with that name already exists.')
            return render(request, 'organization/department_form.html', {'department': department, 'mode': 'edit'})
        department.name = name
        department.description = request.POST.get('description', '')
        department.save()
        messages.success(request, 'Department updated.')
        return redirect('department_list')
    return render(request, 'organization/department_form.html', {'department': department, 'mode': 'edit'})


@management_required
def department_delete(request, department_id):
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can delete departments.')
            return redirect('department_list')
        department = Department.objects.get(pk=department_id)
        department.delete()
        messages.success(request, 'Department deleted.')
    return redirect('department_list')


@management_required
def employee_list(request):
    employees = Employee.objects.select_related('department').all().order_by('last_name', 'first_name')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can create employees.')
            return redirect('employee_list')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        if not first_name or not last_name or not email:
            messages.error(request, 'First name, last name, and email are required.')
            return redirect('employee_list')
        if Employee.objects.filter(email=email).exists():
            messages.error(request, 'An employee with that email already exists.')
            return redirect('employee_list')
        department_id = request.POST.get('department')
        department = Department.objects.filter(pk=department_id).first() if department_id else None
        employee = Employee.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            department=department,
            position=request.POST.get('position', '').strip(),
            employment_status=request.POST.get('employment_status', 'ACTIVE'),
        )
        messages.success(request, f'Employee {employee} created.')
        return redirect('employee_list')
    return render(request, 'organization/employee_list.html', {'employees': employees, 'departments': Department.objects.filter(is_active=True)})


@management_required
def employee_edit(request, employee_id):
    employee = Employee.objects.get(pk=employee_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can update employees.')
            return redirect('employee_list')
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Email is required.')
            return render(request, 'organization/employee_form.html', {'employee': employee, 'departments': Department.objects.filter(is_active=True)})
        duplicate = Employee.objects.filter(email=email).exclude(pk=employee.pk).exists()
        if duplicate:
            messages.error(request, 'Another employee already uses that email.')
            return render(request, 'organization/employee_form.html', {'employee': employee, 'departments': Department.objects.filter(is_active=True)})
        employee.first_name = request.POST.get('first_name', '').strip()
        employee.last_name = request.POST.get('last_name', '').strip()
        employee.email = email
        department_id = request.POST.get('department')
        employee.department = Department.objects.filter(pk=department_id).first() if department_id else None
        employee.position = request.POST.get('position', '').strip()
        employee.employment_status = request.POST.get('employment_status', employee.employment_status)
        employee.is_active = request.POST.get('is_active') == 'on'
        employee.save()
        messages.success(request, 'Employee updated.')
        return redirect('employee_list')
    return render(request, 'organization/employee_form.html', {'employee': employee, 'departments': Department.objects.filter(is_active=True)})


@management_required
def employee_delete(request, employee_id):
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can delete employees.')
            return redirect('employee_list')
        employee = Employee.objects.get(pk=employee_id)
        employee.is_active = False
        employee.employment_status = 'TERMINATED'
        employee.save(update_fields=['is_active', 'employment_status'])
        messages.success(request, 'Employee deactivated.')
    return redirect('employee_list')
