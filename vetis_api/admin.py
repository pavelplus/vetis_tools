from django.contrib import admin

from .models import VetisCredentials


@admin.register(VetisCredentials)
class VetisCredentialsAdmin(admin.ModelAdmin):
    list_display = ['name', 'login', 'is_productive']