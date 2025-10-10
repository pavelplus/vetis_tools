import requests
import xml.etree.ElementTree as ET

from celery import shared_task

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from .models import BusinessEntity, ApiRequestsHistoryRecord, VetisCredentials, Enterprise
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
def reload_enterprises(business_entity_id: int):
    try:
        business_entity = BusinessEntity.objects.get(pk=business_entity_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Хозяйствующий субъект не найден!'}
    
    if business_entity.credentials == None:
        return {'result': 'error', 'message': 'Не настроены параметры подключения для запрошенного хозяйствующиего субъекта!'}
    
    list_count = 1000
    list_offset = 0

    with transaction.atomic():

        business_entity.enterprise_set.update(is_active=False)

        while True: # repeat if has pages

            soap_request = ActivityLocationList(business_entity.guid, list_count, list_offset)

            response = send_soap_request(soap_request, business_entity.credentials)

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