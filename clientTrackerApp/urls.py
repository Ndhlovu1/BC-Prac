from django.urls import path
from . import views

urlpatterns = [
    path("", views.client_list, name="client-list"),
    path("clients/new/", views.client_create, name="client-create"),
    path("clients/<int:pk>/", views.client_detail, name="client-detail"),
    # Contact created from a specific client's page:
    path("clients/<int:client_pk>/contacts/new/", views.contact_create, name="contact-create-for-client"),
    # Optional: standalone contact creation (client dropdown in form)
    path("contacts/new/", views.contact_create, name="contact-create"),
    # path("login-code/", views.client_login, name="client-code-login"),
    path("", views.client_dashboard, name="client-dashboard"),
]

