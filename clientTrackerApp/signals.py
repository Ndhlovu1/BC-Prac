# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import *

# Run after a Contact is saved. The sender limits this handler to Contact objects.
@receiver(post_save, sender=Contact)
def _inc_contact_count(sender, instance, created, **kwargs):
    # Count only newly created contacts, not updates to existing contacts.
    if created:
        # Increment the parent Client's denormalized contact_count atomically.
        Client.objects.filter(pk=instance.client_id).update(
            contact_count=models.F("contact_count") + 1
        )

# Run after a Contact is deleted to keep the parent Client count in sync.
@receiver(post_delete, sender=Contact)
def _dec_contact_count(sender, instance, **kwargs):
    # Decrement the count for the Client associated with the deleted contact.
    Client.objects.filter(pk=instance.client_id).update(
        contact_count=models.F("contact_count") - 1
    )

    