from datetime import date

from django.contrib import messages
from core.decorators import management_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from .models import Project, Task


@management_required
def project_list(request):
    projects = Project.objects.order_by('name')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can manage projects.')
            return redirect('project_list')
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Project name is required.')
            return redirect('project_list')
        project = Project.objects.create(
            name=name,
            description=request.POST.get('description', ''),
            status=request.POST.get('status', 'PLANNING'),
            priority=request.POST.get('priority', 'MEDIUM'),
            start_date=request.POST.get('start_date') or None,
            end_date=request.POST.get('end_date') or None,
            budget=request.POST.get('budget', '0'),
            manager=request.user,
        )
        messages.success(request, f'Project {project.name} created.')
        return redirect('project_list')
    return render(request, 'projects/project_list.html', {'projects': projects})


@management_required
def project_edit(request, project_id):
    project = Project.objects.get(pk=project_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can edit projects.')
            return redirect('project_list')
        project.name = request.POST.get('name', project.name).strip()
        project.description = request.POST.get('description', '')
        project.status = request.POST.get('status', project.status)
        project.priority = request.POST.get('priority', project.priority)
        project.start_date = request.POST.get('start_date') or None
        project.end_date = request.POST.get('end_date') or None
        project.budget = request.POST.get('budget', '0')
        project.save()
        messages.success(request, 'Project updated.')
        return redirect('project_list')
    return render(request, 'projects/project_form.html', {'project': project, 'users': User.objects.filter(is_active=True)})


@management_required
def task_list(request):
    tasks = Task.objects.select_related('project', 'assigned_to').order_by('due_date', 'priority')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser and not request.user == request.user:
            messages.error(request, 'Only managers can create tasks.')
            return redirect('task_list')
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Task title is required.')
            return redirect('task_list')
        project_id = request.POST.get('project')
        project = Project.objects.filter(pk=project_id).first() if project_id else None
        if not project:
            messages.error(request, 'Project is required.')
            return redirect('task_list')
        assigned_to_id = request.POST.get('assigned_to')
        assigned_to = User.objects.filter(pk=assigned_to_id).first() if assigned_to_id else None
        task = Task.objects.create(
            project=project,
            title=title,
            description=request.POST.get('description', ''),
            status=request.POST.get('status', 'PENDING'),
            priority=request.POST.get('priority', 'MEDIUM'),
            due_date=request.POST.get('due_date') or None,
            assigned_to=assigned_to,
        )
        messages.success(request, f'Task {task.title} created.')
        return redirect('task_list')
    return render(request, 'projects/task_list.html', {'tasks': tasks, 'projects': Project.objects.all(), 'users': User.objects.filter(is_active=True)})


@management_required
def task_edit(request, task_id):
    task = Task.objects.get(pk=task_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser and task.assigned_to != request.user:
            messages.error(request, 'You are not allowed to update this task.')
            return redirect('task_list')
        task.title = request.POST.get('title', task.title).strip()
        task.description = request.POST.get('description', '')
        task.status = request.POST.get('status', task.status)
        task.priority = request.POST.get('priority', task.priority)
        task.due_date = request.POST.get('due_date') or None
        assigned_to_id = request.POST.get('assigned_to')
        task.assigned_to = User.objects.filter(pk=assigned_to_id).first() if assigned_to_id else None
        if task.status == 'COMPLETED':
            from django.utils import timezone
            task.completed_at = timezone.now()
        elif task.status != 'COMPLETED':
            task.completed_at = None
        task.save()
        messages.success(request, 'Task updated.')
        return redirect('task_list')
    return render(request, 'projects/task_form.html', {'task': task, 'projects': Project.objects.all(), 'users': User.objects.filter(is_active=True)})


@management_required
def task_complete(request, task_id):
    task = Task.objects.get(pk=task_id)
    if task.assigned_to != request.user and not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You are not permitted to complete this task.')
        return redirect('task_list')
    task.status = 'COMPLETED'
    from django.utils import timezone
    task.completed_at = timezone.now()
    task.save(update_fields=['status', 'completed_at'])
    messages.success(request, 'Task marked complete.')
    return redirect('task_list')
