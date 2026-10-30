from django.urls import path

from . import views

urlpatterns = [
    path('', views.report_dashboard, name='report_dashboard'),
    path('export/<str:report_type>/', views.export_csv, name='report_export_csv'),
]
