from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .forms import ClientForm, ContactForm
from .models import Client, Contact
from django.db.models import Q
from django.template.loader import render_to_string
from django.http import JsonResponse


@login_required
def client_list(request):
    q = request.GET.get("q", "").strip()

    qs = Client.objects.annotate(contact_count=Count("contacts")).order_by("name")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    page_obj = Paginator(qs, 10).get_page(request.GET.get("page"))

    # --- AJAX branch: return just the results HTML ---
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string(
            "clientTrackerApp/clients/_client_results.html",
            {"clients": page_obj, "page_obj": page_obj, "q": q},
            request=request,
        )
        return JsonResponse({"html": html, "count": page_obj.paginator.count})

    return render(request, "clientTrackerApp/client_list.html", {
        "clients": page_obj, "page_obj": page_obj, "q": q,
    })



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
        "clientTrackerApp/contacts/contact_form.html",
        {"form": form, "client": client},
    )


@login_required
def contact_edit(request, pk):
    contact = get_object_or_404(Contact.objects.select_related("client"), pk=pk)

    if request.method == "POST":
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact updated.")
            return redirect("client-detail", pk=contact.client_id)
    else:
        form = ContactForm(instance=contact)

    return render(
        request,
        "clientTrackerApp/contacts/contact_edit.html",
        {"form": form, "contact": contact, "client": contact.client},
    )


@login_required
def contact_delete(request, pk):
    contact = get_object_or_404(Contact.objects.select_related("client"), pk=pk)

    if request.method == "POST":
        client_pk = contact.client_id
        contact.delete()
        messages.success(request, "Contact deleted.")
        return redirect("client-detail", pk=client_pk)

    return render(
        request,
        "clientTrackerApp/contacts/contact_confirm_delete.html",
        {"contact": contact, "client": contact.client},
    )



"""
############################################
Client Edits & Deletion 
############################################
"""

@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, f"Client '{client.name}' updated.")
            return redirect("client-detail", pk=client.pk)
    else:
        form = ClientForm(instance=client)

    return render(request, "clientTrackerApp/client_form.html", {
        "form": form,
        "client": client,   
    })


@login_required
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if request.method == "POST":
        name = client.name
        client.delete()
        messages.success(request, f"Client '{name}' deleted.")
        return redirect("client-list")

    return render(request, "clientTrackerApp/client_confirm_delete.html", {
        "client": client,
    })

