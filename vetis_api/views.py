from django.shortcuts import render
from django.template.response import TemplateResponse

from .xml.build_xml import ProductItemListRequest, BusinessEntityByGuidRequest, send_soap_request


def apitest(request):
    # xml = get_product_item_list('twtrewtretret')
    # xml = ProductItemListRequest('sdadadasd').get_xml()
    # xml = ProductItemListRequest('sdadadasd').get_xml()
    vetis_request = BusinessEntityByGuidRequest('29910ac0-0d3a-4477-bb8d-2c1ddd5f7311')
    # vetis_request = ProductItemListRequest('29910ac0-0d3a-4477-bb8d-2c1ddd5f7311')
    response = send_soap_request(vetis_request)
    context = {
        'response': response,
    }
    return TemplateResponse(request, 'vetis_api/apitest.html', context)