from django.template.loader import render_to_string


""" def _ns(ns: str, name: str) -> str:
    return f'{{{NAMESPACES[ns]}}}{name}'


def _register_namespaces() -> None:
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri) """

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


