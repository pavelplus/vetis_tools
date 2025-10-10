from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    vetis_login = models.CharField(null=True, blank=True, max_length=20, verbose_name='логин Ветис')
    
    def get_display_name(self):
        return self.get_full_name() or self.get_username()
    
