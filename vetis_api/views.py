from django.shortcuts import render
from django.template.response import TemplateResponse

from .xml.build_xml import ProductItemListRequest, BusinessEntityByGuidRequest, ActivityLocationList
from .tasks import send_soap_request
from .models import ApiRequestsHistoryRecord


def apitest(request):

    # xml = get_product_item_list('twtrewtretret')
    # xml = ProductItemListRequest('sdadadasd').get_xml()
    # xml = ProductItemListRequest('sdadadasd').get_xml()
    # vetis_request = BusinessEntityByGuidRequest('29bad9e0-c666-4703-b30d-f54b5e895011')
    vetis_request = ActivityLocationList('29bad9e0-c666-4703-b30d-f54b5e895011')
    # vetis_request = ProductItemListRequest('29910ac0-0d3a-4477-bb8d-2c1ddd5f7311')
    response = send_soap_request(vetis_request)
    context = {
        'soap_request': vetis_request.get_xml(),
        'response': response,
    }
    return TemplateResponse(request, 'vetis_api/apitest.html', context)


def api_requests_history(request):
    requests_history = ApiRequestsHistoryRecord.objects.all()[:20]
    context = {
        'requests_history': requests_history,
    }
    return TemplateResponse(request, 'vetis_api/api_requests_history.html', context)