from django.contrib import admin

from .models import BusinessEntity, VetisCredentials, Enterprise


@admin.register(BusinessEntity)
class BusinessEntityAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'inn']


@admin.register(VetisCredentials)
class VetisCredentialsAdmin(admin.ModelAdmin):
    list_display = ['name', 'login', 'is_productive']


@admin.register(Enterprise)
class EnterpriseAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'number_list']