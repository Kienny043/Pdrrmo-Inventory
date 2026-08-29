"""Signal wiring for the core app (registered in ``CoreConfig.ready()``)."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=get_user_model(), dispatch_uid="core.create_user_profile")
def create_user_profile(sender, instance, created, **kwargs):
    """Give every newly created User a default (STAFF) profile."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
