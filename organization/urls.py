from django.urls import path

from . import views

urlpatterns = [
    path('', views.department_list, name='department_list'),
    path('departments/<int:department_id>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:department_id>/delete/', views.department_delete, name='department_delete'),
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/<int:employee_id>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:employee_id>/delete/', views.employee_delete, name='employee_delete'),
]
