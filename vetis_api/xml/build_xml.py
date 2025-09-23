import xml.etree.ElementTree as ET

from .settings import NAMESPACES


def _ns(ns: str, name: str) -> str:
    return f'{{{NAMESPACES[ns]}}}{name}'


def _register_namespaces() -> None:
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri)


def _list_options_element(count: int, offset: int) -> ET.Element:
    list_options = ET.Element(_ns('bs', 'listOptions'))
    elem = ET.SubElement(list_options, _ns('bs', 'count'))
    elem.text = str(count)
    elem = ET.SubElement(list_options, _ns('bs', 'offset'))
    elem.text = str(offset)
    return list_options
    

def _make_envelope(body_content: ET.Element) -> ET.Element:
    envelope = ET.Element(_ns('soapenv', 'Envelope'))
    envelope.append(ET.Element(_ns('soapenv', 'Header')))
    body = ET.SubElement(envelope, _ns('soapenv', 'Body')) # envelope.append(ET.Element(_ns('soap', 'Body')))
    body.append(body_content)
    return envelope


def get_product_item_list(business_entity_guid: str, list_count: int = 1000, list_offset: int = 0) -> str:
    request = ET.Element(_ns('ws', 'getProductItemListRequest'))
    request.append(_list_options_element(list_count, list_offset))
    # TODO: append business entity element
    envelope = _make_envelope(request)
    _register_namespaces()
    return ET.tostring(envelope, encoding='utf-8').decode('utf-8')