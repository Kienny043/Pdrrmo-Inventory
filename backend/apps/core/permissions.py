"""DRF permission classes for the two-role auth model (spec Section 5).

The whole ``/api/personnel/`` surface is ADMIN-only; ``permanent-delete`` needs
ADMIN plus the ``can_permanently_delete`` flag. Django superusers satisfy both.
"""

from rest_framework.permissions import BasePermission

from .choices import Role
from .models import profile_for


def _is_admin(user):
    if not (user and user.is_authenticated):
        return False
    if user.is_superuser:
        return True
    return profile_for(user).role == Role.ADMIN


def _can_permanently_delete(user):
    if not _is_admin(user):
        return False
    if user.is_superuser:
        return True
    return profile_for(user).can_permanently_delete


class IsAdmin(BasePermission):
    message = "Admin role required."

    def has_permission(self, request, view):
        return _is_admin(request.user)

    def has_object_permission(self, request, view, obj):
        return _is_admin(request.user)


class CanPermanentlyDelete(BasePermission):
    message = "Elevated permission (can_permanently_delete) required."

    def has_permission(self, request, view):
        return _can_permanently_delete(request.user)

    def has_object_permission(self, request, view, obj):
        return _can_permanently_delete(request.user)
