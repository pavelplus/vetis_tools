from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    
    def get_display_name(self):
        return self.get_full_name() or self.get_username()
    
