from django.urls import path

from . import views

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('projects/<int:project_id>/edit/', views.project_edit, name='project_edit'),
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:task_id>/complete/', views.task_complete, name='task_complete'),
]
