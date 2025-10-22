from celery.result import AsyncResult

from django.shortcuts import render, get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.http import Http404

from main.util import build_url
from .models import ApiRequestsHistoryRecord
from vetis_tools.celery import test_mul, debug_task


def apitest(request):

    context = {}

    # xml = get_product_item_list('twtrewtretret')
    # xml = ProductItemListRequest('sdadadasd').get_xml()
    # xml = ProductItemListRequest('sdadadasd').get_xml()
    # vetis_request = BusinessEntityByGuidRequest('29bad9e0-c666-4703-b30d-f54b5e895011')
    # vetis_request = ActivityLocationList('29bad9e0-c666-4703-b30d-f54b5e895011')
    # vetis_request = ProductItemListRequest('29910ac0-0d3a-4477-bb8d-2c1ddd5f7311')
    # response = send_soap_request(vetis_request)
    # context = {
    #     'soap_request': vetis_request.get_xml(),
    #     'response': response,
    # }
    # debug_task.delay()
    # ref = test_mul.delay(2,3)

    if request.method == 'POST' and request.POST.get('send_test_task'):
        task = test_mul.delay(2,3)
        # return redirect(f'{reverse('vetis_api:apitest')}?task_id={task.task_id}')
        return redirect(build_url('vetis_api:apitest', task_id=task.task_id))

    # if request.GET.get('task_id'):
    #     task_id = request.GET.get('task_id')
    #     res = AsyncResult(task_id)
    #     context['task_info'] = {
    #         'task_id': task_id,
    #         'res_state': res.state
    #     }

    return TemplateResponse(request, 'vetis_api/apitest.html', context)


def task_info(request):
    context = {}

    if request.GET.get('task_id'):
        task_id = request.GET.get('task_id')
        res = AsyncResult(task_id)
        context['task_info'] = {
            'task_id': task_id,
            'state': res.state,
            'ready': res.ready(),
            'result': res.result,
        }
        http_status = 200 if not res.ready() else 286
        return TemplateResponse(request, 'vetis_api/includes/task_info.html', context, status=http_status)
    else:
        raise Http404("Task not found.") 


def api_requests_history(request):
    requests_history = ApiRequestsHistoryRecord.objects.all()[:20]
    context = {
        'requests_history': requests_history,
    }
    return TemplateResponse(request, 'vetis_api/api_requests_history.html', context)


def api_requests_history_detail(request, id):
    record = get_object_or_404(ApiRequestsHistoryRecord, pk=id)
    context = {
        'record': record
    }
    return TemplateResponse(request, 'vetis_api/api_requests_history_detail.html', context)