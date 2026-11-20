from django.contrib import admin

# Register your models here.
from .models import Client, Contact

# Using this for testing purposes
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'initials_label')
    search_fields = ('name', 'code')
    ordering = ('name',)
    readonly_fields = ('code', 'initials_label')



@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'surname', 'email', 'client')
    search_fields = ('first_name', 'surname', 'email', 'client__name')
    ordering = ('surname', 'first_name')

