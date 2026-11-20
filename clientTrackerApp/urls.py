from django.urls import path
from . import views


from django.conf.urls.static import static


urlpatterns = [
    path("", views.client_list, name="client-list"),
    path("clients/new/", views.client_create, name="client-create"),
    path("clients/<int:pk>/", views.client_detail, name="client-detail"),
    path("clients/<int:pk>/edit/", views.client_edit, name="client-edit"),
    path("clients/<int:pk>/delete/", views.client_delete, name="client-delete"),

    # Contact created from a specific client's page:
    path("clients/<int:client_pk>/contacts/new/",views.contact_create,name="contact-create-for-client",),
    path("clients/<int:client_pk>/contacts/new/",views.contact_create,name="contact-create-for-client",),
    path("contacts/new/",views.contact_create,name="contact-create",),



    # path("login-code/", views.client_login, name="client-code-login"),
]

