from django.contrib import admin

from .models import BusinessEntity, VetisCredentials


@admin.register(BusinessEntity)
class BusinessEntityAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'inn']


@admin.register(VetisCredentials)
class VetisCredentialsAdmin(admin.ModelAdmin):
    list_display = ['name', 'login', 'is_productive']