import xml.etree.ElementTree as ET

from .settings import NAMESPACES


my_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
    <SOAP-ENV:Header xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" />
    <SOAP-ENV:Body xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <v2:getBusinessEntityByGuidResponse xmlns:bs="http://api.vetrf.ru/schema/cdm/base"
            xmlns:dt="http://api.vetrf.ru/schema/cdm/dictionary/v2"
            xmlns:v2="http://api.vetrf.ru/schema/cdm/registry/ws-definitions/v2">
            <dt:businessEntity>
                <bs:uuid>39bd2c2a-68fd-4f3a-8e1e-e5e27a65bec2</bs:uuid>
                <bs:guid>8786a0f7-daac-4417-821d-966975024785</bs:guid>
                <bs:active>true</bs:active>
                <bs:last>true</bs:last>
                <bs:status>200</bs:status>
                <bs:createDate>2025-08-04T14:44:08+03:00</bs:createDate>
                <bs:updateDate>2025-08-04T14:44:08+03:00</bs:updateDate>
                <bs:previous>1ca1b628-3db5-4196-b064-8481447ce38e</bs:previous>
                <dt:type>1</dt:type>
                <dt:name>ООО "ОКЕАНИКА"</dt:name>
                <dt:incorporationForm>
                    <bs:uuid>f381ed23-8afd-447b-8c45-652a1d6c2d0b</bs:uuid>
                    <dt:name>Общества с ограниченной ответственностью</dt:name>
                    <dt:code>12300</dt:code>
                </dt:incorporationForm>
                <dt:fullName>ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "ОКЕАНИКА"</dt:fullName>
                <dt:inn>9200022287</dt:inn>
                <dt:kpp>920001001</dt:kpp>
                <dt:ogrn>1249200002193</dt:ogrn>
                <dt:juridicalAddress>
                    <dt:country>
                        <bs:uuid>72a84b51-5c5e-11e1-b9b7-001966f192f1</bs:uuid>
                        <bs:guid>74a3cbb1-56fa-94f3-ab3f-e8db4940d96b</bs:guid>
                        <dt:name>Российская Федерация</dt:name>
                    </dt:country>
                    <dt:region>
                        <bs:uuid>6fdecb78-893a-4e3f-a5ba-aa062459463b</bs:uuid>
                        <bs:guid>6fdecb78-893a-4e3f-a5ba-aa062459463b</bs:guid>
                        <dt:name>Севастополь</dt:name>
                    </dt:region>
                    <dt:street>
                        <bs:uuid>97e1ed89-bc48-46c2-b98a-e50e87aa20c8</bs:uuid>
                        <bs:guid>31ee46bc-e476-4a20-ade0-8018d04e89d4</bs:guid>
                        <dt:name>Большая Морская</dt:name>
                    </dt:street>
                    <dt:house>ЗД. 23</dt:house>
                    <dt:building>СТР. 2</dt:building>
                    <dt:postIndex>299011</dt:postIndex>
                    <dt:addressView>299011, Российская Федерация, г. Севастополь, Большая Морская
                        ул., д. ЗД. 23, стр. СТР. 2</dt:addressView>
                </dt:juridicalAddress>
            </dt:businessEntity>
        </v2:getBusinessEntityByGuidResponse>
    </SOAP-ENV:Body>
</soapenv:Envelope>'''


def get_not_none(*args: ET.Element, default = ET.Element | None) -> ET.Element | None:
    for arg in args:
        if arg is not None:
            return arg
    return default

def get_not_none_text(*args: ET.Element, default: str = '') -> str:
    for arg in args:
        if arg is not None:
            return arg.text
    return default


def try_to_read():
    result_xml = ET.fromstring(my_xml)

    business_entity_xml = result_xml.find('./soapenv:Body/ws:getBusinessEntityByGuidResponse/dt:businessEntity', NAMESPACES)

    print(business_entity_xml.find('dt:name', NAMESPACES) == True)
    print(business_entity_xml.find('dt:fullName', NAMESPACES))
    print(business_entity_xml.find('dt:fio', NAMESPACES))

    name_xml = get_not_none_text(business_entity_xml.find('dt:name', NAMESPACES), business_entity_xml.find('dt:fullName', NAMESPACES), business_entity_xml.find('dt:fio', NAMESPACES), default='нет имени')

    print(name_xml)
