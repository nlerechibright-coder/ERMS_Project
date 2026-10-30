from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
    path("staff/", views.staff_list, name="staff_list"),
    path("staff/new/", views.staff_create, name="staff_create"),
    path("staff/<int:user_id>/edit/", views.staff_edit, name="staff_edit"),
]
