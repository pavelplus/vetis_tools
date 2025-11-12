from celery.result import AsyncResult

from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from .models import ApiRequestsHistoryRecord


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