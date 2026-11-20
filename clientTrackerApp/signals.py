# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import *

@receiver(post_save, sender=Contact)
def _inc_contact_count(sender, instance, created, **kwargs):
    if created:
        Client.objects.filter(pk=instance.client_id).update(
            contact_count=models.F("contact_count") + 1
        )

@receiver(post_delete, sender=Contact)
def _dec_contact_count(sender, instance, **kwargs):
    Client.objects.filter(pk=instance.client_id).update(
        contact_count=models.F("contact_count") - 1
    )

    