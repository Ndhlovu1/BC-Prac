# clientTrackerApp/context_processors.py
from .models import Client, Contact


def delinked_counts(request):
    """Provide delinked record counts to templates for staff users only."""
    # Hide these counts from anonymous users and non-staff users.
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    # Count contacts with no linked client and clients marked as delinked.
    return {
        "delinked_count": Contact.objects.filter(client__isnull=True).count(),
        "delinked_clients_count": Client.objects.filter(is_delinked=True).count(),
    }


