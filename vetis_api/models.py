from django.db import models

from main.models import User


class ApiRequestsHistoryRecord(models.Model):
    datetime = models.DateTimeField(auto_now_add=True, verbose_name='метка времени')
    soap_action = models.CharField(null=True, max_length=30, verbose_name='SOAP action')
    soap_request = models.TextField(null=True, verbose_name='текст запроса')
    response_status_code = models.IntegerField(null=True, verbose_name='статус ответа')
    response_body = models.TextField(null=True, verbose_name='текст ответа')
    comment = models.CharField(null=True, max_length=255, verbose_name='комментарий')
    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='пользователь')

    def __str__(self):
        return f'{self.soap_action} ({self.response_status_code})'
    
    class Meta:
        verbose_name = 'запись истории запросов'
        verbose_name_plural = 'записи истории запросов'
        ordering = ['-datetime']


class BusinessEntity(models.Model):
    TYPE_CHOICES = (
        (1, 'Юрлицо'),
        (2, 'Физлицо'),
        (3, 'ИП'),
    )
    guid = models.UUIDField(null=False, blank=False, editable=True, unique=True)
    uuid = models.UUIDField(null=False, blank=False, editable=True, unique=True)
    type = models.IntegerField(null=False, blank=False, choices=TYPE_CHOICES, verbose_name='тип') # get_type_display in templates
    name = models.CharField(null=False, blank=False, verbose_name='имя')
    inn = models.CharField(null=True, blank=True, max_length=20, verbose_name='ИНН')
    address = models.CharField(null=True, blank=True, max_length=255, verbose_name='адрес')

    def __str__(self):
        return f'{self.name} ({self.inn})'
    
    class Meta:
        verbose_name = 'хозяйствующий субъект'
        verbose_name_plural = 'хозяйствующие субъекты'
        ordering = ['name']


class VetisCredentials(models.Model):
    name = models.CharField(null=False, blank=False, max_length=100, verbose_name='название')
    is_productive = models.BooleanField(default=False, verbose_name='продуктивный')
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