from django.urls import path
from . import views

urlpatterns = [
    # Clients
    path("", views.client_list, name="client-list"),
    path("clients/new/", views.client_create, name="client-create"),
    path("clients/<int:pk>/", views.client_detail, name="client-detail"),
    path("clients/<int:pk>/edit/", views.client_edit, name="client-edit"),
    path("clients/<int:pk>/delete/", views.client_delete, name="client-delete"),

    # Contacts
    path("clients/<int:client_pk>/contacts/new/", views.contact_create, name="contact-create-for-client"),
    path("contacts/new/", views.contact_create, name="contact-create"),
    path("contacts/<int:pk>/edit/", views.contact_edit, name="contact-edit"),
    path("contacts/<int:pk>/delete/", views.contact_delete, name="contact-delete"),

    # Optional code-login
    # path("login-code/", views.client_login, name="client-code-login"),
    # path("dashboard/", views.client_dashboard, name="client-dashboard"),
]