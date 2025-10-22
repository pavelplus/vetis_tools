from datetime import datetime

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

    def __str__(self):
        return f'{self.name} ({self.address})'
    
    class Meta:
        verbose_name = 'предприятие'
        verbose_name_plural = 'предприятия'
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
    producer_guid = models.UUIDField(verbose_name='производитель (GUID)')
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

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'единица измерения'
        verbose_name_plural = 'единицы измерения'
        ordering = ['name']


class ComplexDate():

    def __init__(self, year: int, month: int = None, day: int = None, hour: int = None, minute: int = None):
        self._year = year
        self._month = month
        self._day = day
        self._hour = hour
        self._minute = minute

        if not self.is_valid():
            raise ValueError()
        
        self.date_str = self.to_string()


    @classmethod
    def from_string(cls, str: str):
        year = None
        month = None
        day = None
        hour = None
        minute = None
        
        try:
            date, time = str.split(' ')
        except:
            date = str
            time = None
        
        if date:
            ymd = date.split('-')
            if len(ymd) >= 1:
                year = int(ymd[0])
            if len(ymd) >= 2:
                month = int(ymd[1])
            if len(ymd) >= 3:
                day = int(ymd[2])
        
        if time:
            hm = time.split(':')
            if len(hm) >= 1:
                hour = int(hm[0])
            if len(hm) >= 2:
                minute = int(hm[1])

        return cls(year, month, day, hour, minute)
    

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
        elif what == 'minute':
            self._minute = value
        
        if not self.is_valid():
            raise ValueError()
        
        self.date_str = self.to_string()

        return self


    def to_string(self) -> str:
        date_values = [f'{self._year:0>4}']
        time_str = ''
        if self._month is not None:
            date_values.append(f'{self._month:0>2}')
            if self._day is not None:
                date_values.append(f'{self._day:0>2}')
                if self._hour is not None:
                    time_str += f' {self._hour:0>2}'
                    if self._minute is not None:
                        time_str += f':{self._minute:0>2}'

        return f'{'-'.join(date_values)}{time_str}'
    

    def to_datetime(self) -> datetime:
        return datetime(
            year=self._year,
            month=self._month if self._month is not None else 1,
            day=self._day if self._day is not None else 1,
            hour=self._hour if self._hour is not None else 0,
            minute=self._minute if self._minute is not None else 0
        )
    

    def is_valid(self):
        if self._year is not None and (self._year < 1 or self._year > 9999):
            return False
        if self._month is not None and (self._month < 1 or self._month > 12):
            return False
        if self._day is not None and (self._day < 1 or self._day > 31):
            return False
        if self._hour is not None and (self._hour < 0 or self._hour > 23):
            return False
        if self._minute is not None and (self._minute < 0 or self._minute > 59):
            return False
        
        return True


class StockEntry(models.Model):
    STATUS_CHOICES = (
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

    enterprise = models.ForeignKey(Enterprise, on_delete=models.PROTECT, verbose_name='предприятие')
    guid = models.UUIDField(db_index=True)
    uuid = models.UUIDField(unique=True, db_index=True)
    is_active = models.BooleanField(verbose_name='активная')
    is_last = models.BooleanField(verbose_name='последняя')
    status = models.IntegerField(choices=STATUS_CHOICES, verbose_name='статус версии')
    date_created = models.DateTimeField(verbose_name='дата создания')
    date_updated = models.DateTimeField(verbose_name='дата обновления')
    previous_uuid = models.UUIDField(null=True, blank=True, verbose_name='UUID предыдущей версии')
    next_uuid = models.UUIDField(null=True, blank=True, verbose_name='UUID следующей версии')
    entry_number = models.IntegerField(verbose_name='номер записи')

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

    def __str__(self):
        return f'{self.entry_number} {self.product_item_name} - {self.volume}'
    
    class Meta:
        verbose_name = 'запись складского журнала'
        verbose_name_plural = 'записи складского журнала'
        ordering = ['-date_expiry']


class PackingType(models.Model):
    guid = models.UUIDField(unique=True)
    uuid = models.UUIDField(unique=True)
    name = models.CharField(max_length=2, verbose_name='идентификатор')
    globalID = models.CharField(max_length=255, verbose_name='название')

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
    
    stock_entry = models.ForeignKey(StockEntry, on_delete=models.PROTECT, verbose_name='запись журнала')
    level = models.IntegerField(choices=LEVEL_CHOICES, verbose_name='уровень')
    packing_type = models.ForeignKey(PackingType, on_delete=models.PROTECT, verbose_name='тип упаковки')
    quantity = models.IntegerField(verbose_name='количество единиц')
    product_marks = models.TextField(blank=True, verbose_name='маркировка')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'упаковка'
        verbose_name_plural = 'упаковки'
        ordering = ['level']