import requests
from time import sleep
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
    SubProduct
    )
from .xml.build_xml import *
from .xml.settings import NAMESPACES


# app = Celery('tasks', broker='pyamqp://guest@192.168.101.242//')


# PROD
ENDPOINTS_PROD = {
    'ProductService': 'https://api.vetrf.ru/platform/services/2.1/ProductService',
    'EnterpriseService': 'https://api.vetrf.ru/platform/services/2.1/EnterpriseService',
}

# TEST
ENDPOINTS_TEST = {
    'ProductService': 'https://api2.vetrf.ru:8002/platform/services/2.1/ProductService',
    'EnterpriseService': 'https://api2.vetrf.ru:8002/platform/services/2.1/EnterpriseService',
}


def send_soap_request(soap_request: AbstractRequest, credentials: VetisCredentials):
    headers = {
        'Content-Type': 'text/html;charset=UTF-8',
        'SOAPAction': soap_request.soap_action,
    }
    body = soap_request.get_xml()

    endpoint_url = ENDPOINTS_PROD[soap_request.endpoint_name] if credentials.is_productive else ENDPOINTS_TEST[soap_request.endpoint_name]

    response = requests.post(
            url=endpoint_url,
            auth=(credentials.login, credentials.password),
            headers=headers,
            data=body
        )
    
    record = ApiRequestsHistoryRecord()
    record.soap_action = soap_request.soap_action
    record.soap_request = soap_request.get_xml()
    record.response_status_code = response.status_code
    record.response_body = response.text
    record.comment = f'{credentials.name} {endpoint_url}'
    record.save()
    
    return response


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
        business_entity = BusinessEntity.objects.get(pk=business_entity_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Хозяйствующий субъект не найден!'}
    
    try:
        credentials = VetisCredentials.objects.get(pk=credentials_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Не обнаружены параметры подключения!'}
    
    list_count = 1000
    list_offset = 0

    with transaction.atomic():

        business_entity.enterprise_set.update(is_active=False)

        while True: # repeat if has pages

            soap_request = ActivityLocationListRequest(business_entity.guid, list_count, list_offset)

            response = send_soap_request(soap_request, credentials)

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


@shared_task
def reload_product_subproduct(credentials_id: int):
    """Update existing product and subproduct records form Vetis"""

    try:
        credentials = VetisCredentials.objects.get(pk=credentials_id)
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
        business_entity = BusinessEntity.objects.get(pk=business_entity_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Хозяйствующий субъект не найден!'}
    
    try:
        credentials = VetisCredentials.objects.get(pk=credentials_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Не обнаружены параметры подключения!'}
    
    list_count = 1000
    list_offset = 0

    with transaction.atomic():

        ProductItem.objects.filter(producer_guid=business_entity.guid)

        while True: # repeat if has pages

            print(f'reload_product_items: list_offset={list_offset}')

            soap_request = ProductItemListRequest(business_entity.guid, list_count, list_offset)

            response = send_soap_request(soap_request, credentials)

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
                product_item.name = product_item_xml.find('dt:name', NAMESPACES).text
                globalID_xml = product_item_xml.find('dt:globalID', NAMESPACES)
                if globalID_xml is not None:
                    product_item.gtin = globalID_xml.text
                    print(f'Found GTIN: {product_item.gtin}')
                product_item.product_type = int(product_item_xml.find('dt:productType', NAMESPACES).text)
                product_item.product_guid = product_item_xml.find('dt:product/bs:guid', NAMESPACES).text
                product_item.subproduct_guid = product_item_xml.find('dt:subProduct/bs:guid', NAMESPACES).text
                product_item.is_gost = product_item_xml.find('dt:correspondsToGost', NAMESPACES).text == 'true'
                if product_item.is_gost:
                    product_item.gost = product_item_xml.find('dt:gost', NAMESPACES).text
                product_item.producer_guid = product_item_xml.find('dt:producer/bs:guid', NAMESPACES).text
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

    return {'result': 'success', 'message': 'Список продукции обновлен.'}