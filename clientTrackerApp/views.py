from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .forms import *
from .models import Client, Contact
from django.db.models import Q
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction


staff_required = user_passes_test(
    lambda u: u.is_active and u.is_staff, login_url="staff-login")

@login_required
def client_list(request):
    q = request.GET.get("q", "").strip()

    qs = (
        Client.objects
        .filter(is_delinked=False)          # ← exclude archived
        .annotate(contact_count=Count("contacts"))
        .order_by("name")
    )
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    page_obj = Paginator(qs, 10).get_page(request.GET.get("page"))
    context = {"clients": page_obj, "page_obj": page_obj, "q": q}

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string(
            "clientTrackerApp/clients/partial/_client_results.html",
            context, request=request,
        )
        return JsonResponse({"html": html, "count": page_obj.paginator.count})

    return render(request, "clientTrackerApp/client_list.html", context)

@login_required
@staff_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(request, "clientTrackerApp/client_detail.html", {
        "client": client,
        "contacts": client.contacts.all(),
    })


@login_required
@staff_required
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
@staff_required
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
@staff_required
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
@staff_required
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
@staff_required
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
@staff_required
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





"""
######################################################
Staff Login - Better Protection Against Outsiders
######################################################
"""

def staff_login(request):
    # Already logged in and staff → go to dashboard
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("client-list")

    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = StaffLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.get_short_name() or user.username}.")

            # Safe redirect: only follow ?next= if same-origin
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect("client-list")
    else:
        form = StaffLoginForm(request)

    return render(request, "auth/login.html", {
        "form": form,
        "next": next_url,
    })


def staff_logout(request):
    if request.method == "POST":       # POST-only for CSRF safety
        auth_logout(request)
        messages.info(request, "You have been logged out.")
        return redirect("staff-login")
    # GET → render a tiny confirmation page instead of logging out silently
    return render(request, "auth/logout.html")


"""
#######################################################
 AJAX DELINK — set contact.client = None (does NOT delete)
#######################################################
"""
@login_required
@staff_required
@require_POST
def contact_delink(request, pk):
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        return JsonResponse({"ok": False, "error": "AJAX only"}, status=400)

    contact = get_object_or_404(Contact.objects.select_related("client"), pk=pk)

    client_id = request.POST.get("client_id")
    if client_id and str(contact.client_id) != str(client_id):
        return JsonResponse(
            {"ok": False, "error": "Contact does not belong to this client."},
            status=400,
        )

    if contact.client_id is None:
        return JsonResponse({"ok": False, "error": "Contact is already delinked."}, status=400)

    name = f"{contact.first_name} {contact.surname}"
    contact.client = None
    contact.save(update_fields=["client"])

    return JsonResponse({
        "ok": True,
        "message": f'"{name}" has been delinked.',
        "contact_id": contact.pk,
        "client_id": client_id,
    })


"""
# ######################################################
# DELINKED CONTACTS LIST
# ######################################################
"""


@login_required
@staff_required
def delinked_contacts(request):
    q = request.GET.get("q", "").strip()
    qs = Contact.objects.filter(client__isnull=True).order_by("surname", "first_name")

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(surname__icontains=q) |
            Q(email__icontains=q)
        )

    return render(request, "clientTrackerApp/contacts/delinked_list.html", {
        "contacts": qs,
        "q": q,
        "total_clients": Client.objects.count(),
    })


"""
# ######################################################
# RE-LINK A DELINKED CONTACT TO A CLIENT 
# ######################################################
"""


@login_required
@staff_required
def contact_relink(request, pk):
    contact = get_object_or_404(Contact, pk=pk)

    if contact.client_id is not None:
        messages.info(request, "That contact is already linked to a client.")
        return redirect("client-detail", pk=contact.client_id)

    if request.method == "POST":
        client_id = request.POST.get("client")
        client = Client.objects.filter(pk=client_id).first() if client_id else None
        if not client:
            messages.error(request, "Please select a client.")
        else:
            contact.client = client
            contact.save(update_fields=["client"])
            messages.success(
                request,
                f'"{contact.first_name} {contact.surname}" relinked to {client.name}.'
            )
            return redirect("client-detail", pk=client.pk)

    clients = Client.objects.order_by("name")
    return render(request, "clientTrackerApp/contacts/contact_relink.html", {
        "contact": contact,
        "clients": clients,
    })




"""
# ######################################################
# # DELINK A CLIENT (soft-delete + cascade-unlink its contacts)
# ######################################################
"""

@login_required
@staff_required
def client_delink(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if client.is_delinked:
        messages.info(request, "This client is already delinked.")
        return redirect("delinked-clients")

    if request.method == "POST":
        with transaction.atomic():
            # 1) Unlink every contact that belongs to this client
            unlinked = client.contacts.update(client=None)

            # 2) Mark the client as delinked
            client.is_delinked = True
            client.delinked_at = timezone.now()
            client.save(update_fields=["is_delinked", "delinked_at"])

        messages.success(
            request,
            f'"{client.name}" was delinked. '
            f'{unlinked} contact{"s" if unlinked != 1 else ""} were also unlinked.'
        )
        return redirect("delinked-clients")

    # GET → confirmation page
    return render(request, "clientTrackerApp/clients/client_delink_confirm.html", {
        "client": client,
        "contact_count": client.contacts.count(),
    })


# ------------------------------------------------------------------
# LIST OF DELINKED CLIENTS (+ their (now-delinked) contacts)
# ------------------------------------------------------------------
@login_required
@staff_required
def delinked_clients(request):
    q = request.GET.get("q", "").strip()

    qs = Client.objects.filter(is_delinked=True).order_by("-delinked_at", "name")

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    return render(request, "clientTrackerApp/clients/delinked_clients.html", {
        "clients": qs,
        "q": q,
    })


# ------------------------------------------------------------------
# RE-LINK A DELINKED CLIENT (+ optionally its contacts back)
# ------------------------------------------------------------------
@login_required
@staff_required
def client_relink(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if not client.is_delinked:
        messages.info(request, "That client is already active.")
        return redirect("client-detail", pk=client.pk)

    if request.method == "POST":
        with transaction.atomic():
            client.is_delinked = False
            client.delinked_at = None
            client.save(update_fields=["is_delinked", "delinked_at"])

            # Optional: reattach orphans that share this client's code prefix
            relink_contacts = request.POST.get("relink_contacts") == "on"
            if relink_contacts:
                # Match any orphaned contact whose email was associated with this
                # client's code (nothing reliable to match on otherwise).
                # If you track this in a history table, plug that query in here.
                pass

        messages.success(request, f'"{client.name}" has been relinked.')
        return redirect("client-detail", pk=client.pk)

    orphans = Contact.objects.filter(client__isnull=True).order_by("surname", "first_name")

    return render(request, "clientTrackerApp/clients/client_relink.html", {
        "client": client,
        "orphans": orphans,
    })






