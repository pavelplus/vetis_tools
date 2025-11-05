from datetime import datetime, timezone, timedelta

from django.db import models
from django.core.exceptions import ObjectDoesNotExist

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

TZ_MOSCOW = timezone(timedelta(hours=3))


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
    name = models.CharField(max_length=100, verbose_name='название')
    is_productive = models.BooleanField(default=False, verbose_name='продуктивный')
    login = models.CharField(verbose_name='логин')
    password = models.CharField(verbose_name='пароль')
    api_key = models.CharField(verbose_name='API key')
    service_id = models.CharField(verbose_name='service ID')
    issuer_id = models.CharField(verbose_name='issuer ID')

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
    guid = models.UUIDField(editable=True, unique=True, db_index=True)
    uuid = models.UUIDField(editable=True, unique=True)
    type = models.IntegerField(choices=TYPE_CHOICES, verbose_name='тип') # get_type_display in templates
    name = models.CharField(max_length=255, verbose_name='имя')
    short_name = models.CharField(max_length=30, null=True, blank=True, verbose_name='имя (кратко)')
    inn = models.CharField(blank=True, max_length=20, verbose_name='ИНН')
    address = models.CharField(blank=True, max_length=255, verbose_name='адрес')
    credentials = models.ForeignKey(VetisCredentials, null=True, verbose_name='параметры подключения', on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True, verbose_name='активен')

    def __str__(self):
        return self.short_name if self.short_name else f'{self.name} ({self.inn})'
    
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
    name = models.CharField(max_length=255, verbose_name='имя')
    number_list = models.CharField(blank=True, verbose_name='номера предприятия')
    address = models.CharField(blank=True, max_length=255, verbose_name='адрес')
    is_active = models.BooleanField(default=True, verbose_name='активно')
    is_allowed = models.BooleanField(default=False, verbose_name='разрешено работать через АПИ')
    stock_entries_last_updated = models.DateTimeField(null=True, blank=True, verbose_name='последнее обновление журнала')

    def __str__(self):
        return f'{self.name} ({self.address})'
    
    class Meta:
        verbose_name = 'предприятие'
        verbose_name_plural = 'предприятия'
        ordering = ['name']


class BusinessEntityInfo(models.Model):
    guid = models.UUIDField(primary_key=True)
    uuid = models.UUIDField()
    name = models.CharField(max_length=255, verbose_name='имя')
    inn = models.CharField(blank=True, max_length=20, verbose_name='ИНН')
    date_updated = models.DateTimeField(auto_now=True, verbose_name='дата обновления')

    def __str__(self):
        return f'{self.name} ({self.inn})'
    
    class Meta:
        verbose_name = 'хозяйствующий субъект (инфо)'
        verbose_name_plural = 'хозяйствующие субъекты (инфо)'
        ordering = ['name']


class EnterpriseInfo(models.Model):
    guid = models.UUIDField(primary_key=True)
    uuid = models.UUIDField()
    name = models.CharField(max_length=255, verbose_name='имя')
    address = models.CharField(blank=True, max_length=255, verbose_name='адрес')
    date_updated = models.DateTimeField(auto_now=True, verbose_name='дата обновления')

    def __str__(self):
        return f'{self.name} ({self.address})'
    
    class Meta:
        verbose_name = 'предприятие (инфо)'
        verbose_name_plural = 'предприятия (инфо)'
        ordering = ['name']


class Product(models.Model):
    guid = models.UUIDField(unique=True, db_index=True)
    uuid = models.UUIDField(unique=True)
    name = models.CharField(max_length=255, verbose_name='название')
    code = models.CharField(blank=True, max_length=255, verbose_name='код ТН ВЭД')
    product_type = models.IntegerField(choices=PRODUCT_TYPES, verbose_name='тип продукции')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'продукция'
        verbose_name_plural = 'продукция'
        ordering = ['name']


class SubProduct(models.Model):
    guid = models.UUIDField(unique=True, db_index=True)
    uuid = models.UUIDField(unique=True)
    name = models.CharField(max_length=255, verbose_name='название')
    code = models.CharField(blank=True, max_length=255, verbose_name='код ТН ВЭД')
    product_guid = models.UUIDField(verbose_name='продукция (GUID)')
    product = models.ForeignKey(Product, null=True, verbose_name='продукция', on_delete=models.PROTECT)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'вид продукции'
        verbose_name_plural = 'виды продукции'
        ordering = ['name']


class ProductItem(models.Model):
    guid = models.UUIDField(unique=True, db_index=True)
    uuid = models.UUIDField(unique=True)
    is_active = models.BooleanField(default=True, verbose_name='активно')
    name = models.CharField(max_length=255, verbose_name='название')
    gtin = models.CharField(blank=True, max_length=20, verbose_name='GTIN')
    product_type = models.IntegerField(choices=PRODUCT_TYPES, verbose_name='тип продукции')
    product_guid = models.UUIDField(verbose_name='продукция (GUID)')
    product = models.ForeignKey(Product, null=True, verbose_name='продукция', on_delete=models.PROTECT)
    subproduct_guid = models.UUIDField(verbose_name='вид продукции (GUID)')
    subproduct = models.ForeignKey(SubProduct, null=True, verbose_name='вид продукции', on_delete=models.PROTECT)
    is_gost = models.BooleanField(default=False, verbose_name='соответствует ГОСТ')
    gost = models.CharField(blank=True, max_length=255, verbose_name='ГОСТ')
    producer_guid = models.UUIDField(blank=True, null=True, verbose_name='производитель (GUID)')
    producer = models.ForeignKey(BusinessEntity, null=True, verbose_name='производитель', on_delete=models.PROTECT)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'наименование продукции'
        verbose_name_plural = 'наименования продукции'
        ordering = ['name']


class Unit(models.Model):
    guid = models.UUIDField(unique=True)
    name = models.CharField(max_length=255, verbose_name='название')

    # TODO implement native get_or_create logic https://docs.djangoproject.com/en/5.2/ref/models/querysets/#get-or-create
    @classmethod
    def get_or_create(cls, guid: str, name: str):
        try:
            unit = cls.objects.get(guid=guid)
        except ObjectDoesNotExist:
            unit = cls.objects.create(guid=guid, name=name)
        return unit

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'единица измерения'
        verbose_name_plural = 'единицы измерения'
        ordering = ['name']


class ComplexDate():
    """
    Contains required year, month and optional day, hour.
    String representation: dd.mm.yyyy:hh
    """

    def __init__(self, year: int, month: int, day: int = None, hour: int = None):
        self._year = year
        self._month = month
        self._day = day
        self._hour = hour

        if not self.is_valid():
            raise ValueError()
        
        self.date_str = self.to_string()


    @classmethod
    def from_string(cls, str: str):
        year = None
        month = None
        day = None
        hour = None
        
        try:
            date, time = str.split(':')
        except:
            date = str
            time = None
        
        date_list = date.split('.')

        if len(date_list) == 3:
            day = int(date_list.pop(0))
        
        month = int(date_list[0])
        year = int(date_list[1])
        
        if time:
            hour = int(time)

        return cls(year, month, day, hour)
    

    def __str__(self):
        return self.date_str
    

    def update(self, what: str, value: int):
        if what == 'year':
            self._year = value
        elif what == 'month':
            self._month = value
        elif what == 'day':
            self._day = value
        elif what == 'hour':
            self._hour = value
        
        if not self.is_valid():
            raise ValueError()
        
        self.date_str = self.to_string()

        return self


    def to_string(self) -> str:
        result_str = ''
        if self._day:
            result_str += f'{self._day:0>2}.'
        result_str += f'{self._month:0>2}.{self._year:0>4}'
        if self._hour is not None:
            result_str += f':{self._hour:0>2}'

        return result_str
    

    def to_datetime(self) -> datetime:
        return datetime(
            year=self._year,
            month=self._month,
            day=self._day if self._day is not None else 1,
            hour=self._hour if self._hour is not None else 0,
            tzinfo=TZ_MOSCOW
        )
    

    def is_valid(self):
        if self._year is None or (self._year < 1 or self._year > 9999):
            return False
        if self._month is None or (self._month < 1 or self._month > 12):
            return False
        if self._day is not None and (self._day < 1 or self._day > 31):
            return False
        if self._hour is not None and (self._hour < 0 or self._hour > 23):
            return False
        
        return True


# class VetDocument(models.Model):
#     VETDFORM_CHOICES = (
#         ('CERTCU1', 'Форма 1 ветеринарного сертификата ТС'),
#         ('LIC1', 'Форма 1 ветеринарного свидетельства'),
#         ('CERTCU2', 'Форма 2 ветеринарного сертификата ТС'),
#         ('LIC2', 'Форма 2 ветеринарного свидетельства'),
#         ('CERTCU3', 'Форма 3 ветеринарного сертификата ТС'),
#         ('LIC3', 'Форма 3 ветеринарного свидетельства'),
#         ('NOTE4', 'Форма 4 ветеринарной справки'),
#         ('CERT5I', 'Форма 5i ветеринарного сертификата'),
#         ('CERT61', 'Форма 6.1 ветеринарного сертификата'),
#         ('CERT62', 'Форма 6.2 ветеринарного сертификата'),
#         ('CERT63', 'Форма 6.3 ветеринарного сертификата'),
#         ('PRODUCTIVE', 'Форма производственного ветеринарного сертификата'),
#     )

#     VETDTYPE_CHOICES = (
#         ('INCOMING', 'Входящий ВСД'),
#         ('OUTGOING', 'Исходящий ВСД'),
#         ('PRODUCTIVE', 'Производственный ВСД'),
#         ('RETURNABLE', 'Возвратный ВСД'),
#         ('TRANSPORT', 'Транспортный ВСД'),
#     )

#     VETDSTATUS_CHOICES = (
#         ('CONFIRMED', 'Оформлен'),
#         ('WITHDRAWN', 'Аннулирован'),
#         ('UTILIZED', 'Погашен'),
#         ('FINALIZED', 'Закрыт'),
#     )

#     enterprise = models.ForeignKey(Enterprise, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='предприятие')
#     uuid = models.UUIDField(unique=True, db_index=True)
#     issue_date = models.DateField(verbose_name='дата оформления')
#     vetd_form = models.CharField(max_length=10, choices=VETDFORM_CHOICES, verbose_name='форма')
#     vetd_type = models.CharField(max_length=10, choices=VETDTYPE_CHOICES, verbose_name='тип')
#     vetd_status = models.CharField(max_length=10, choices=VETDSTATUS_CHOICES, verbose_name='статус')
#     is_finalized = models.BooleanField(default=False, verbose_name='закрыт')
#     date_updated = models.DateTimeField(null=True, blank=True, verbose_name='дата изменения статуса')
#     status_change = models.TextField(blank=True, verbose_name='информация об изменении статуса')

#     consignor_be_guid = models.UUIDField(null=True, blank=True)
#     consignor_ent_guid = models.UUIDField(null=True, blank=True)
#     consignor_enterprise = models.ForeignKey(Enterprise, null=True, blank=True, on_delete=models.SET_NULL, related_name='consignor_vetd_set', verbose_name='предприятие-отправитель')
#     consignee_be_guid = models.UUIDField(null=True, blank=True)
#     consignee_ent_guid = models.UUIDField(null=True, blank=True)
#     consignee_enterprise = models.ForeignKey(Enterprise, null=True, blank=True, on_delete=models.SET_NULL, related_name='consignee_vetd_set', verbose_name='предприятие-получатель')
#     producer_be_guid = models.UUIDField(null=True, blank=True)
#     producer_ent_guid = models.UUIDField(null=True, blank=True)
#     producer_enterprise = models.ForeignKey(Enterprise, null=True, blank=True, on_delete=models.SET_NULL, related_name='producer_vetd_set', verbose_name='предприятие-получатель')

#     product_type = models.IntegerField(choices=PRODUCT_TYPES, verbose_name='тип продукции')
#     product_guid = models.UUIDField(null=True, blank=True, verbose_name='продукция (GUID)')
#     product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT, verbose_name='продукция')
#     subproduct_guid = models.UUIDField(null=True, blank=True, verbose_name='вид продукции (GUID)')
#     subproduct = models.ForeignKey(SubProduct, null=True, blank=True, on_delete=models.PROTECT, verbose_name='вид продукции')
    
#     product_item_guid = models.UUIDField(null=True, blank=True, verbose_name='наименование продукции (GUID)')
#     product_item_name = models.CharField(max_length=255, verbose_name='наименование продукции')
#     product_item = models.ForeignKey(ProductItem, null=True, blank=True, on_delete=models.PROTECT, verbose_name='наименование продукции (справочник)')

#     volume = models.DecimalField(decimal_places=6, max_digits=15, verbose_name='объем')
#     unit = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name='ЕИ')

#     date_produced_1 = models.CharField(max_length=16, verbose_name='дата производства 1')
#     date_produced_2 = models.CharField(max_length=16, blank=True, verbose_name='дата производства 2')
#     date_produced = models.DateTimeField(verbose_name='дата производства')  # минимальная дата в интервале

#     date_expiry_1 = models.CharField(max_length=16, verbose_name='срок годности 1')
#     date_expiry_2 = models.CharField(max_length=16, blank=True, verbose_name='срок годности 2')
#     date_expiry = models.DateTimeField(verbose_name='срок годности')  # минимальная дата в интервале

#     is_perishable = models.BooleanField(verbose_name='скоропорт')

#     origin_country = models.CharField(max_length=255, null=True, blank=True, verbose_name='страна происхождения')
#     producer_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='наименование производителя')


#     @property
#     def date_produced_display(self):
#         return self.date_produced_1 + ( f' - {self.date_produced_2}' if self.date_produced_2 else '')
    
#     @property
#     def date_expiry_display(self):
#         return self.date_expiry_1 + ( f' - {self.date_expiry_2}' if self.date_expiry_2 else '')
    
#     def __str__(self):
#         return f'{self.uuid} {self.product_item_name} - {self.volume}'
    
#     class Meta:
#         verbose_name = 'ветеринарный документ'
#         verbose_name_plural = 'ветеринарные документы'
#         ordering = ['-date_updated']

STOCK_ENTRY_STATUS_CHOICES = (
    (100, 'Запись создана'),
    (101, 'Гашение ВС (импорт)'),
    (102, 'Гашение ВСД'),
    (103, 'Производство'),
    (104, 'Справка о здоровье дойных животных'),
    (105, 'Аннулирование ВСД или транзакции'),
    (106, 'Гашение бумажного ВСД'),
    (110, 'Объединение'),
    (120, 'Разделение'),
    (200, 'Внесены изменения'),
    (201, 'Запись аннулирована'),
    (202, 'Списание'),
    (203, 'Редактирование производства'),
    (204, 'Заключение по результатам ВСЭ'),
    (230, 'Обновление в результате присоединения'),
    (231, 'Обновление в результате присоединения'),
    (240, 'Обновление в результате отделения'),
    (250, 'Восстановление после удаления'),
    (260, 'Пометка на удаление'),
    (300, 'Перемещение в другую группу'),
    (400, 'Запись удалена'),
    (410, 'Удаление в результате объединения'),
    (420, 'Удаление в результате разделения'),
    (430, 'Удаление в результате присоединения'),
    )

class StockEntryMain(models.Model):
    '''Головная запись складского журнала с доп. информацией'''
    guid = models.UUIDField(unique=True, db_index=True)
    is_populated = models.BooleanField(default=False, verbose_name='данные заполнены')
    initial_status = models.IntegerField(null=True, blank=True, choices=STOCK_ENTRY_STATUS_CHOICES, verbose_name='статус версии')
    date_created = models.DateTimeField(null=True, blank=True, verbose_name='дата создания')
    initial_volume = models.DecimalField(decimal_places=6, max_digits=15, null=True, blank=True, verbose_name='объем')
    source_be_guid = models.UUIDField(null=True)
    source_be_name = models.TextField(max_length=255, blank=True, verbose_name='хозяйствующий субъект - источник')
    source_ent_guid = models.UUIDField(null=True)
    source_ent_name = models.TextField(max_length=255, blank=True, verbose_name='предприятие - источник')
    comment_important = models.BooleanField(default=False, verbose_name='комментарий важен')
    comment_text = models.TextField(max_length=255, blank=True, verbose_name='текст комментария')

    def __str__(self):
        return str(self.guid) + (f' {self.source_ent_name} - {self.initial_volume}' if self.is_populated else ' ???')
    
    class Meta:
        verbose_name = 'головная запись складского журнала'
        verbose_name_plural = 'головные записи складского журнала'
        ordering = ['-date_created']
    

class StockEntry(models.Model):
    '''Версии записей складского журнала'''
    main = models.ForeignKey(StockEntryMain, on_delete=models.PROTECT, verbose_name='головная запись')
    enterprise = models.ForeignKey(Enterprise, on_delete=models.PROTECT, verbose_name='предприятие')
    guid = models.UUIDField(db_index=True)
    uuid = models.UUIDField(unique=True, db_index=True)
    is_active = models.BooleanField(verbose_name='активная')
    is_last = models.BooleanField(verbose_name='последняя')
    status = models.IntegerField(choices=STOCK_ENTRY_STATUS_CHOICES, verbose_name='статус версии')
    date_created = models.DateTimeField(verbose_name='дата создания')
    date_updated = models.DateTimeField(verbose_name='дата обновления')
    previous_uuid = models.UUIDField(null=True, blank=True, verbose_name='UUID предыдущей версии')
    next_uuid = models.UUIDField(null=True, blank=True, verbose_name='UUID следующей версии')
    entry_number = models.BigIntegerField(verbose_name='номер записи')

    product_type = models.IntegerField(choices=PRODUCT_TYPES, verbose_name='тип продукции')
    product_guid = models.UUIDField(null=True, blank=True, verbose_name='продукция (GUID)')
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT, verbose_name='продукция')
    subproduct_guid = models.UUIDField(null=True, blank=True, verbose_name='вид продукции (GUID)')
    subproduct = models.ForeignKey(SubProduct, null=True, blank=True, on_delete=models.PROTECT, verbose_name='вид продукции')
    
    product_item_guid = models.UUIDField(null=True, blank=True, verbose_name='наименование продукции (GUID)')
    product_item_name = models.CharField(max_length=255, verbose_name='наименование продукции')
    product_item = models.ForeignKey(ProductItem, null=True, blank=True, on_delete=models.PROTECT, verbose_name='наименование продукции (справочник)')

    volume = models.DecimalField(decimal_places=6, max_digits=15, verbose_name='объем')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name='ЕИ')

    date_produced_1 = models.CharField(max_length=16, verbose_name='дата производства 1')
    date_produced_2 = models.CharField(max_length=16, blank=True, verbose_name='дата производства 2')
    date_produced = models.DateTimeField(verbose_name='дата производства')  # минимальная дата в интервале

    date_expiry_1 = models.CharField(max_length=16, verbose_name='срок годности 1')
    date_expiry_2 = models.CharField(max_length=16, blank=True, verbose_name='срок годности 2')
    date_expiry = models.DateTimeField(verbose_name='срок годности')  # минимальная дата в интервале

    is_perishable = models.BooleanField(verbose_name='скоропорт')

    origin_country = models.CharField(max_length=255, null=True, blank=True, verbose_name='страна происхождения')
    producer_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='наименование производителя')
    producer_guid = models.UUIDField(null=True, blank=True, verbose_name='предприятие-производитель (GUID)')
    producer = models.ForeignKey(Enterprise, null=True, blank=True, on_delete=models.PROTECT, related_name='produced_entries_set', verbose_name='предприятие-производитель')

    @property
    def date_produced_display(self):
        return self.date_produced_1 + ( f' - {self.date_produced_2}' if self.date_produced_2 else '')
    
    @property
    def date_expiry_display(self):
        return self.date_expiry_1 + ( f' - {self.date_expiry_2}' if self.date_expiry_2 else '')
    
    def days_to_expiry(self) -> int:
        date_to_compare = datetime.now(tz=TZ_MOSCOW)
        delta = self.date_expiry - date_to_compare
        return delta.days
    
    def date_expiry_group(self) -> str:
        EXPIRY_GROUPS = (
            (-1, 'Просрочена'),
            (0, 'Сегодня'),
            (7, 'Менее 7 дней'),
            (30, 'Менее 30 дней'),
        )
        days_to_expiry = self.days_to_expiry()
        for val, group_name in EXPIRY_GROUPS:
            if days_to_expiry <= val:
                return group_name
        return 'Более 30 дней'

    def date_expiry_class(self) -> str:
        CLASS_VALUES = (
            (-1, 'text-danger'),
            (7, 'text-warning'),
        )
        if not self.volume:
            return ''
        days_to_expiry = self.days_to_expiry()
        for val, class_name in CLASS_VALUES:
            if days_to_expiry <= val:
                return class_name
        return ''   

    def __str__(self):
        return f'{self.entry_number} {self.product_item_name} - {self.volume}'
    
    class Meta:
        verbose_name = 'запись складского журнала'
        verbose_name_plural = 'записи складского журнала'
        ordering = ['-date_updated']


class PackingType(models.Model):
    guid = models.UUIDField(unique=True)
    uuid = models.UUIDField(unique=True)
    name = models.CharField(max_length=255, verbose_name='название')
    global_id = models.CharField(max_length=2, verbose_name='идентификатор')

    # TODO implement native get_or_create logic https://docs.djangoproject.com/en/5.2/ref/models/querysets/#get-or-create
    @classmethod
    def get_or_create(cls, guid: str, uuid: str, name: str, global_id: str):
        try:
            packing_type = cls.objects.get(guid=guid)
        except ObjectDoesNotExist:
            packing_type = cls.objects.create(
                guid=guid,
                uuid=uuid,
                name=name,
                global_id=global_id
                )
        return packing_type

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'тип упаковки'
        verbose_name_plural = 'типы упаковки'
        ordering = ['name']


class Package(models.Model):
    LEVEL_CHOICES = (
        (1, 'Внутренний уровень'),
        (2, 'Потребительский уровень'),
        (3, 'Промежуточный уровень'),
        (4, 'Торговый уровень'),
        (5, 'Дополнительный уровень'),
        (6, 'Транспортный уровень'),
    )

    stock_entry = models.ForeignKey(StockEntry, on_delete=models.CASCADE, verbose_name='запись журнала')
    level = models.IntegerField(choices=LEVEL_CHOICES, verbose_name='уровень')
    packing_type = models.ForeignKey(PackingType, on_delete=models.PROTECT, verbose_name='тип упаковки')
    quantity = models.IntegerField(verbose_name='количество единиц')
    product_marks = models.TextField(blank=True, verbose_name='маркировка')

    def __str__(self):
        return f'{self.packing_type} {self.quantity}'

    class Meta:
        verbose_name = 'упаковка'
        verbose_name_plural = 'упаковки'
        ordering = ['level']


class StockEntryVetDocument(models.Model):
    stock_entry = models.ForeignKey(StockEntry, on_delete=models.CASCADE, verbose_name='запись журнала')
    uuid = models.UUIDField()

    
    def get_formatted_uuid(self):
        uuid_str = str(self.uuid).replace('-', '')
        return '-'.join(uuid_str[0+i:4+i] for i in range(0, len(uuid_str), 4))

    def __str__(self):
        return str(self.uuid)
    
    class Meta:
        verbose_name = 'вет. документ'
        verbose_name_plural = 'вет. документы'


# class StockEntryComment(models.Model):
#     stock_entry_guid = models.UUIDField(unique=True, db_index=True, verbose_name='GUID записи журнала')
#     important = models.BooleanField(verbose_name='важно')
#     text = models.CharField(max_length=255, verbose_name='текст')

#     def __str__(self):
#         return self.text
    
#     class Meta:
#         verbose_name = 'комментарий записи журнала'
#         verbose_name_plural = 'комментарии записи журнала'