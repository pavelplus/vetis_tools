import requests
import logging
from time import sleep
from datetime import datetime, timedelta, date
from decimal import Decimal
import xml.etree.ElementTree as ET

from celery import shared_task, states

from django.core.exceptions import ObjectDoesNotExist, BadRequest
from django.db import transaction

from .models import *
from .xml.build_xml import *


logger = logging.getLogger('vetis_tools')

# PROD
ENDPOINTS_PROD = {
    'ProductService': 'https://api.vetrf.ru/platform/services/2.1/ProductService',
    'EnterpriseService': 'https://api.vetrf.ru/platform/services/2.1/EnterpriseService',
    'DictionaryService': 'https://api.vetrf.ru/platform/services/2.1/DictionaryService',
    'ApplicationManagementService': 'https://api.vetrf.ru/platform/services/2.1/ApplicationManagementService',
}

# TEST
ENDPOINTS_TEST = {
    'ProductService': 'https://api2.vetrf.ru:8002/platform/services/2.1/ProductService',
    'EnterpriseService': 'https://api2.vetrf.ru:8002/platform/services/2.1/EnterpriseService',
    'DictionaryService': 'https://api2.vetrf.ru:8002/platform/services/2.1/DictionaryService',
    'ApplicationManagementService': 'https://api2.vetrf.ru:8002/platform/services/2.1/ApplicationManagementService',
}


def get_xml_text(element: ET.Element, path: str, default: str = 'RAISE_ERROR') -> str:
    """Find element, return it's text. If element not found - return default or raise error."""
    found_element = element.find(path, NAMESPACES)

    if found_element is not None:
        return found_element.text
    elif default == 'RAISE_ERROR':
        raise RuntimeError(f'Не найден запрошенный элемент: {path}')
        
    return default


def process_complex_date(complex_date_interval_xml: ET.Element) -> tuple[ComplexDate, ComplexDate]:
    """Returns [complex_date_1, complex_date_2]"""

    complex_date_1_xml = complex_date_interval_xml.find('vd:firstDate', NAMESPACES)
    year = int(get_xml_text(complex_date_1_xml, 'dt:year'))
    month = int(get_xml_text(complex_date_1_xml, 'dt:month'))
    complex_date_1 = ComplexDate(year=year, month=month)
    day_text = get_xml_text(complex_date_1_xml, 'dt:day', default='')
    if day_text:
        complex_date_1.update('day', int(day_text))
        hour_text = get_xml_text(complex_date_1_xml, 'dt:hour', default='')
        if hour_text:
            complex_date_1.update('hour', int(hour_text))

    complex_date_2_xml = complex_date_interval_xml.find('vd:secondDate', NAMESPACES)
    if complex_date_2_xml is not None:
        year = int(get_xml_text(complex_date_2_xml, 'dt:year'))
        month = int(get_xml_text(complex_date_2_xml, 'dt:month'))
        complex_date_2 = ComplexDate(year=year, month=month)
        day_text = get_xml_text(complex_date_2_xml, 'dt:day', default='')
        if day_text:
            complex_date_2.update('day', int(day_text))
            hour_text = get_xml_text(complex_date_2_xml, 'dt:hour', default='')
            if hour_text:
                complex_date_2.update('hour', int(hour_text))
    else:
        complex_date_2 = None
    
    return (complex_date_1, complex_date_2)


def send_soap_request(soap_request: AbstractRequest, credentials: VetisCredentials):
    headers = {
        'Content-Type': 'text/html;charset=UTF-8',
        'SOAPAction': soap_request.soap_action,
    }
    body = soap_request.get_xml()

    endpoint_url = ENDPOINTS_PROD[soap_request.endpoint_name] if credentials.is_productive else ENDPOINTS_TEST[soap_request.endpoint_name]

    for try_num in range(3):

        if try_num:
            sleep(5*try_num)

        try:
            response = requests.post(
                    url=endpoint_url,
                    auth=(credentials.login, credentials.password),
                    headers=headers,
                    data=body
                )
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            response = None
        
        if response is not None:
            break
        else:
            logger.warning(f'Ошибка подключения (попытка {try_num + 1})')

    if response is None:
        raise RuntimeError('Не удалось установить соединение для отправки soap запроса')

    record = ApiRequestsHistoryRecord()
    record.soap_action = soap_request.soap_action
    record.soap_request = soap_request.get_xml()
    record.comment = f'{credentials.name} {endpoint_url}'
    record.response_status_code = response.status_code
    record.response_body = response.text
    record.save()

    # Cleanup history table
    ApiRequestsHistoryRecord.objects.filter(datetime__lt=(datetime.now(tz=TZ_MOSCOW)-timedelta(days=7))).delete()
    
    return response


def send_2step_soap_request(soap_request: AbstractRequest, credentials: VetisCredentials):

    logger.debug('Отправка двухэтапного запроса. Этап 1.')

    response = send_soap_request(soap_request, credentials)

    if response.status_code != 200:
        raise RuntimeError(f'Ошибка запроса ({response.status_code}): {response.reason}')

    result_xml = ET.fromstring(response.text)

    response_xml = result_xml.find('./soapenv:Body/apldef:submitApplicationResponse', NAMESPACES)

    # status = response_xml.find('apl:application/apl:status', NAMESPACES).text
    status = get_xml_text(response_xml, 'apl:application/apl:status')

    logger.debug(f'Статус ответа: {status}')

    if status != 'ACCEPTED':
        raise RuntimeError(f'Ошибка обработки запроса ({status})')
    
    # application_id = response_xml.find('apl:application/apl:applicationId', NAMESPACES).text
    application_id = get_xml_text(response_xml, 'apl:application/apl:applicationId')

    application_result_request = ReceiveApplicationResultRequest(api_key=credentials.api_key, issuer_id=credentials.issuer_id, application_id=application_id)

    status = '---'

    for try_num in range(6):
        sleep(3 + try_num*10)

        logger.debug(f'Получение ответа. Попытка {try_num + 1}...')
        
        response = send_soap_request(application_result_request, credentials)

        if response.status_code != 200:
            raise RuntimeError(f'Ошибка запроса при ожидании двухэтапного ответа ({response.status_code}): {response.reason}')
        
        result_xml = ET.fromstring(response.text)

        response_xml = result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse', NAMESPACES)

        # status = response_xml.find('apl:application/apl:status', NAMESPACES).text
        status = get_xml_text(response_xml, 'apl:application/apl:status')

        logger.debug(f'Статус в ответе: {status}')

        if status == 'COMPLETED':
            return response
        elif status == 'REJECTED':
            raise RuntimeError('Запрос отклонен (REJECTED)')

    raise RuntimeError(f'Таймаут ожидания результата обработки. Последний полученный статус запроса: {status}')


@shared_task(bind=True)
def test_task(this_task):

    logger.debug(f'type of this_task {type(this_task)}, {this_task}')
    
    for i in range(0, 5):
        this_task.update_state(state='PROGRESS', meta={'info': f'Processing test task {i+1}...'})
        logger.debug(f'Processing test task {i+1}...')
        sleep(1.0)
    logger.debug('Тестовая задача завершена')
    # raise RuntimeError("Error example")
    return 'Тестовая задача завершена успешно'


@shared_task(bind=True)
def maintenance_task(this_task, credentials_id: int):
    raise RuntimeError('Нет активной задачи')

    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Не обнаружены параметры подключения')
    
    for item in ITEMS:
        item_id = item[0]
        group_name = item[1]
        print(f'{item_id}, {group_name}')
        assort_group = AssortGroup.objects.get(name=group_name)
        ProductItem.objects.filter(id=item_id).update(assort_group=assort_group)

    return 'Задача успешно завершена'


@shared_task(bind=True)
def reload_enterprises_task(this_task, credentials_id: int, business_entity_id: int):
    return reload_enterprises(this_task, credentials_id, business_entity_id)


def reload_enterprises(this_task, credentials_id: int, business_entity_id: int):
    try:
        business_entity = BusinessEntity.objects.get(id=business_entity_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Хозяйствующий субъект не найден')
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Не обнаружены параметры подключения')
    
    list_count = 1000
    list_offset = 0

    response_xml_pages = []

    logger.debug('Загружаем информацию о предприятиях хозяйствующего субъекта...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': 'Загружаем информацию о предприятиях хозяйствующего субъекта...'})

    while True: # repeat if has pages

        logger.debug(f'Запрос c list_offset={list_offset}')

        soap_request = ActivityLocationListRequest(business_entity.guid, list_count, list_offset)

        response = send_soap_request(soap_request, credentials)

        if response.status_code != 200:
            raise RuntimeError(f'Ошибка запроса ({response.status_code}): {response.reason}')
        
        result_xml = ET.fromstring(response.text)

        response_xml_pages.append(result_xml.find('./soapenv:Body/ws:getActivityLocationListResponse/dt:activityLocationList', NAMESPACES))

        total = int(response_xml_pages[-1].get('total'))

        if not list_offset:
            logger.debug(f'Всего предприятий: {total}')
        
        if total > list_offset + list_count:
            list_offset += list_count
        else:
            break

    logger.debug('Обновляем информацию о предприятиях хозяйствующего субъекта...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': 'Обновляем информацию о предприятиях хозяйствующего субъекта...'})

    with transaction.atomic():

        business_entity.enterprise_set.update(is_active=False)

        for response_xml in response_xml_pages:

            for enterprise_xml in response_xml.findall('dt:location/dt:enterprise', NAMESPACES):
                try:
                    # enterprise = Enterprise.objects.get(guid=enterprise_xml.find('bs:guid', NAMESPACES).text)
                    enterprise = Enterprise.objects.get(guid=get_xml_text(enterprise_xml, 'bs:guid'))
                except:
                    enterprise = Enterprise()
                
                enterprise.business_entity = business_entity
                enterprise.guid = get_xml_text(enterprise_xml, 'bs:guid')
                enterprise.uuid = get_xml_text(enterprise_xml, 'bs:uuid')
                enterprise.type = int(get_xml_text(enterprise_xml, 'dt:type'))
                enterprise.name = get_xml_text(enterprise_xml, 'dt:name')
                enterprise.address = get_xml_text(enterprise_xml, 'dt:address/dt:addressView')
                enterprise.is_active = get_xml_text(enterprise_xml, 'bs:active') == 'true'

                enterprise_numbers = []

                for enterprise_number in enterprise_xml.findall('dt:numberList/dt:enterpriseNumber', NAMESPACES):
                    enterprise_numbers.append(enterprise_number.text)

                enterprise.number_list = ', '.join(enterprise_numbers)

                enterprise.save()

        # /for pages
    # /transaction.atomic
    
    return 'Предприятия хозяйствующего субъекта успешно обновлены.'


def get_or_load_product_by_guid(credentials: VetisCredentials, product_guid: str, update: bool = False) -> Product:
    """
    Retrieves product from DB and loads from Vetis if not found.
    If update == True updates existing record from Vetis.
    """

    try:
        product = Product.objects.get(guid=product_guid)
    except ObjectDoesNotExist:
        product = None

    if product is not None and not update:
        return product

    if product is None:
        product = Product()        

    logger.debug(f'Загружаем тип продукции (product): {product_guid}')

    soap_request = ProductByGuidRequest(product_guid)
    response = send_soap_request(soap_request, credentials)

    if response is None:
        raise BadRequest()
    
    if response.status_code != 200:
        raise BadRequest()
    
    result_xml = ET.fromstring(response.text)

    product_xml = result_xml.find('./soapenv:Body/ws:getProductByGuidResponse/dt:product', NAMESPACES)

    # guid
    # uuid
    # name
    # code
    # product_type

    product.guid = get_xml_text(product_xml, 'bs:guid')
    product.uuid = get_xml_text(product_xml, 'bs:uuid')
    product.name = get_xml_text(product_xml, 'dt:name')
    product.code = get_xml_text(product_xml, 'dt:code', default='')
    product.product_type = int(get_xml_text(product_xml, 'dt:productType'))

    product.save()

    return product


def get_or_load_subproduct_by_guid(credentials: VetisCredentials, subproduct_guid: str, update: bool = False) -> SubProduct:
    """
    Retrieves subproduct from DB and loads from Vetis if not found.
    If update == True updates existing record from Vetis.
    """

    try:
        subproduct = SubProduct.objects.get(guid=subproduct_guid)
    except ObjectDoesNotExist:
        subproduct = None  

    if subproduct is not None and not update:
        return subproduct

    if subproduct is None:
        subproduct = SubProduct()

    logger.debug(f'Загружаем продукцию (subproduct): {subproduct_guid}')

    soap_request = SubproductByGuidRequest(subproduct_guid)
    response = send_soap_request(soap_request, credentials)

    if response is None:
        raise BadRequest()
    
    if response.status_code != 200:
        raise BadRequest()
    
    result_xml = ET.fromstring(response.text)

    subproduct_xml = result_xml.find('./soapenv:Body/ws:getSubProductByGuidResponse/dt:subProduct', NAMESPACES)

    # guid
    # uuid
    # name
    # code
    # product_guid
    # product

    subproduct.guid = get_xml_text(subproduct_xml, 'bs:guid')
    subproduct.uuid = get_xml_text(subproduct_xml, 'bs:uuid')
    subproduct.name = get_xml_text(subproduct_xml, 'dt:name')
    subproduct.code = get_xml_text(subproduct_xml, 'dt:code', default='')
    subproduct.product_guid = get_xml_text(subproduct_xml, 'dt:productGuid')

    product = get_or_load_product_by_guid(credentials=credentials, product_guid=subproduct.product_guid)

    subproduct.product = product

    subproduct.save()

    return subproduct


def fill_product_item_from_xml(product_item: ProductItem, product_item_xml: ET.Element, credentials: VetisCredentials):

    # guid
    # uuid
    # is_active
    # name
    # gtin
    # product_type
    # product_guid
    # product
    # subproduct_guid
    # subproduct
    # is_gost
    # gost
    # producer_guid
    # producer

    product_item.guid = get_xml_text(product_item_xml, 'bs:guid')
    product_item.uuid = get_xml_text(product_item_xml, 'bs:uuid')
    product_item.is_active = get_xml_text(product_item_xml, 'bs:active') == 'true'
    product_item.name = get_xml_text(product_item_xml, 'dt:name', default='')
    product_item.gtin = get_xml_text(product_item_xml, 'dt:globalID', default='')

    product_item.product_type = int(get_xml_text(product_item_xml, 'dt:productType'))
    product_item.product_guid = get_xml_text(product_item_xml, 'dt:product/bs:guid')
    product_item.product = get_or_load_product_by_guid(credentials=credentials, product_guid=product_item.product_guid)
    product_item.subproduct_guid = get_xml_text(product_item_xml, 'dt:subProduct/bs:guid')
    product_item.subproduct = get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=product_item.subproduct_guid)

    if not product_item.name:
        product_item.name = product_item.subproduct.name

    product_item.is_gost = get_xml_text(product_item_xml, 'dt:correspondsToGost') == 'true'
    if product_item.is_gost:
        product_item.gost = get_xml_text(product_item_xml, 'dt:gost')

    producer_guid_xml = product_item_xml.find('dt:producer/bs:guid', NAMESPACES)
    if producer_guid_xml is not None:
        product_item.producer_guid = producer_guid_xml.text
        producer = BusinessEntity.objects.filter(guid=product_item.producer_guid).first()
        if producer is not None:
            product_item.producer = producer

    product_item.save()


def get_or_load_product_item_by_guid(credentials: VetisCredentials, product_item_guid: str, update: bool = False) -> ProductItem:
    """
    Retrieves product item from DB and loads from Vetis if not found.
    If update == True updates existing record from Vetis.
    """

    try:
        product_item = ProductItem.objects.get(guid=product_item_guid)
    except ObjectDoesNotExist:
        product_item = None

    if product_item is not None and not update:
        return product_item

    if product_item is None:
        product_item = ProductItem()        

    logger.debug(f'Загружаем наименование продукции (product item): {product_item_guid}')

    soap_request = ProductItemByGuidRequest(product_item_guid)
    response = send_soap_request(soap_request, credentials)

    if response is None:
        raise BadRequest()
    
    if response.status_code != 200:
        raise BadRequest()
    
    result_xml = ET.fromstring(response.text)

    product_item_xml = result_xml.find('./soapenv:Body/ws:getProductItemByGuidResponse/dt:productItem', NAMESPACES)

    fill_product_item_from_xml(product_item, product_item_xml, credentials)

    return product_item


def get_or_create_dummy_product_item(product_item_name: str, subproduct: SubProduct) -> ProductItem:

    product_item = ProductItem.objects.filter(subproduct=subproduct, name=product_item_name).first()

    if product_item is None:
    
        product_item = ProductItem()

        product_item.is_active = True
        product_item.name = product_item_name

        product_item.product_type = subproduct.product.product_type
        product_item.product_guid = subproduct.product.guid
        product_item.product = subproduct.product
        product_item.subproduct_guid = subproduct.guid
        product_item.subproduct = subproduct

        product_item.is_gost = False

        product_item.save()

    return product_item


def get_or_load_unit_by_guid(credentials: VetisCredentials, unit_guid: str, update: bool = False) -> SubProduct:
    """
    Retrieves unit from DB and loads from Vetis if not found.
    If update == True updates existing record from Vetis.
    """

    try:
        unit = Unit.objects.get(guid=unit_guid)
    except ObjectDoesNotExist:
        unit = None  

    if unit is not None and not update:
        return unit

    if unit is None:
        unit = Unit()

    logger.debug(f'Загружаем единицу измерения: {unit_guid}')

    soap_request = UnitByGuidRequest(unit_guid)
    response = send_soap_request(soap_request, credentials)

    if response is None:
        raise BadRequest()
    
    if response.status_code != 200:
        raise BadRequest()
    
    result_xml = ET.fromstring(response.text)

    unit_xml = result_xml.find('./soapenv:Body/ws:getUnitByGuidResponse/dt:unit', NAMESPACES)

    # guid
    # name

    unit.guid = get_xml_text(unit_xml, 'bs:guid')
    unit.name = get_xml_text(unit_xml, 'dt:name')

    unit.save()

    return unit


def get_or_load_business_entity_info_by_guid(credentials: VetisCredentials, business_entity_guid: str, update: bool = False) -> BusinessEntityInfo:
    try:
        be_info = BusinessEntityInfo.objects.get(guid=business_entity_guid)
    except ObjectDoesNotExist:
        be_info = None

    if be_info is not None and not update:
        return be_info

    if be_info is None:
        be_info = BusinessEntityInfo()

    logger.debug(f'Заружем информацию о хозяйствующем субъекте: {business_entity_guid}')
    
    soap_request = BusinessEntityByGuidRequest(business_entity_guid)
    response = send_soap_request(soap_request, credentials)

    result_xml = ET.fromstring(response.text)

    business_entity_xml = result_xml.find('./soapenv:Body/ws:getBusinessEntityByGuidResponse/dt:businessEntity', NAMESPACES)

    be_info.guid = business_entity_guid
    be_info.uuid = get_xml_text(business_entity_xml, 'bs:uuid')

    # name_xml = business_entity_xml.find('dt:name', NAMESPACES)
    # if name_xml is None:
    #     name_xml = business_entity_xml.find('dt:fullName', NAMESPACES)
    # if name_xml is None:
    #     name_xml = business_entity_xml.find('dt:fio', NAMESPACES)

    # if name_xml is None:
    #     be_info.name = str(business_entity_guid)
    # else:
    #     be_info.name = name_xml.text

    be_info.name = (
        get_xml_text(business_entity_xml, 'dt:name', default='')
        or get_xml_text(business_entity_xml, 'dt:fullName', default='')
        or get_xml_text(business_entity_xml, 'dt:fio', default='')
        or str(business_entity_guid)
    )

    # inn_xml = business_entity_xml.find('dt:inn', NAMESPACES)
    # if inn_xml is not None:
    #     be_info.inn = inn_xml.text

    be_info.inn = get_xml_text(business_entity_xml, 'dt:inn', default='')
    
    be_info.save()

    return be_info


def get_or_load_enterprise_info_by_guid(credentials: VetisCredentials, enterprise_guid: str, update: bool = False) -> EnterpriseInfo:
    try:
        ent_info = EnterpriseInfo.objects.get(guid=enterprise_guid)
    except ObjectDoesNotExist:
        ent_info = None

    if ent_info is not None and not update:
        return ent_info

    if ent_info is None:
        ent_info = EnterpriseInfo()
    
    logger.debug(f'Загружаем информацию о предприятии: {enterprise_guid}')

    soap_request = EnterpriseByGuidRequest(enterprise_guid)
    response = send_soap_request(soap_request, credentials)

    result_xml = ET.fromstring(response.text)

    enterprise_xml = result_xml.find('./soapenv:Body/ws:getEnterpriseByGuidResponse/dt:enterprise', NAMESPACES)

    ent_info.guid = enterprise_guid
    ent_info.uuid = get_xml_text(enterprise_xml, 'bs:uuid')
    ent_info.name = get_xml_text(enterprise_xml, 'dt:name')
    ent_info.address = get_xml_text(enterprise_xml, 'dt:address/dt:addressView', default='')

    # address_xml = enterprise_xml.find('dt:address/dt:addressView', NAMESPACES)
    # if address_xml is not None:
    #     ent_info.address = address_xml.text
    
    # owner_guid = enterprise_xml.find('dt:owner/bs:guid', NAMESPACES).text  # В ОТВЕТЕ НЕТ ИНФЫ О ХС!!!
    # ent_info.business_entity = get_or_load_business_entity_info_by_guid(credentials, owner_guid)

    ent_info.save()

    return ent_info


def get_or_load_vet_document_by_uuid(credentials: VetisCredentials, enterprise: Enterprise, initiator_login: str, vetd_uuid: str, update: bool = False) -> VetDocument:
    try:
        vet_document = VetDocument.objects.get(uuid=vetd_uuid)
    except ObjectDoesNotExist:
        vet_document = None

    if vet_document is not None and not update:
        return vet_document

    if vet_document is None:
        vet_document = VetDocument()

    soap_request = GetVetDocumentByUuidRequest(
        enterprise_guid=enterprise.guid,
        vet_document_uuid=vetd_uuid,
        api_key=credentials.api_key,
        service_id=credentials.service_id,
        issuer_id=credentials.issuer_id,
        initiator_login=initiator_login
    )

    response = send_2step_soap_request(soap_request, credentials)

    result_xml = ET.fromstring(response.text)

    response_xml = result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse/apl:application/apl:result/merc:getVetDocumentByUuidResponse/vd:vetDocument', NAMESPACES)

    if response_xml is None:
        raise RuntimeError('Ошибка парсинга ответа при загрузке вет. документа: не найден вет. документ')
    
    fill_vet_document_from_xml(vet_document, response_xml, credentials)

    return vet_document


@shared_task(bind=True)
def reload_product_subproduct_task(this_task, credentials_id: int):
    return reload_product_subproduct(this_task, credentials_id)


def reload_product_subproduct(this_task, credentials_id: int):
    """Update existing product and subproduct records form Vetis"""

    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Не обнаружены параметры подключения')

    for product in Product.objects.all():
        get_or_load_product_by_guid(credentials=credentials, product_guid=product.guid, update=True)
    
    for subproduct in SubProduct.objects.all():
        get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=subproduct.guid, update=True)

    return 'Списки продукция и вид продукции обновлены.'


@shared_task(bind=True)
def reload_product_items_task(this_task, credentials_id: int, business_entity_id: int):
    return reload_product_items(this_task, credentials_id, business_entity_id)


def reload_product_items(this_task, credentials_id: int, business_entity_id: int):
    try:
        business_entity = BusinessEntity.objects.get(id=business_entity_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Хозяйствующий субъект не найден')
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Не обнаружены параметры подключения')
    
    list_count = 1000
    list_offset = 0

    response_xml_pages = []

    logger.debug('Загружаем наименования продукции хозяйствующего субъекта...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': 'Загружаем наименования продукции хозяйствующего субъекта...'})

    while True: # repeat if has pages

        logger.debug(f'Запрос c list_offset={list_offset}')

        soap_request = ProductItemListRequest(business_entity.guid, list_count, list_offset)

        response = send_soap_request(soap_request, credentials)

        if response.status_code != 200:
            raise RuntimeError(f'Ошибка запроса ({response.status_code}): {response.reason}')
        
        result_xml = ET.fromstring(response.text)

        response_xml_pages.append(result_xml.find('./soapenv:Body/ws:getProductItemListResponse/dt:productItemList', NAMESPACES))

        total = int(response_xml_pages[-1].get('total'))

        if not list_offset:
            logger.debug(f'Всего наименований: {total}')
        
        if total > list_offset + list_count:
            list_offset += list_count
        else:
            break

    logger.debug('Заполняем наименования продукции хозяйствующего субъекта...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': 'Заполняем наименования продукции хозяйствующего субъекта...'})

    with transaction.atomic():

        ProductItem.objects.filter(producer_guid=business_entity.guid).update(is_active=False)

        for response_xml in response_xml_pages:

            for product_item_xml in response_xml.findall('dt:productItem', NAMESPACES):
                try:
                    product_item = ProductItem.objects.get(guid=product_item_xml.find('bs:guid', NAMESPACES).text)
                except:
                    product_item = ProductItem()

                fill_product_item_from_xml(product_item, product_item_xml, credentials)

        # /for pages
    # /transaction.atomic

    # fill product ids
    for product_item in ProductItem.objects.filter(product__isnull=True):
        product = get_or_load_product_by_guid(credentials=credentials, product_guid=product_item.product_guid)
        product_item.product = product
        product_item.save()

    # fill subproduct ids
    for product_item in ProductItem.objects.filter(subproduct__isnull=True):
        subproduct = get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=product_item.subproduct_guid)
        product_item.subproduct = subproduct
        product_item.save()

    return f'Список продукции обновлен. Всего: {total}'


def fill_vet_document_from_xml(vet_document: VetDocument, vet_document_xml: ET.Element, credentials: VetisCredentials):

    # uuid
    # issue_date
    # vetd_form
    # vetd_type
    # vetd_status
    # is_finalized
    # date_updated

    # vet_document.enterprise = enterprise
    vet_document.uuid = get_xml_text(vet_document_xml, 'bs:uuid')
    logger.debug(f'Заполняем вет документ uuid={vet_document.uuid}')
    vet_document.issue_date = date.fromisoformat(get_xml_text(vet_document_xml, 'vd:issueDate'))
    vet_document.vetd_form = get_xml_text(vet_document_xml, 'vd:vetDForm')
    vet_document.vetd_type = get_xml_text(vet_document_xml, 'vd:vetDType')
    vet_document.vetd_status = get_xml_text(vet_document_xml, 'vd:vetDStatus')
    vet_document.is_finalized = get_xml_text(vet_document_xml, 'vd:finalized', default='false') == 'true'
    date_updated_text = get_xml_text(vet_document_xml, 'vd:lastUpdateDate', default='')
    if date_updated_text:
        vet_document.date_updated = datetime.fromisoformat(date_updated_text)
    
    # status_change

    vet_document.status_change = ''

    for status_change_xml in vet_document_xml.findall('vd:statusChange', NAMESPACES):
        status = get_xml_text(status_change_xml, 'vd:status')
        fio = get_xml_text(status_change_xml, 'vd:specifiedPerson/vd:fio')
        actual_date = datetime.fromisoformat(get_xml_text(status_change_xml, 'vd:actualDateTime'))
        if vet_document.status_change:
            vet_document.status_change += '\n'
        vet_document.status_change += f'{status} - {fio} - {actual_date.strftime('%Y-%m-%d %H:%M:%S')}'

    # consignor_be_guid
    # consignor_be_name
    # consignor_ent_guid
    # consignor_ent_name
    # consignee_be_guid
    # consignee_be_name
    # consignee_ent_guid
    # consignee_ent_name
    # producer_be_guid
    # producer_be_name
    # producer_ent_guid
    # producer_ent_name

    if vet_document.vetd_type not in ['TRANSPORT', 'RETURNABLE', 'PRODUCTIVE']:
        raise RuntimeError(f'Неизвестный тип ветеринарного документа {vet_document.vetd_type}. uuid={vet_document.uuid}')
    
    if vet_document.vetd_type in ['TRANSPORT', 'RETURNABLE']:
        vet_document.consignor_be_guid = get_xml_text(vet_document_xml, 'vd:certifiedConsignment/vd:consignor/dt:businessEntity/bs:guid')
        vet_document.consignor_be_name = str(get_or_load_business_entity_info_by_guid(credentials, vet_document.consignor_be_guid))
        vet_document.consignor_ent_guid = get_xml_text(vet_document_xml, 'vd:certifiedConsignment/vd:consignor/dt:enterprise/bs:guid')
        vet_document.consignor_ent_name = str(get_or_load_enterprise_info_by_guid(credentials, vet_document.consignor_ent_guid))

        vet_document.consignee_be_guid = get_xml_text(vet_document_xml, 'vd:certifiedConsignment/vd:consignee/dt:businessEntity/bs:guid')
        vet_document.consignee_be_name = str(get_or_load_business_entity_info_by_guid(credentials, vet_document.consignee_be_guid))
        vet_document.consignee_ent_guid = get_xml_text(vet_document_xml, 'vd:certifiedConsignment/vd:consignee/dt:enterprise/bs:guid')
        vet_document.consignee_ent_name = str(get_or_load_enterprise_info_by_guid(credentials, vet_document.consignee_ent_guid))

        batch_xml = vet_document_xml.find('vd:certifiedConsignment/vd:batch', NAMESPACES)

    if vet_document.vetd_type == 'PRODUCTIVE':
        # vet_document.producer_be_guid = get_xml_text(vet_document_xml, 'vd:certifiedBatch/vd:batch/vd:origin/vd:producer/dt:enterprise/bs:guid')
        # vet_document.producer_be_name = get_or_load_business_entity_info_by_guid(credentials, vet_document.producer_be_guid)
        vet_document.producer_ent_guid = get_xml_text(vet_document_xml, 'vd:certifiedBatch/vd:batch/vd:origin/vd:producer/dt:enterprise/bs:guid')
        vet_document.producer_ent_name = str(get_or_load_enterprise_info_by_guid(credentials, vet_document.producer_ent_guid))

        producer_ent = Enterprise.objects.filter(guid=vet_document.producer_ent_guid).first()
        if producer_ent is not None:
            vet_document.producer_be_guid = producer_ent.business_entity.guid
            vet_document.producer_be_name = str(producer_ent.business_entity)

        batch_xml = vet_document_xml.find('vd:certifiedBatch/vd:batch', NAMESPACES)

    # product_type
    # product_guid
    # product
    # subproduct_guid
    # subproduct

    vet_document.product_type = int(get_xml_text(batch_xml, 'vd:productType'))
    vet_document.product_guid = get_xml_text(batch_xml, 'vd:product/bs:guid')
    vet_document.product = get_or_load_product_by_guid(credentials, vet_document.product_guid)
    vet_document.subproduct_guid = get_xml_text(batch_xml, 'vd:subProduct/bs:guid')
    vet_document.subproduct = get_or_load_subproduct_by_guid(credentials, vet_document.subproduct_guid)

    # product_item_guid
    # product_item_name
    # product_item

    vet_document.product_item_name = get_xml_text(batch_xml, 'vd:productItem/dt:name')
    vet_document_guid_xml = batch_xml.find('vd:productItem/bs:guid', NAMESPACES)
    if vet_document_guid_xml is not None:
        vet_document.product_item_guid = vet_document_guid_xml.text
        vet_document.product_item = get_or_load_product_item_by_guid(credentials=credentials, product_item_guid=vet_document.product_item_guid)
    else:
        vet_document.product_item = get_or_create_dummy_product_item(vet_document.product_item_name, vet_document.subproduct)

    # volume
    # unit

    vet_document.volume = Decimal(get_xml_text(batch_xml, 'vd:volume'))
    vet_document.unit = get_or_load_unit_by_guid(credentials, get_xml_text(batch_xml, 'vd:unit/bs:guid'))

    # date_produced_1
    # date_produced_2
    # date_produced
    # date_expiry_1
    # date_expiry_2
    # date_expiry

    date_produced_1, date_produced_2 = process_complex_date(batch_xml.find('vd:dateOfProduction', NAMESPACES))

    vet_document.date_produced_1 = date_produced_1.to_string()
    vet_document.date_produced_2 = date_produced_2.to_string() if date_produced_2 else ''
    vet_document.date_produced = date_produced_1.to_datetime()

    date_expiry_1, date_expiry_2 = process_complex_date(batch_xml.find('vd:expiryDate', NAMESPACES))

    vet_document.date_expiry_1 = date_expiry_1.to_string()
    vet_document.date_expiry_2 = date_expiry_2.to_string() if date_expiry_2 else ''
    vet_document.date_expiry = date_expiry_1.to_datetime()

    # is_perishable

    vet_document.is_perishable = get_xml_text(batch_xml, 'vd:perishable', default='false') == 'true'
    
    # origin_country
    # producer_name

    vet_document.origin_country = get_xml_text(batch_xml, 'vd:origin/vd:country/dt:name', default='')
    vet_document.producer_name = get_xml_text(batch_xml, 'vd:origin/vd:producer/dt:enterprise/dt:name', default='')

    vet_document.save()


@shared_task(bind=True)
def update_vet_documents_task(this_task, credentials_id: int, initiator_login: str, enterprise_id: int):
    return update_vet_documents(this_task, credentials_id, initiator_login, enterprise_id)


def update_vet_documents(this_task, credentials_id: int, initiator_login: str, enterprise_id: int):
    try:
        enterprise = Enterprise.objects.get(id=enterprise_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Предприятие не найдено')
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Не обнаружены параметры подключения')

    if enterprise.vet_documents_last_updated is not None:
        begin_date = enterprise.vet_documents_last_updated - timedelta(minutes=5) # rolloff slightly just in case
    else:
        begin_date = datetime.now(tz=TZ_MOSCOW) - timedelta(days=2) # well... ok

    end_date = datetime.now(tz=TZ_MOSCOW)

    list_count = 1000
    list_offset = 0

    response_xml_pages = []

    logger.debug('Загружаем список ветеринарных документов...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': 'Загружаем список ветеринарных документов...'})

    while True: # repeat if has pages

        logger.debug(f'Запрос c list_offset={list_offset}')

        soap_request = GetVetDocumentChangesListRequest(
            enterprise_guid=enterprise.guid,
            begin_date=begin_date,
            end_date=end_date,
            api_key=credentials.api_key,
            service_id=credentials.service_id,
            issuer_id=credentials.issuer_id,
            initiator_login=initiator_login,
            list_count=list_count,
            list_offset=list_offset
        )

        response = send_2step_soap_request(soap_request, credentials)

        result_xml = ET.fromstring(response.text)

        response_xml_pages.append(result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse/apl:application/apl:result/merc:getVetDocumentChangesListResponse/vd:vetDocumentList', NAMESPACES))

        total = int(response_xml_pages[-1].get('total'))

        if not list_offset:
            logger.debug(f'Всего документов: {total}')

        if total > list_offset + list_count:
            list_offset += list_count
        else:
            break

    logger.debug('Обновляем список ветеринарных документов...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': 'Обновляем список ветеринарных документов...'})

    with transaction.atomic():

        for response_xml in response_xml_pages:

            for vet_document_xml in response_xml.findall('vd:vetDocument', NAMESPACES):
                try:
                    vet_document = VetDocument.objects.get(uuid=vet_document_xml.find('bs:uuid', NAMESPACES).text)
                except:
                    vet_document = VetDocument()

                fill_vet_document_from_xml(
                    vet_document=vet_document,
                    vet_document_xml=vet_document_xml,
                    credentials=credentials
                    )
                
        # /for pages

        enterprise.vet_documents_last_updated = end_date
        enterprise.save()

    # /transaction.atomic   

    return f'Ветеринарные документы по предприятию успешно обновлены. Всего: {total}'


def fill_stock_entry_from_xml(stock_entry: StockEntry, enterprise: Enterprise, stock_entry_xml: ET.Element, credentials: VetisCredentials):

    # main
    # enterprise
    # guid
    # uuid

    stock_entry.enterprise = enterprise
    stock_entry.guid = get_xml_text(stock_entry_xml, 'bs:guid')
    stock_entry.uuid = get_xml_text(stock_entry_xml, 'bs:uuid')
    stock_entry.main, main_created = StockEntryMain.objects.get_or_create(guid=stock_entry.guid)

    # is_active
    # is_last
    # status
    # date_created
    # date_updated
    # previous_uuid
    # next_uuid
    # entry_number

    stock_entry.is_active = get_xml_text(stock_entry_xml, 'bs:active') == 'true'
    stock_entry.is_last = get_xml_text(stock_entry_xml, 'bs:last') == 'true'
    stock_entry.status = int(get_xml_text(stock_entry_xml, 'bs:status'))
    stock_entry.date_created = datetime.fromisoformat(get_xml_text(stock_entry_xml, 'bs:createDate'))
    stock_entry.date_updated = datetime.fromisoformat(get_xml_text(stock_entry_xml, 'bs:updateDate'))
    previous_uuid_xml = stock_entry_xml.find('bs:previous', NAMESPACES)
    if previous_uuid_xml is not None:
        stock_entry.previous_uuid = previous_uuid_xml.text
    next_uuid_xml = stock_entry_xml.find('bs:next', NAMESPACES)
    if next_uuid_xml is not None:
        stock_entry.next_uuid = next_uuid_xml.text
    stock_entry.entry_number = get_xml_text(stock_entry_xml, 'vd:entryNumber')

    batch_xml = stock_entry_xml.find('vd:batch', NAMESPACES)
    
    # product_type
    # product_guid
    # product
    # subproduct_guid
    # subproduct

    stock_entry.product_type = int(get_xml_text(batch_xml, 'vd:productType'))
    stock_entry.product_guid = get_xml_text(batch_xml, 'vd:product/bs:guid')
    stock_entry.product = get_or_load_product_by_guid(credentials=credentials, product_guid=stock_entry.product_guid)
    stock_entry.subproduct_guid = get_xml_text(batch_xml, 'vd:subProduct/bs:guid')
    stock_entry.subproduct = get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=stock_entry.subproduct_guid)
    
    # product_item_guid
    # product_item_name
    # product_item

    stock_entry.product_item_name = get_xml_text(batch_xml, 'vd:productItem/dt:name')
    product_item_guid_xml = batch_xml.find('vd:productItem/bs:guid', NAMESPACES)
    if product_item_guid_xml is not None:
        stock_entry.product_item_guid = product_item_guid_xml.text
        stock_entry.product_item = get_or_load_product_item_by_guid(credentials=credentials, product_item_guid=stock_entry.product_item_guid)
    else:
        stock_entry.product_item = get_or_create_dummy_product_item(stock_entry.product_item_name, stock_entry.subproduct)

    # volume
    # unit

    if stock_entry.status in [201]:  # запись аннулирована
        stock_entry.volume = 0
    else:
        stock_entry.volume = Decimal(batch_xml.find('vd:volume', NAMESPACES).text)

    stock_entry.unit = get_or_load_unit_by_guid(credentials, get_xml_text(batch_xml, 'vd:unit/bs:guid'))
    
    # date_produced_1
    # date_produced_2
    # date_produced
    # date_expiry_1
    # date_expiry_2
    # date_expiry

    date_produced_1, date_produced_2 = process_complex_date(batch_xml.find('vd:dateOfProduction', NAMESPACES))

    stock_entry.date_produced_1 = date_produced_1.to_string()
    stock_entry.date_produced_2 = date_produced_2.to_string() if date_produced_2 else ''
    stock_entry.date_produced = date_produced_1.to_datetime()

    date_expiry_1, date_expiry_2 = process_complex_date(batch_xml.find('vd:expiryDate', NAMESPACES))

    stock_entry.date_expiry_1 = date_expiry_1.to_string()
    stock_entry.date_expiry_2 = date_expiry_2.to_string() if date_expiry_2 else ''
    stock_entry.date_expiry = date_expiry_1.to_datetime()

    # is_perishable

    stock_entry.is_perishable = get_xml_text(batch_xml, 'vd:perishable') == 'true'

    # origin_country
    # producer_name
    
    stock_entry.origin_country = get_xml_text(batch_xml, 'vd:origin/vd:country/dt:name', default='')
    stock_entry.producer_name = get_xml_text(batch_xml, 'vd:origin/vd:producer/dt:enterprise/dt:name', default='')

    producer_guid_xml = batch_xml.find('vd:origin/vd:producer/dt:enterprise/bs:guid', NAMESPACES)
    if producer_guid_xml is not None:
        stock_entry.producer_guid = producer_guid_xml.text
        try:
            producer = Enterprise.objects.get(guid=stock_entry.producer_guid)
            stock_entry.producer = producer
        except ObjectDoesNotExist:
            pass

    stock_entry.save()

    # packages

    stock_entry.package_set.all().delete()

    for package_xml in batch_xml.findall('vd:packageList/dt:package', NAMESPACES):

        package = Package()
        package.stock_entry = stock_entry
        package.level = int(get_xml_text(package_xml, 'dt:level'))
        packing_type_guid = get_xml_text(package_xml, 'dt:packingType/bs:guid')
        packing_type_uuid = get_xml_text(package_xml, 'dt:packingType/bs:uuid')
        packing_type_name = get_xml_text(package_xml, 'dt:packingType/dt:name')
        packing_type_glodal_id = get_xml_text(package_xml, 'dt:packingType/dt:globalID')
        package.packing_type = PackingType.get_or_create(
            guid=packing_type_guid,
            uuid=packing_type_uuid,
            name=packing_type_name,
            global_id=packing_type_glodal_id
        )
        quantity_xml = package_xml.find('dt:quantity', NAMESPACES)
        if quantity_xml is not None:
            package.quantity = int(quantity_xml.text)
        else:
            package.quantity = 0
        
        marks = []
        for marks_xml in package_xml.findall('dt:productMarks', NAMESPACES):
            marks.append(marks_xml.text)
        if marks:
            package.product_marks = ' '.join(marks)

        package.save()
    
    stock_entry.stockentryvetdocument_set.all().delete()

    for vet_document_uuid_xml in stock_entry_xml.findall('vd:vetDocument/bs:uuid', NAMESPACES):
        vet_document = StockEntryVetDocument()
        vet_document.stock_entry = stock_entry
        vet_document.uuid = vet_document_uuid_xml.text
        vet_document.save()

    # / for package


@shared_task(bind=True)
def update_stock_entries_task(this_task, credentials_id: int, initiator_login: str, enterprise_id: int):
    return update_stock_entries(this_task, credentials_id, initiator_login, enterprise_id)


def update_stock_entries(this_task, credentials_id: int, initiator_login: str, enterprise_id: int):
    """Загружаем изменения в записях журнала, загружаем изменения в списке ветдокументов, обновляем головные записи."""

    try:
        enterprise = Enterprise.objects.get(id=enterprise_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Предприятие не найдено')
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Не обнаружены параметры подключения')
    
    # last_updated_entry = StockEntry.objects.filter(enterprise=enterprise).order_by('-date_updated').first()

    if enterprise.stock_entries_last_updated is not None:
        update_mode = 'CHANGES'
        begin_date = enterprise.stock_entries_last_updated - timedelta(minutes=5) # rolloff slightly just in case
    else:
        update_mode = 'INITIAL'

    end_date = datetime.now(tz=TZ_MOSCOW)

    list_count = 1000
    list_offset = 0

    response_xml_pages = []

    logger.debug(f'Загружаем записи складского журнала (режим {update_mode})...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': f'Загружаем записи складского журнала (режим {update_mode})...'})

    while True: # repeat if has pages

        logger.debug(f'Запрос c list_offset={list_offset}')

        if update_mode == 'INITIAL':
            soap_request = GetStockEntryListRequest(
                enterprise_guid=enterprise.guid,
                api_key=credentials.api_key,
                service_id=credentials.service_id,
                issuer_id=credentials.issuer_id,
                initiator_login=initiator_login,
                list_count=list_count,
                list_offset=list_offset
            )
        else:
            soap_request = GetStockEntryChangesListRequest(
                enterprise_guid=enterprise.guid,
                begin_date=begin_date,
                end_date=end_date,
                api_key=credentials.api_key,
                service_id=credentials.service_id,
                issuer_id=credentials.issuer_id,
                initiator_login=initiator_login,
                list_count=list_count,
                list_offset=list_offset
            )

        response = send_2step_soap_request(soap_request, credentials)

        result_xml = ET.fromstring(response.text)

        if update_mode == 'INITIAL':
            response_xml_pages.append(result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse/apl:application/apl:result/merc:getStockEntryListResponse/vd:stockEntryList', NAMESPACES))
        else:
            response_xml_pages.append(result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse/apl:application/apl:result/merc:getStockEntryChangesListResponse/vd:stockEntryList', NAMESPACES))

        total = int(response_xml_pages[-1].get('total'))

        if not list_offset:
            logger.debug(f'Всего записей: {total}')

        if total > list_offset + list_count:
            list_offset += list_count
        else:
            break
    # /while

    logger.debug(f'Обновляем записи складского журнала (режим {update_mode})...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': f'Обновляем записи складского журнала (режим {update_mode})...'})

    with transaction.atomic():

        for response_xml in response_xml_pages:

            for stock_entry_xml in response_xml.findall('vd:stockEntry', NAMESPACES):
                try:
                    stock_entry = StockEntry.objects.get(uuid=stock_entry_xml.find('bs:uuid', NAMESPACES).text)
                except:
                    stock_entry = StockEntry()

                fill_stock_entry_from_xml(
                    stock_entry=stock_entry,
                    enterprise=enterprise,
                    stock_entry_xml=stock_entry_xml,
                    credentials=credentials
                    )

        # /for pages

        enterprise.stock_entries_last_updated = end_date
        enterprise.save()

    # /transaction.atomic   

    uvd_result = update_vet_documents(this_task, credentials_id, initiator_login, enterprise_id)

    usemr_result = update_stock_entry_main_records(this_task, credentials_id, initiator_login, enterprise_id)

    total_result = {
        "info1": f'Складские записи для предприятия успешно обновлены. Всего: {total}',
        "info2": usemr_result,
        "info3": uvd_result,
    }

    return total_result


@shared_task(bind=True)
def update_stock_entry_history_task(this_task, credentials_id: int, initiator_login: str, stock_entry_id: int):
    return update_stock_entry_history(this_task, credentials_id, initiator_login, stock_entry_id)


def update_stock_entry_history(this_task, credentials_id: int, initiator_login: str, stock_entry_id: int):
    try:
        stock_entry = StockEntry.objects.get(id=stock_entry_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Запись журнала не найдена')
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Не обнаружены параметры подключения')
    
    enterprise = stock_entry.enterprise

    # business_entity = BusinessEntity.objects.filter(credentials=credentials, id=enterprise.business_entity.id).first()
    # if business_entity is None:
    #     raise RuntimeError('Запись журнала не принадлежит текущему хозяйственному субъекту!')
    
    if enterprise.business_entity.credentials != credentials:
        raise RuntimeError('Запись журнала не принадлежит текущему хозяйственному субъекту')
    
    list_count = 1000
    list_offset = 0

    response_xml_pages = []

    logger.debug('Загружаем историю записи журнала...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': f'Загружаем историю записи журнала {stock_entry.entry_number}...'})

    while True: # repeat if has pages
            
        soap_request = GetStockEntryVersionListRequest(
            enterprise_guid=enterprise.guid,
            stock_entry_guid=stock_entry.guid,
            api_key=credentials.api_key,
            service_id=credentials.service_id,
            issuer_id=credentials.issuer_id,
            initiator_login=initiator_login,
            list_count=list_count,
            list_offset=list_offset
        )

        response = send_2step_soap_request(soap_request, credentials)

        result_xml = ET.fromstring(response.text)

        response_xml_pages.append(result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse/apl:application/apl:result/merc:getStockEntryVersionListResponse/vd:stockEntryList', NAMESPACES))

        total = int(response_xml_pages[-1].get('total'))

        if not list_offset:
            logger.debug(f'Всего версий: {total}')
        
        if total > list_offset + list_count:
            list_offset += list_count
        else:
            break
    # /while

    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': f'Обновляем историю записи журнала {stock_entry.entry_number}...'})

    with transaction.atomic():

        for response_xml in response_xml_pages:

            for stock_entry_version_xml in response_xml.findall('vd:stockEntry', NAMESPACES):
                try:
                    stock_entry_version = StockEntry.objects.get(uuid=stock_entry_version_xml.find('bs:uuid', NAMESPACES).text)
                except:
                    stock_entry_version = StockEntry()

                fill_stock_entry_from_xml(
                    stock_entry=stock_entry_version,
                    enterprise=enterprise,
                    stock_entry_xml=stock_entry_version_xml,
                    credentials=credentials
                    )

        # /for pages
    # /transaction.atomic   

    return f'История для записи журнала успешно обновлена. Всего: {total}'


def update_stock_entry_main(this_task, stock_entry_main: StockEntryMain, credentials: VetisCredentials, initiator_login: str):
    if stock_entry_main.is_populated:
        return False
    
    first_stock_entry = StockEntry.objects.filter(main=stock_entry_main).order_by('date_created').first()

    if first_stock_entry is None:
        raise RuntimeError(f'Не найдено версий для головной записи журнала с id={stock_entry_main.id}')

    if first_stock_entry.previous_uuid is not None:
        logger.debug('Загружаем полную историю записи журнала')
        update_stock_entry_history(this_task, credentials.id, initiator_login=initiator_login, stock_entry_id=first_stock_entry.id)
        first_stock_entry = StockEntry.objects.filter(main=stock_entry_main).order_by('date_created').first()
        if first_stock_entry is None:
            raise RuntimeError(f'Не удалось загрузить полную историю для записи с id={first_stock_entry.id}')
    
    if first_stock_entry.status in [102]:  # Гашение ВСД
        logger.debug('Берем данные из вет. документа')
        stock_entry_vet_document = first_stock_entry.stockentryvetdocument_set.first()

        if stock_entry_vet_document is not None:

            vet_document = get_or_load_vet_document_by_uuid(credentials, first_stock_entry.enterprise, initiator_login, stock_entry_vet_document.uuid)

            if vet_document.vetd_type != 'TRANSPORT':
                raise RuntimeError(f'Неизвестный тип ветеринарного документа {vet_document.vetd_type}')

            stock_entry_main.initial_status = first_stock_entry.status
            stock_entry_main.date_created = first_stock_entry.date_created
            stock_entry_main.initial_volume = first_stock_entry.volume
            stock_entry_main.source_be_guid = vet_document.consignor_be_guid
            stock_entry_main.source_be_name = vet_document.consignor_be_name
            stock_entry_main.source_ent_guid = vet_document.consignor_ent_guid
            stock_entry_main.source_ent_name = vet_document.consignor_ent_name
            stock_entry_main.is_populated = True
            stock_entry_main.save()
            return True

        else:
            logger.warning(f'Нет вет. документа для записи со статусом Гашение ВСД. Номер записи={first_stock_entry.entry_number}')
            return False

    else:
        stock_entry_main.initial_status = first_stock_entry.status
        stock_entry_main.date_created = first_stock_entry.date_created
        stock_entry_main.initial_volume = first_stock_entry.volume
        stock_entry_main.source_be_guid = first_stock_entry.enterprise.business_entity.guid
        stock_entry_main.source_be_name = str(first_stock_entry.enterprise.business_entity)
        stock_entry_main.source_ent_guid = first_stock_entry.enterprise.guid
        stock_entry_main.source_ent_name = str(first_stock_entry.enterprise)
        stock_entry_main.is_populated = True
        stock_entry_main.save()
    
    return True


@shared_task(bind=True)
def update_stock_entry_main_records_task(this_task, credentials_id: int, initiator_login: str, enterprise_id: int):
    return update_stock_entry_main_records(this_task, credentials_id, initiator_login, enterprise_id)


def update_stock_entry_main_records(this_task, credentials_id: int, initiator_login: str, enterprise_id: int):
    try:
        enterprise = Enterprise.objects.get(id=enterprise_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Предприятие не найдено')
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        raise RuntimeError('Не обнаружены параметры подключения')
    
    if enterprise.business_entity.credentials != credentials:
        raise RuntimeError('Параметры подключения не соответствуют указанному предприятию')

    stock_entries = StockEntry.objects.filter(is_last=True, enterprise=enterprise).select_related('main').exclude(main__is_populated=True)
    total = stock_entries.count()
    processed = 0
    updated = 0

    logger.debug('Обновляем головные записи журнала...')
    if this_task:
        this_task.update_state(state='PROGRESS', meta={'info': f'Обновляем головные записи журнала ({total})...'})

    for stock_entry in stock_entries:
        processed += 1
        if update_stock_entry_main(
            this_task=this_task,
            stock_entry_main=stock_entry.main,
            credentials=credentials,
            initiator_login=initiator_login
        ):
            updated += 1

    return f'Завершено обновление головных записей журнала (обновлено {updated} из {total})'