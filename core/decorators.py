from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse


def _role(user):
    return getattr(getattr(user, "profile", None), "role", "")


def management_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if user.is_staff or user.is_superuser:
            return view_func(request, *args, **kwargs)

        if _role(user) == "sales_staff":
            try:
                return redirect(reverse("pos_interface"))
            except Exception:
                return redirect("dashboard")

        messages.error(request, "Management access required.")
        return redirect("dashboard")

    return _wrapped


def pos_access_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        user = request.user
        role = _role(user)
        if user.is_staff or user.is_superuser or role in ("sales_staff", "manager"):
            return view_func(request, *args, **kwargs)

        messages.error(request, "You do not have access to the till.")
        return redirect("dashboard")

    return _wrapped
