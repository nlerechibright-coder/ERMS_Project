from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('organization/', include('organization.urls')),
    path('inventory/', include('inventory.urls')),
    path('procurement/', include('procurement.urls')),
    path('sales/', include('sales.urls')),
    path('projects/', include('projects.urls')),
    path('finance/', include('finance.urls')),
    path('reports/', include('reports.urls')),
    path('pos/', include('pos.urls')),
]
