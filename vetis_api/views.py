from django.shortcuts import render
from django.template.response import TemplateResponse

from .xml.build_xml import get_product_item_list


def apitest(request):
    xml = get_product_item_list('twtrewtretret')
    context = {
        'xml': xml
    }
    return TemplateResponse(request, 'vetis_api/apitest.html', context)