from django.db import models

from main.models import User


PRODUCT_TYPES = (
    (1, 'Мясо и мясопродукты'),
    (2, 'Корма и кормовые добавки'),
    (3, 'Живые животные'),
    (4, 'Лекарственные средства'),
    (5, 'Пищевые продукты'),
    (6, 'Непищевые продукты и другое'),
    (7, 'Рыба и морепродукты'),
    (8, 'Продукция, не требующая разрешения'),
)


class ApiRequestsHistoryRecord(models.Model):
    datetime = models.DateTimeField(auto_now_add=True, verbose_name='метка времени')
    soap_action = models.CharField(null=True, max_length=30, verbose_name='SOAP action')
    soap_request = models.TextField(null=True, verbose_name='текст запроса')
    response_status_code = models.IntegerField(null=True, verbose_name='статус ответа')
    response_body = models.TextField(null=True, verbose_name='текст ответа')
    comment = models.CharField(null=True, max_length=255, verbose_name='комментарий')
    user = models.ForeignKey(User, null=True, on_delete=models.PROTECT, verbose_name='пользователь')

    def __str__(self):
        return f'{self.soap_action} ({self.response_status_code})'
    
    class Meta:
        verbose_name = 'запись истории запросов'
        verbose_name_plural = 'записи истории запросов'
        ordering = ['-datetime']


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


class BusinessEntity(models.Model):
    TYPE_CHOICES = (
        (1, 'Юрлицо'),
        (2, 'Физлицо'),
        (3, 'ИП'),
    )
    guid = models.UUIDField(null=False, blank=False, editable=True, unique=True, db_index=True)
    uuid = models.UUIDField(null=False, blank=False, editable=True, unique=True)
    type = models.IntegerField(null=False, blank=False, choices=TYPE_CHOICES, verbose_name='тип') # get_type_display in templates
    name = models.CharField(null=False, blank=False, verbose_name='имя')
    inn = models.CharField(null=True, blank=True, max_length=20, verbose_name='ИНН')
    address = models.CharField(null=True, blank=True, max_length=255, verbose_name='адрес')
    credentials = models.ForeignKey(VetisCredentials, null=True, verbose_name='параметры подключения', on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True, verbose_name='активен')

    def __str__(self):
        return f'{self.name} ({self.inn})'
    
    class Meta:
        verbose_name = 'хозяйствующий субъект'
        verbose_name_plural = 'хозяйствующие субъекты'
        ordering = ['name']


class Enterprise(models.Model):
    TYPE_CHOICES = (
        (1, 'предприятие'),
        (2, 'рынок'),
        (3, 'СББЖ'),
        (4, 'судно'),
    )
    business_entity = models.ForeignKey(BusinessEntity, on_delete=models.PROTECT, verbose_name='хозяйствующий субъект')
    guid = models.UUIDField(editable=True, unique=True, db_index=True)
    uuid = models.UUIDField(editable=True, unique=True)
    type = models.IntegerField(choices=TYPE_CHOICES, verbose_name='тип') # get_type_display in templates
    name = models.CharField(verbose_name='имя')
    number_list = models.CharField(null=True, blank=True, verbose_name='номера предприятия')
    address = models.CharField(null=True, blank=True, max_length=255, verbose_name='адрес')
    is_active = models.BooleanField(default=True, verbose_name='активно')

    def __str__(self):
        return f'{self.name} ({self.address})'
    
    class Meta:
        verbose_name = 'предприятие'
        verbose_name_plural = 'предприятия'
        ordering = ['name']