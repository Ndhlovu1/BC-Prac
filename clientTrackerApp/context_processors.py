# clientTrackerApp/context_processors.py
from .models import Client, Contact

def delinked_counts(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}
    return {
        "delinked_count":          Contact.objects.filter(client__isnull=True).count(),
        "delinked_clients_count":  Client.objects.filter(is_delinked=True).count(),
    }


