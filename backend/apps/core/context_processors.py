"""Template context processors for the core app."""

from .choices import Role
from .models import profile_for


def role(request):
    """Expose is_admin / can_permanently_delete to every template + the nav bar."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"is_admin": False, "can_permanently_delete": False}
    if user.is_superuser:
        return {"is_admin": True, "can_permanently_delete": True}
    profile = profile_for(user)
    return {
        "is_admin": profile.role == Role.ADMIN,
        "can_permanently_delete": profile.can_permanently_delete,
    }
