from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import CharField, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import management_required

from .models import UserProfile

ROLE_CHOICES = [
    ("manager", "Manager"),
    ("sales_staff", "Sales Staff"),
]


@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        profile.role = request.POST.get("role", profile.role)
        profile.phone = request.POST.get("phone", profile.phone)
        profile.department = request.POST.get("department", profile.department)
        profile.save()
        messages.success(request, "Profile updated.")
    return render(request, "accounts/profile.html", {"profile": profile})


@management_required
def staff_list(request):
    User = get_user_model()
    users = (
        User.objects
        .select_related("profile")
        .annotate(role=Coalesce("profile__role", Value("manager"), output_field=CharField()))
        .order_by("-is_active", "username")
    )
    return render(request, "accounts/staff_list.html", {"users": users, "role_choices": ROLE_CHOICES})


@management_required
def staff_create(request):
    User = get_user_model()

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        department = (request.POST.get("department") or "").strip()
        role = request.POST.get("role", "sales_staff")

        if not username:
            messages.error(request, "Username is required.")
        elif not password:
            messages.error(request, "Password is required.")
        elif role not in dict(ROLE_CHOICES):
            messages.error(request, "Invalid role.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "That username already exists.")
        else:
            is_manager = role == "manager"
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email,
                is_staff=is_manager,
                is_superuser=False,
                is_active=True,
            )
            UserProfile.objects.create(user=user, role=role, phone=phone, department=department)
            messages.success(request, f"Staff account created for {user.username}.")
            return redirect("staff_list")

    return render(request, "accounts/staff_form.html", {
        "role_choices": ROLE_CHOICES,
        "editing": False,
    })


@management_required
def staff_edit(request, user_id):
    User = get_user_model()
    staff = get_object_or_404(User, pk=user_id)

    if staff.is_superuser:
        messages.error(request, "Superuser accounts cannot be edited from this page.")
        return redirect("staff_list")

    if request.user.pk == staff.pk:
        messages.error(request, "You cannot edit your own account from this page.")
        return redirect("staff_list")

    profile, _ = UserProfile.objects.get_or_create(user=staff)

    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        department = (request.POST.get("department") or "").strip()
        role = request.POST.get("role", profile.role)
        password = request.POST.get("password") or ""
        is_active = request.POST.get("is_active") == "on"

        if role not in dict(ROLE_CHOICES):
            messages.error(request, "Invalid role.")
        else:
            staff.first_name = first_name
            staff.last_name = last_name
            staff.email = email
            staff.is_active = is_active
            staff.is_staff = role == "manager"
            staff.is_superuser = False

            if password:
                staff.set_password(password)

            staff.save()

            profile.role = role
            profile.phone = phone
            profile.department = department
            profile.save()

            messages.success(request, f"Staff account updated for {staff.username}.")
            return redirect("staff_list")

    return render(request, "accounts/staff_form.html", {
        "staff": staff,
        "profile": profile,
        "role_choices": ROLE_CHOICES,
        "editing": True,
    })
