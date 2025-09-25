import requests

from django.template.loader import render_to_string

from .settings import NAMESPACES, ENDPOINTS


""" def _ns(ns: str, name: str) -> str:
    return f'{{{NAMESPACES[ns]}}}{name}'


def _register_namespaces() -> None:
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri) """

class AbstractRequest:
    endpoint = None
    soap_action = None

    def __init__():
        raise NotImplementedError

    def get_xml(self):
        raise NotImplementedError


class ProductItemListRequest(AbstractRequest):

    endpoint = ENDPOINTS['ProductService']
    soap_action = 'GetProductItemList'

    def __init__(self, business_entity_guid: str, list_count: int = 1000, list_offset: int = 0):
        self.business_entity_guid = business_entity_guid
        self.list_count = list_count
        self.list_offset = list_offset

    def get_xml(self) -> str:
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetProductItemList.xml', context)
    

class BusinessEntityByGuidRequest(AbstractRequest):

    endpoint = ENDPOINTS['EnterpriseService']
    soap_action = 'GetBusinessEntityByGuid'

    def __init__(self, business_entity_guid: str):
        self.business_entity_guid = business_entity_guid

    def get_xml(self):
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetBusinessEntityByGuid.xml', context)


def send_soap_request(request: AbstractRequest):
    headers = {
        'Content-Type': 'text/html;charset=UTF-8',
        'SOAPAction': request.soap_action,
    }
    body = request.get_xml()

    print('Sending SOAP request')

    response = requests.post(
            url=request.endpoint,
            auth=('kuzmenko-180702', 'Dt54Jdy4Y'),
            headers=headers,
            data=body
        )
    
    print('response: ' + str(response))

    return response