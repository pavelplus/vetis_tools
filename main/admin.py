from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

UserAdmin.fieldsets +=  (('Дополнительные поля', {'fields': ('vetis_login', )}),)

admin.site.register(User, UserAdmin)