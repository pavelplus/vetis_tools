import requests

from celery import Celery

from django.core.exceptions import ObjectDoesNotExist

from .models import BusinessEntity
from .xml.build_xml import *


app = Celery('tasks', broker='pyamqp://guest@192.168.101.242//')

@app.task
def add(x, y):
    return x + y


def send_soap_request(soap_request: AbstractRequest):
    headers = {
        'Content-Type': 'text/html;charset=UTF-8',
        'SOAPAction': soap_request.soap_action,
    }
    body = soap_request.get_xml()

    response = requests.post(
            url=soap_request.endpoint,
            auth=('kuzmenko-180702', 'Dt54Jdy4Y'), # Dt54Jdy4Y
            headers=headers,
            data=body
        )
    
    return response


def reload_enterprises(business_entity_id: int):
    try:
        business_entity = BusinessEntity.objects.get(pk=business_entity_id)
    except ObjectDoesNotExist:
        return {'result': 'error', 'message': 'Хозяйствующий субъект не найден!'}
    
    soap_request = ActivityLocationList(business_entity['guid'])

    # response = send_soap_request(soap_request)
    
    return {'result': 'success'}