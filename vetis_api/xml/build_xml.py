from datetime import datetime

from django.template.loader import render_to_string

from ..models import TZ_MOSCOW


VETIS_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'


class AbstractRequest:
    endpoint_name = None
    soap_action = None

    def __init__():
        raise NotImplementedError()

    def get_xml(self):
        raise NotImplementedError()


class ProductByGuidRequest(AbstractRequest):
    endpoint_name = 'ProductService'
    soap_action = 'GetProductByGuid'

    def __init__(self, product_guid: str):
        self.product_guid = product_guid

    def get_xml(self) -> str:
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetProductByGuid.xml', context)
    

class SubproductByGuidRequest(AbstractRequest):
    endpoint_name = 'ProductService'
    soap_action = 'GetSubProductByGuid'

    def __init__(self, subproduct_guid: str):
        self.subproduct_guid = subproduct_guid

    def get_xml(self) -> str:
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetSubproductByGuid.xml', context)


class ProductItemByGuidRequest(AbstractRequest):
    endpoint_name = 'ProductService'
    soap_action = 'GetProductItemByGuid'

    def __init__(self, product_item_guid: str):
        self.product_item_guid = product_item_guid

    def get_xml(self) -> str:
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetProductItemByGuid.xml', context)


class ProductItemListRequest(AbstractRequest):

    endpoint_name = 'ProductService'
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

    endpoint_name = 'EnterpriseService'
    soap_action = 'GetBusinessEntityByGuid'

    def __init__(self, business_entity_guid: str):
        self.business_entity_guid = business_entity_guid

    def get_xml(self):
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetBusinessEntityByGuid.xml', context)
    

class ActivityLocationListRequest(AbstractRequest):

    endpoint_name = 'EnterpriseService'
    soap_action = 'GetActivityLocationList'

    def __init__(self, business_entity_guid: str, list_count: int = 1000, list_offset: int = 0):
        self.business_entity_guid = business_entity_guid
        self.list_count = list_count
        self.list_offset = list_offset

    def get_xml(self):
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetActivityLocationList.xml', context)


class GetStockEntryListRequest(AbstractRequest):

    endpoint_name = 'ApplicationManagementService'
    soap_action = 'submitApplicationRequest'

    def __init__(self, enterprise_guid: str, api_key: str, service_id: str, issuer_id: str, initiator_login: str, list_count: int = 1000, list_offset: int = 0):
        self.enterprise_guid = enterprise_guid
        self.api_key = api_key
        self.service_id = service_id
        self.issuer_id = issuer_id
        self.initiator_login = initiator_login
        self.list_count = list_count
        self.list_offset = list_offset
    
    def get_xml(self):
        self.issue_date = datetime.now().strftime(VETIS_DATETIME_FORMAT)
        self.local_transaction_id = datetime.now().strftime('%Y%m%d-%H%M%S')
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetStockEntryList.xml', context)
    

class GetStockEntryChangesListRequest(AbstractRequest):

    endpoint_name = 'ApplicationManagementService'
    soap_action = 'submitApplicationRequest'

    def __init__(self, enterprise_guid: str, begin_date: datetime, end_date: datetime, api_key: str, service_id: str, issuer_id: str, initiator_login: str, list_count: int = 1000, list_offset: int = 0):
        self.enterprise_guid = enterprise_guid
        self.begin_date = begin_date.astimezone(TZ_MOSCOW).strftime(VETIS_DATETIME_FORMAT)
        self.end_date = end_date.astimezone(TZ_MOSCOW).strftime(VETIS_DATETIME_FORMAT)
        self.api_key = api_key
        self.service_id = service_id
        self.issuer_id = issuer_id
        self.initiator_login = initiator_login
        self.list_count = list_count
        self.list_offset = list_offset
    
    def get_xml(self):
        self.issue_date = datetime.now().strftime(VETIS_DATETIME_FORMAT)
        self.local_transaction_id = datetime.now().strftime('%Y%m%d-%H%M%S')
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetStockEntryChangesList.xml', context)
    

class GetStockEntryVersionListRequest(AbstractRequest):

    endpoint_name = 'ApplicationManagementService'
    soap_action = 'submitApplicationRequest'

    def __init__(self, enterprise_guid: str, stock_entry_guid: str, api_key: str, service_id: str, issuer_id: str, initiator_login: str, list_count: int = 1000, list_offset: int = 0):
        self.enterprise_guid = enterprise_guid
        self.stock_entry_guid = stock_entry_guid
        self.api_key = api_key
        self.service_id = service_id
        self.issuer_id = issuer_id
        self.initiator_login = initiator_login
        self.list_count = list_count
        self.list_offset = list_offset
    
    def get_xml(self):
        self.issue_date = datetime.now().strftime(VETIS_DATETIME_FORMAT)
        self.local_transaction_id = datetime.now().strftime('%Y%m%d-%H%M%S')
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/GetStockEntryVersionList.xml', context)
        

class ReceiveApplicationResultRequest(AbstractRequest):

    endpoint_name = 'ApplicationManagementService'
    soap_action = 'receiveApplicationResult'

    def __init__(self, api_key: str, issuer_id: str, application_id: str):
        self.api_key = api_key
        self.issuer_id = issuer_id
        self.application_id = application_id

    def get_xml(self):
        context = {
            'vetis_request': self
        }
        return render_to_string('vetis_api/xml/ReceiveApplicationResult.xml', context)