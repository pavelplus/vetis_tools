import requests
from time import sleep
from datetime import datetime, timedelta
from decimal import Decimal
import xml.etree.ElementTree as ET

from celery import shared_task

from django.core.exceptions import ObjectDoesNotExist, BadRequest
from django.db import transaction

from .models import (
    BusinessEntity,
    ApiRequestsHistoryRecord,
    VetisCredentials,
    Enterprise,
    ProductItem,
    Product,
    SubProduct,
    StockEntry,
    Unit,
    ComplexDate,
    Package,
    PackingType
    )
from .xml.build_xml import *
from .xml.settings import NAMESPACES



# PROD
ENDPOINTS_PROD = {
    'ProductService': 'https://api.vetrf.ru/platform/services/2.1/ProductService',
    'EnterpriseService': 'https://api.vetrf.ru/platform/services/2.1/EnterpriseService',
    'ApplicationManagementService': 'https://api.vetrf.ru/platform/services/2.1/ApplicationManagementService',
}

# TEST
ENDPOINTS_TEST = {
    'ProductService': 'https://api2.vetrf.ru:8002/platform/services/2.1/ProductService',
    'EnterpriseService': 'https://api2.vetrf.ru:8002/platform/services/2.1/EnterpriseService',
    'ApplicationManagementService': 'https://api2.vetrf.ru:8002/platform/services/2.1/ApplicationManagementService',
}


def send_soap_request(soap_request: AbstractRequest, credentials: VetisCredentials):
    headers = {
        'Content-Type': 'text/html;charset=UTF-8',
        'SOAPAction': soap_request.soap_action,
    }
    body = soap_request.get_xml()

    endpoint_url = ENDPOINTS_PROD[soap_request.endpoint_name] if credentials.is_productive else ENDPOINTS_TEST[soap_request.endpoint_name]

    # print(f'send_soap_request: endpoint_url={endpoint_url}, body={body}')
    # print(f'send_soap_request: headers={headers}')
    # print(f'send_soap_request: body={body}')

    # return None

    for try_num in range(3):
        try:
            response = requests.post(
                    url=endpoint_url,
                    auth=(credentials.login, credentials.password),
                    headers=headers,
                    data=body
                )
        except requests.exceptions.ConnectionError:
            response = None
        
        if response is None:
            print(f'Connection error on try #{try_num+1}')
            sleep(5 + 5*try_num)
        else:
            break

    record = ApiRequestsHistoryRecord()
    record.soap_action = soap_request.soap_action
    record.soap_request = soap_request.get_xml()
    record.comment = f'{credentials.name} {endpoint_url}'
    if response is not None:
        record.response_status_code = response.status_code
        record.response_body = response.text
    else:
        record.response_status_code = 0
    record.save()
    
    return response


def send_2step_soap_request(soap_request: AbstractRequest, credentials: VetisCredentials):

    print('Sending two-step request. Step 1.')

    response = send_soap_request(soap_request, credentials)

    if response is None:
        return {'result': 'error', 'message': 'Ошибка соединения'}

    if response.status_code != 200:
        return {'result': 'error', 'message': f'Ошибка запроса ({response.status_code}): {response.reason}'}

    result_xml = ET.fromstring(response.text)

    response_xml = result_xml.find('./soapenv:Body/apldef:submitApplicationResponse', NAMESPACES)

    status = response_xml.find('apl:application/apl:status', NAMESPACES).text

    print(f'Status: {status}')

    if status != 'ACCEPTED':
        return {'result': 'error', 'message': f'Ошибка обработки запроса ({status})'}
    
    application_id = response_xml.find('apl:application/apl:applicationId', NAMESPACES).text

    application_result_request = ReceiveApplicationResultRequest(api_key=credentials.api_key, issuer_id=credentials.issuer_id, application_id=application_id)

    for try_num in range(3):
        sleep(5 + try_num*10)

        print(f'Receiving result... Try #{try_num}')
        
        response = send_soap_request(application_result_request, credentials)

        if response is None:
            return {'result': 'error', 'message': 'Ошибка соединения'}

        if response.status_code != 200:
            return {'result': 'error', 'message': f'Ошибка запроса при ожидании двухэтапного ответа ({response.status_code}): {response.reason}'}
        
        result_xml = ET.fromstring(response.text)

        response_xml = result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse', NAMESPACES)

        status = response_xml.find('apl:application/apl:status', NAMESPACES).text

        print(f'Status: {status}')

        if status == 'COMPLETED':
            return {'result': 'success', 'response': response}
        elif status == 'REJECTED':
            return {'result': 'error', 'message': 'Запрос отклонен (REJECTED)'}

    return {'result': 'error', 'message': 'Таймаут ожидания результата обработки'}


@shared_task
def test_task():
    for i in range(0, 5):
        print(f'Processing {i+1}...')
        sleep(1.0)
    print('Task done.')
    return {'result': 'success', 'message': 'Тестовая задача завершена успешно.'}


@shared_task
def reload_enterprises(credentials_id: int, business_entity_id: int):
    try:
        business_entity = BusinessEntity.objects.get(id=business_entity_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Хозяйствующий субъект не найден!'}
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Не обнаружены параметры подключения!'}
    
    list_count = 1000
    list_offset = 0

    with transaction.atomic():

        business_entity.enterprise_set.update(is_active=False)

        while True: # repeat if has pages

            soap_request = ActivityLocationListRequest(business_entity.guid, list_count, list_offset)

            response = send_soap_request(soap_request, credentials)

            if response is None:
                return {'result': 'error', 'message': 'Ошибка соединения'}

            if response.status_code != 200:
                return {'result': 'error', 'message': f'Ошибка запроса ({response.status_code}): {response.reason}'}
            
            result_xml = ET.fromstring(response.text)

            response_xml = result_xml.find('./soapenv:Body/ws:getActivityLocationListResponse/dt:activityLocationList', NAMESPACES)

            for enterprise_xml in response_xml.findall('dt:location/dt:enterprise', NAMESPACES):
                try:
                    enterprise = Enterprise.objects.get(guid=enterprise_xml.find('bs:guid', NAMESPACES).text)
                except:
                    enterprise = Enterprise()
                
                enterprise.business_entity = business_entity
                enterprise.guid = enterprise_xml.find('bs:guid', NAMESPACES).text
                enterprise.uuid = enterprise_xml.find('bs:uuid', NAMESPACES).text
                enterprise.type = int(enterprise_xml.find('dt:type', NAMESPACES).text)
                enterprise.name = enterprise_xml.find('dt:name', NAMESPACES).text
                enterprise.address = enterprise_xml.find('dt:address/dt:addressView', NAMESPACES).text
                enterprise.is_active = enterprise_xml.find('bs:active', NAMESPACES).text == 'true'

                enterprise_numbers = []

                for enterprise_number in enterprise_xml.findall('dt:numberList/dt:enterpriseNumber', NAMESPACES):
                    enterprise_numbers.append(enterprise_number.text)

                enterprise.number_list = ', '.join(enterprise_numbers)

                enterprise.save()

            total = int(response_xml.get('total'))
            
            if total > list_offset + list_count:
                list_offset += list_count
            else:
                break

        # /while
    # /transaction.atomic
    
    return {'result': 'success', 'message': 'Предприятия хозяйствующего субъекта успешно обновлены.'}


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

    print(f'Loading product: {product_guid}')

    soap_request = ProductByGuidRequest(product_guid)
    response = send_soap_request(soap_request, credentials)

    if response is None:
        raise BadRequest()
    
    sleep(0.5)
    
    if response.status_code != 200:
        raise BadRequest()
    
    result_xml = ET.fromstring(response.text)

    product_xml = result_xml.find('./soapenv:Body/ws:getProductByGuidResponse/dt:product', NAMESPACES)

    # guid
    # uuid
    # name
    # code
    # product_type

    product.guid = product_xml.find('bs:guid', NAMESPACES).text
    product.uuid = product_xml.find('bs:uuid', NAMESPACES).text
    product.name = product_xml.find('dt:name', NAMESPACES).text
    code_xml = product_xml.find('dt:code', NAMESPACES)
    if code_xml is not None:
        product.code = code_xml.text
    product.product_type = int(product_xml.find('dt:productType', NAMESPACES).text)

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

    print(f'Loading subproduct: {subproduct_guid}')

    soap_request = SubproductByGuidRequest(subproduct_guid)
    response = send_soap_request(soap_request, credentials)

    if response is None:
        raise BadRequest()
    
    sleep(0.5)
    
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

    subproduct.guid = subproduct_xml.find('bs:guid', NAMESPACES).text
    subproduct.uuid = subproduct_xml.find('bs:uuid', NAMESPACES).text
    subproduct.name = subproduct_xml.find('dt:name', NAMESPACES).text
    code_xml = subproduct_xml.find('dt:code', NAMESPACES)
    if code_xml is not None:
        subproduct.code = code_xml.text
    subproduct.product_guid = subproduct_xml.find('dt:productGuid', NAMESPACES).text

    product = get_or_load_product_by_guid(credentials=credentials, product_guid=subproduct.product_guid)

    subproduct.product = product

    subproduct.save()

    return subproduct


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

    print(f'Loading product item: {product_item_guid}')

    soap_request = ProductItemByGuidRequest(product_item_guid)
    response = send_soap_request(soap_request, credentials)

    if response is None:
        raise BadRequest()
    
    sleep(0.5)
    
    if response.status_code != 200:
        raise BadRequest()
    
    result_xml = ET.fromstring(response.text)

    product_item_xml = result_xml.find('./soapenv:Body/ws:getProductItemByGuidResponse/dt:productItem', NAMESPACES)

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

    product_item.guid = product_item_xml.find('bs:guid', NAMESPACES).text
    product_item.uuid = product_item_xml.find('bs:uuid', NAMESPACES).text
    product_item.is_active = product_item_xml.find('bs:active', NAMESPACES).text == 'true'
    name_xml = product_item_xml.find('dt:name', NAMESPACES)
    if name_xml is not None:
        product_item.name = name_xml.text
    globalID_xml = product_item_xml.find('dt:globalID', NAMESPACES)
    if globalID_xml is not None:
        product_item.gtin = globalID_xml.text
    product_item.product_type = int(product_item_xml.find('dt:productType', NAMESPACES).text)
    product_item.product_guid = product_item_xml.find('dt:product/bs:guid', NAMESPACES).text
    product_item.product = get_or_load_product_by_guid(credentials=credentials, product_guid=product_item.product_guid)
    product_item.subproduct_guid = product_item_xml.find('dt:subProduct/bs:guid', NAMESPACES).text
    product_item.subproduct = get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=product_item.subproduct_guid)
    if name_xml is None:
        product_item.name = product_item.subproduct.name
    product_item.is_gost = product_item_xml.find('dt:correspondsToGost', NAMESPACES).text == 'true'
    if product_item.is_gost:
        product_item.gost = product_item_xml.find('dt:gost', NAMESPACES).text
    producer_guid_xml = product_item_xml.find('dt:producer/bs:guid', NAMESPACES)
    if producer_guid_xml is not None:
        product_item.producer_guid = producer_guid_xml.text
    producer = BusinessEntity.objects.filter(guid=product_item.producer_guid).first()
    if producer is not None:
        product_item.producer = producer

    product_item.save()

    return product_item


@shared_task
def reload_product_subproduct(credentials_id: int):
    """Update existing product and subproduct records form Vetis"""

    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Не обнаружены параметры подключения!'}

    for product in Product.objects.all():
        get_or_load_product_by_guid(credentials=credentials, product_guid=product.guid, update=True)
    
    for subproduct in SubProduct.objects.all():
        get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=subproduct.guid, update=True)

    return {'result': 'success', 'message': 'Списки продукция и вид продукции обновлены.'}


@shared_task
def reload_product_items(credentials_id: int, business_entity_id: int):
    try:
        business_entity = BusinessEntity.objects.get(id=business_entity_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Хозяйствующий субъект не найден!'}
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Не обнаружены параметры подключения!'}
    
    list_count = 1000
    list_offset = 0

    with transaction.atomic():

        ProductItem.objects.filter(producer_guid=business_entity.guid).update(is_active=False)

        while True: # repeat if has pages

            print(f'reload_product_items: list_offset={list_offset}')

            soap_request = ProductItemListRequest(business_entity.guid, list_count, list_offset)

            response = send_soap_request(soap_request, credentials)

            if response is None:
                return {'result': 'error', 'message': 'Ошибка соединения'}

            if response.status_code != 200:
                return {'result': 'error', 'message': f'Ошибка запроса ({response.status_code}): {response.reason}'}
            
            result_xml = ET.fromstring(response.text)

            response_xml = result_xml.find('./soapenv:Body/ws:getProductItemListResponse/dt:productItemList', NAMESPACES)

            for product_item_xml in response_xml.findall('dt:productItem', NAMESPACES):
                try:
                    product_item = ProductItem.objects.get(guid=product_item_xml.find('bs:guid', NAMESPACES).text)
                except:
                    product_item = ProductItem()

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

                product_item.guid = product_item_xml.find('bs:guid', NAMESPACES).text
                product_item.uuid = product_item_xml.find('bs:uuid', NAMESPACES).text
                product_item.is_active = product_item_xml.find('bs:active', NAMESPACES).text == 'true'
                name_xml = product_item_xml.find('dt:name', NAMESPACES)
                if name_xml is not None:
                    product_item.name = name_xml.text
                globalID_xml = product_item_xml.find('dt:globalID', NAMESPACES)
                if globalID_xml is not None:
                    product_item.gtin = globalID_xml.text
                product_item.product_type = int(product_item_xml.find('dt:productType', NAMESPACES).text)
                product_item.product_guid = product_item_xml.find('dt:product/bs:guid', NAMESPACES).text
                product_item.product = get_or_load_product_by_guid(credentials=credentials, product_guid=product_item.product_guid)
                product_item.subproduct_guid = product_item_xml.find('dt:subProduct/bs:guid', NAMESPACES).text
                product_item.subproduct = get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=product_item.subproduct_guid)
                if name_xml is None:
                    product_item.name = product_item.subproduct.name
                product_item.is_gost = product_item_xml.find('dt:correspondsToGost', NAMESPACES).text == 'true'
                if product_item.is_gost:
                    product_item.gost = product_item_xml.find('dt:gost', NAMESPACES).text
                producer_guid_xml = product_item_xml.find('dt:producer/bs:guid', NAMESPACES)
                if producer_guid_xml is not None:
                    product_item.producer_guid = producer_guid_xml.text
                product_item.producer = business_entity

                product_item.save()

            total = int(response_xml.get('total'))
            
            if total > list_offset + list_count:
                list_offset += list_count
                sleep(1.0)
            else:
                break
        # /while
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

    return {'result': 'success', 'message': f'Список продукции обновлен. Всего: {total}'}


def fill_stock_entry_from_xml(stock_entry: StockEntry, enterprise: Enterprise, stock_entry_xml: ET.Element, credentials: VetisCredentials):

    # enterprise
    # guid
    # uuid
    # is_active
    # is_last
    # status
    # date_created
    # date_updated
    # previous_uuid
    # next_uuid
    # entry_number

    stock_entry.enterprise = enterprise
    stock_entry.guid = stock_entry_xml.find('bs:guid', NAMESPACES).text
    stock_entry.uuid = stock_entry_xml.find('bs:uuid', NAMESPACES).text
    stock_entry.is_active = stock_entry_xml.find('bs:active', NAMESPACES).text == 'true'
    stock_entry.is_last = stock_entry_xml.find('bs:last', NAMESPACES).text == 'true'
    stock_entry.status = int(stock_entry_xml.find('bs:status', NAMESPACES).text)
    stock_entry.date_created = datetime.fromisoformat(stock_entry_xml.find('bs:createDate', NAMESPACES).text)
    stock_entry.date_updated = datetime.fromisoformat(stock_entry_xml.find('bs:updateDate', NAMESPACES).text)
    previous_uuid_xml = stock_entry_xml.find('bs:previous', NAMESPACES)
    if previous_uuid_xml is not None:
        stock_entry.previous_uuid = previous_uuid_xml.text
    next_uuid_xml = stock_entry_xml.find('bs:next', NAMESPACES)
    if next_uuid_xml is not None:
        stock_entry.next_uuid = next_uuid_xml.text
    stock_entry.entry_number = stock_entry_xml.find('vd:entryNumber', NAMESPACES).text

    batch_xml = stock_entry_xml.find('vd:batch', NAMESPACES)
    
    # product_type
    # product_guid
    # product
    # subproduct_guid
    # subproduct

    stock_entry.product_type = int(batch_xml.find('vd:productType', NAMESPACES).text)
    stock_entry.product_guid = batch_xml.find('vd:product/bs:guid', NAMESPACES).text
    stock_entry.product = get_or_load_product_by_guid(credentials=credentials, product_guid=stock_entry.product_guid)
    stock_entry.subproduct_guid = batch_xml.find('vd:subProduct/bs:guid', NAMESPACES).text
    stock_entry.subproduct = get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=stock_entry.subproduct_guid)
    
    # product_item_guid
    # product_item_name
    # product_item

    stock_entry.product_item_name = batch_xml.find('vd:productItem/dt:name', NAMESPACES).text
    product_item_guid_xml = batch_xml.find('vd:productItem/bs:guid', NAMESPACES)
    if product_item_guid_xml is not None:
        stock_entry.product_item_guid = product_item_guid_xml.text
        stock_entry.product_item = get_or_load_product_item_by_guid(credentials=credentials, product_item_guid=stock_entry.product_item_guid)

    # volume

    stock_entry.volume = Decimal(batch_xml.find('vd:volume', NAMESPACES).text)

    # unit
    
    unit_guid = batch_xml.find('vd:unit/bs:guid', NAMESPACES).text
    unit_name = batch_xml.find('vd:unit/dt:name', NAMESPACES).text

    stock_entry.unit = Unit.get_or_create(guid=unit_guid, name=unit_name)
    
    # date_produced_1
    # date_produced_2
    # date_produced

    date_produced_1_xml = batch_xml.find('vd:dateOfProduction/vd:firstDate', NAMESPACES)
    year = int(date_produced_1_xml.find('dt:year', NAMESPACES).text)
    month = int(date_produced_1_xml.find('dt:month', NAMESPACES).text)
    date_produced_1 = ComplexDate(year=year, month=month)
    day_xml = date_produced_1_xml.find('dt:day', NAMESPACES)
    if day_xml is not None:
        date_produced_1.update('day', int(day_xml.text))
        hour_xml = date_produced_1_xml.find('dt:hour', NAMESPACES)
        if hour_xml is not None:
            date_produced_1.update('hour', int(hour_xml.text))
    stock_entry.date_produced_1 = date_produced_1.to_string()

    stock_entry.date_produced = date_produced_1.to_datetime()

    date_produced_2_xml = batch_xml.find('vd:dateOfProduction/vd:secondDate', NAMESPACES)
    if date_produced_2_xml is not None:
        year = int(date_produced_2_xml.find('dt:year', NAMESPACES).text)
        month = int(date_produced_2_xml.find('dt:month', NAMESPACES).text)
        date_produced_2 = ComplexDate(year=year, month=month)
        day_xml = date_produced_2_xml.find('dt:day', NAMESPACES)
        if day_xml is not None:
            date_produced_2.update('day', int(day_xml.text))
            hour_xml = date_produced_2_xml.find('dt:hour', NAMESPACES)
            if hour_xml is not None:
                date_produced_2.update('hour', int(hour_xml.text))
        stock_entry.date_produced_2 = date_produced_2.to_string()

    # date_expiry_1
    # date_expiry_2
    # date_expiry

    date_expiry_1_xml = batch_xml.find('vd:expiryDate/vd:firstDate', NAMESPACES)
    year = int(date_expiry_1_xml.find('dt:year', NAMESPACES).text)
    month = int(date_expiry_1_xml.find('dt:month', NAMESPACES).text)
    date_expiry_1 = ComplexDate(year=year, month=month)
    day_xml = date_expiry_1_xml.find('dt:day', NAMESPACES)
    if day_xml is not None:
        date_expiry_1.update('day', int(day_xml.text))
        hour_xml = date_expiry_1_xml.find('dt:hour', NAMESPACES)
        if hour_xml is not None:
            date_expiry_1.update('hour', int(hour_xml.text))
    stock_entry.date_expiry_1 = date_expiry_1.to_string()

    stock_entry.date_expiry = date_expiry_1.to_datetime()

    date_expiry_2_xml = batch_xml.find('vd:expiryDate/vd:secondDate', NAMESPACES)
    if date_expiry_2_xml is not None:
        year = int(date_expiry_2_xml.find('dt:year', NAMESPACES).text)
        month = int(date_expiry_2_xml.find('dt:month', NAMESPACES).text)
        date_expiry_2 = ComplexDate(year=year, month=month)
        day_xml = date_expiry_2_xml.find('dt:day', NAMESPACES)
        if day_xml is not None:
            date_expiry_2.update('day', int(day_xml.text))
            hour_xml = date_expiry_2_xml.find('dt:hour', NAMESPACES)
            if hour_xml is not None:
                date_expiry_2.update('hour', int(hour_xml.text))
        stock_entry.date_expiry_2 = date_expiry_2.to_string()

    # is_perishable

    stock_entry.is_perishable = batch_xml.find('vd:perishable', NAMESPACES).text == 'true'

    # origin_country
    # producer_name
    
    origin_country_xml = batch_xml.find('vd:origin/vd:country/dt:name', NAMESPACES)
    if origin_country_xml is not None:
        stock_entry.origin_country = origin_country_xml.text

    producer_name_xml = batch_xml.find('vd:origin/vd:producer/dt:enterprise/dt:name', NAMESPACES)
    if producer_name_xml is not None:
        stock_entry.producer_name = producer_name_xml.text

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
        package.level = int(package_xml.find('dt:level', NAMESPACES).text)
        packing_type_guid = package_xml.find('dt:packingType/bs:guid', NAMESPACES).text
        packing_type_uuid = package_xml.find('dt:packingType/bs:uuid', NAMESPACES).text
        packing_type_name = package_xml.find('dt:packingType/dt:name', NAMESPACES).text
        packing_type_glodal_id = package_xml.find('dt:packingType/dt:globalID', NAMESPACES).text
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

    # / for package


@shared_task
def update_stock_entries(credentials_id: int, initiator_login: str, enterprise_id: int):

    try:
        enterprise = Enterprise.objects.get(id=enterprise_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Предприятие не найдено!'}
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Не обнаружены параметры подключения!'}
    
    # last_updated_entry = StockEntry.objects.filter(enterprise=enterprise).order_by('-date_updated').first()

    if enterprise.stock_entries_last_updated is not None:
        update_mode = 'CHANGES'
        begin_date = enterprise.stock_entries_last_updated - timedelta(minutes=5) # rolloff slightly just in case
    else:
        update_mode = 'INITIAL'

    end_date = datetime.now(tz=TZ_MOSCOW)

    list_count = 1000
    list_offset = 0

    with transaction.atomic():

        while True: # repeat if has pages

            print(f'update_stock_entries: mode={update_mode}, list_offset={list_offset}')

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

            result = send_2step_soap_request(soap_request, credentials)

            if result['result'] != 'success':
                return result
            
            response = result['response']

            result_xml = ET.fromstring(response.text)
            
            # return {'result': 'error', 'message': 'Aborted.'}

            if update_mode == 'INITIAL':
                response_xml = result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse/apl:application/apl:result/merc:getStockEntryListResponse/vd:stockEntryList', NAMESPACES)
            else:
                response_xml = result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse/apl:application/apl:result/merc:getStockEntryChangesListResponse/vd:stockEntryList', NAMESPACES)

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
                
                '''
                # enterprise
                # guid
                # uuid
                # is_active
                # is_last
                # status
                # date_created
                # date_updated
                # previous_uuid
                # next_uuid
                # entry_number

                stock_entry.enterprise = enterprise
                stock_entry.guid = stock_entry_xml.find('bs:guid', NAMESPACES).text
                stock_entry.uuid = stock_entry_xml.find('bs:uuid', NAMESPACES).text
                stock_entry.is_active = stock_entry_xml.find('bs:active', NAMESPACES).text == 'true'
                stock_entry.is_last = stock_entry_xml.find('bs:last', NAMESPACES).text == 'true'
                stock_entry.status = int(stock_entry_xml.find('bs:status', NAMESPACES).text)
                stock_entry.date_created = datetime.fromisoformat(stock_entry_xml.find('bs:createDate', NAMESPACES).text)
                stock_entry.date_updated = datetime.fromisoformat(stock_entry_xml.find('bs:updateDate', NAMESPACES).text)
                previous_uuid_xml = stock_entry_xml.find('bs:previous', NAMESPACES)
                if previous_uuid_xml is not None:
                    stock_entry.previous_uuid = previous_uuid_xml.text
                next_uuid_xml = stock_entry_xml.find('bs:next', NAMESPACES)
                if next_uuid_xml is not None:
                    stock_entry.next_uuid = next_uuid_xml.text
                stock_entry.entry_number = stock_entry_xml.find('vd:entryNumber', NAMESPACES).text

                batch_xml = stock_entry_xml.find('vd:batch', NAMESPACES)
                
                # product_type
                # product_guid
                # product
                # subproduct_guid
                # subproduct

                stock_entry.product_type = int(batch_xml.find('vd:productType', NAMESPACES).text)
                stock_entry.product_guid = batch_xml.find('vd:product/bs:guid', NAMESPACES).text
                stock_entry.product = get_or_load_product_by_guid(credentials=credentials, product_guid=stock_entry.product_guid)
                stock_entry.subproduct_guid = batch_xml.find('vd:subProduct/bs:guid', NAMESPACES).text
                stock_entry.subproduct = get_or_load_subproduct_by_guid(credentials=credentials, subproduct_guid=stock_entry.subproduct_guid)
                
                # product_item_guid
                # product_item_name
                # product_item

                stock_entry.product_item_name = batch_xml.find('vd:productItem/dt:name', NAMESPACES).text
                product_item_guid_xml = batch_xml.find('vd:productItem/bs:guid', NAMESPACES)
                if product_item_guid_xml is not None:
                    stock_entry.product_item_guid = product_item_guid_xml.text
                    stock_entry.product_item = get_or_load_product_item_by_guid(credentials=credentials, product_item_guid=stock_entry.product_item_guid)

                # volume

                stock_entry.volume = Decimal(batch_xml.find('vd:volume', NAMESPACES).text)

                # unit
                
                unit_guid = batch_xml.find('vd:unit/bs:guid', NAMESPACES).text
                unit_name = batch_xml.find('vd:unit/dt:name', NAMESPACES).text

                stock_entry.unit = Unit.get_or_create(guid=unit_guid, name=unit_name)
                
                # date_produced_1
                # date_produced_2
                # date_produced

                date_produced_1_xml = batch_xml.find('vd:dateOfProduction/vd:firstDate', NAMESPACES)
                year = int(date_produced_1_xml.find('dt:year', NAMESPACES).text)
                month = int(date_produced_1_xml.find('dt:month', NAMESPACES).text)
                date_produced_1 = ComplexDate(year=year, month=month)
                day_xml = date_produced_1_xml.find('dt:day', NAMESPACES)
                if day_xml is not None:
                    date_produced_1.update('day', int(day_xml.text))
                    hour_xml = date_produced_1_xml.find('dt:hour', NAMESPACES)
                    if hour_xml is not None:
                        date_produced_1.update('hour', int(hour_xml.text))
                stock_entry.date_produced_1 = date_produced_1.to_string()

                stock_entry.date_produced = date_produced_1.to_datetime()

                date_produced_2_xml = batch_xml.find('vd:dateOfProduction/vd:secondDate', NAMESPACES)
                if date_produced_2_xml is not None:
                    year = int(date_produced_2_xml.find('dt:year', NAMESPACES).text)
                    month = int(date_produced_2_xml.find('dt:month', NAMESPACES).text)
                    date_produced_2 = ComplexDate(year=year, month=month)
                    day_xml = date_produced_2_xml.find('dt:day', NAMESPACES)
                    if day_xml is not None:
                        date_produced_2.update('day', int(day_xml.text))
                        hour_xml = date_produced_2_xml.find('dt:hour', NAMESPACES)
                        if hour_xml is not None:
                            date_produced_2.update('hour', int(hour_xml.text))
                    stock_entry.date_produced_2 = date_produced_2.to_string()

                # date_expiry_1
                # date_expiry_2
                # date_expiry

                date_expiry_1_xml = batch_xml.find('vd:expiryDate/vd:firstDate', NAMESPACES)
                year = int(date_expiry_1_xml.find('dt:year', NAMESPACES).text)
                month = int(date_expiry_1_xml.find('dt:month', NAMESPACES).text)
                date_expiry_1 = ComplexDate(year=year, month=month)
                day_xml = date_expiry_1_xml.find('dt:day', NAMESPACES)
                if day_xml is not None:
                    date_expiry_1.update('day', int(day_xml.text))
                    hour_xml = date_expiry_1_xml.find('dt:hour', NAMESPACES)
                    if hour_xml is not None:
                        date_expiry_1.update('hour', int(hour_xml.text))
                stock_entry.date_expiry_1 = date_expiry_1.to_string()

                stock_entry.date_expiry = date_expiry_1.to_datetime()

                date_expiry_2_xml = batch_xml.find('vd:expiryDate/vd:secondDate', NAMESPACES)
                if date_expiry_2_xml is not None:
                    year = int(date_expiry_2_xml.find('dt:year', NAMESPACES).text)
                    month = int(date_expiry_2_xml.find('dt:month', NAMESPACES).text)
                    date_expiry_2 = ComplexDate(year=year, month=month)
                    day_xml = date_expiry_2_xml.find('dt:day', NAMESPACES)
                    if day_xml is not None:
                        date_expiry_2.update('day', int(day_xml.text))
                        hour_xml = date_expiry_2_xml.find('dt:hour', NAMESPACES)
                        if hour_xml is not None:
                            date_expiry_2.update('hour', int(hour_xml.text))
                    stock_entry.date_expiry_2 = date_expiry_2.to_string()

                # is_perishable

                stock_entry.is_perishable = batch_xml.find('vd:perishable', NAMESPACES).text == 'true'

                # origin_country
                # producer_name
                
                origin_country_xml = batch_xml.find('vd:origin/vd:country/dt:name', NAMESPACES)
                if origin_country_xml is not None:
                    stock_entry.origin_country = origin_country_xml.text

                producer_name_xml = batch_xml.find('vd:origin/vd:producer/dt:enterprise/dt:name', NAMESPACES)
                if producer_name_xml is not None:
                    stock_entry.producer_name = producer_name_xml.text

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
                    package.level = int(package_xml.find('dt:level', NAMESPACES).text)
                    packing_type_guid = package_xml.find('dt:packingType/bs:guid', NAMESPACES).text
                    packing_type_uuid = package_xml.find('dt:packingType/bs:uuid', NAMESPACES).text
                    packing_type_name = package_xml.find('dt:packingType/dt:name', NAMESPACES).text
                    packing_type_glodal_id = package_xml.find('dt:packingType/dt:globalID', NAMESPACES).text
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

                # / for package'''

            # / for main

            total = int(response_xml.get('total'))

            print(f'Stock entry total: {total}')
            
            if total > list_offset + list_count:
                list_offset += list_count
                sleep(1.0)
            else:
                break
        # /while

        enterprise.stock_entries_last_updated = end_date
        enterprise.save()

    # /transaction.atomic   

    return {'result': 'success', 'message': f'Складские записи для предприятия успешно обновлены. Всего: {total}'}

@shared_task
def update_stock_entry_history(credentials_id: int, initiator_login: str, stock_entry_id: int):
    try:
        stock_entry = StockEntry.objects.get(id=stock_entry_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Запись журнала не найдена!'}
    
    try:
        credentials = VetisCredentials.objects.get(id=credentials_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Не обнаружены параметры подключения!'}
    
    enterprise = stock_entry.enterprise
    
    list_count = 1000
    list_offset = 0

    with transaction.atomic():

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

            result = send_2step_soap_request(soap_request, credentials)

            if result['result'] != 'success':
                return result
            
            response = result['response']

            result_xml = ET.fromstring(response.text)

            response_xml = result_xml.find('./soapenv:Body/apldef:receiveApplicationResultResponse/apl:application/apl:result/merc:getStockEntryVersionListResponse/vd:stockEntryList', NAMESPACES)

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

            # /for main

            total = int(response_xml.get('total'))

            print(f'Stock entry version total: {total}')
            
            if total > list_offset + list_count:
                list_offset += list_count
                sleep(1.0)
            else:
                break
        # /while
    # /transaction.atomic   

    return {'result': 'success', 'message': f'История для записи журнала успешно обновлена. Всего: {total}'}