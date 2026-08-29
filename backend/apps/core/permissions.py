"""DRF permission classes for the two-role auth model (spec Section 5).

The whole ``/api/personnel/`` surface is ADMIN-only; ``permanent-delete`` needs
ADMIN plus the ``can_permanently_delete`` flag. Django superusers satisfy both.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

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


class IsAdminOrReadOnly(BasePermission):
    """Any authenticated user may read; only ADMIN may write.

    Used where STAFF needs to browse (items, trainings) to request or
    register, but only ADMIN manages the records (spec Section 5).
    """

    message = "Admin role required to modify this resource."

    def _check(self, request):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return _is_admin(request.user)

    def has_permission(self, request, view):
        return self._check(request)

    def has_object_permission(self, request, view, obj):
        return self._check(request)
