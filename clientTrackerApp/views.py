from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ClientForm, ContactForm
from .models import Client, Contact


@login_required
def client_list(request):
    # Prefetch contacts to avoid N+1; annotate count for the badge
    clients = Client.objects.annotate(contact_count=Count("contacts")).prefetch_related("contacts")
    return render(request, "clientTrackerApp/client_list.html", {"clients": clients})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(request, "clientTrackerApp/client_detail.html", {
        "client": client,
        "contacts": client.contacts.all(),
    })


@login_required
def client_create(request):
    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"Client '{client.name}' created with code {client.code}.")
            return redirect("client-list")
    else:
        form = ClientForm()
    return render(request, "clientTrackerApp/client_form.html", {"form": form})

@login_required
def contact_create(request, client_pk=None):
    client = get_object_or_404(Client, pk=client_pk) if client_pk else None

    if request.method == "POST":
        form = ContactForm(request.POST, client=client)
        if form.is_valid():
            contact = form.save()
            messages.success(request, "Contact added.")
            return redirect("client-detail", pk=contact.client_id)
    else:
        form = ContactForm(client=client)

    return render(
        request,
        "clientTrackerApp/contact_form.html",
        {"form": form, "client": client},
    )




@login_required
def client_dashboard(request):
    cid = request.session.get("client_id")
    client = get_object_or_404(Client, id=cid)
    return render(request, "clientTrackerApp/dashboard.html", {
        "client": client,
        "contacts": client.contacts.all(),
    })


