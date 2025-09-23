from django.db import models


class VetisCredentials(models.Model):
    name = models.CharField(null=False, blank=False, max_length=100, verbose_name='название')
    login = models.CharField(null=False, blank=False, verbose_name='логин')
    password = models.CharField(null=False, blank=False, verbose_name='пароль')
    api_key = models.CharField(null=False, blank=False, verbose_name='API key')
    service_id = models.CharField(null=False, blank=False, verbose_name='service ID')
    issuer_id = models.CharField(null=False, blank=False, verbose_name='issuer ID')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'подключение Ветис'
        verbose_name_plural = 'подключения Ветис'
        ordering = ['name']