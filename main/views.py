from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.template.response import TemplateResponse
from django.contrib import messages

from vetis_api.models import BusinessEntity
from vetis_api.tasks import reload_enterprises


def index(request):
    return TemplateResponse(request, 'main/index.html', {})


def business_entities(request):
    business_entities = BusinessEntity.objects.all()
    context = {
        'business_entities': business_entities,
    }
    return TemplateResponse(request, 'main/business_entities.html', context=context)


def business_entity_detail(request, id):
    business_entity = get_object_or_404(BusinessEntity, pk=id)
    context = {
        'business_entity': business_entity,
    }
    return TemplateResponse(request, 'main/business_entity_detail.html', context=context)


def vetis_task(request):
    vetis_task = None
    if request.method == 'POST':
        vetis_task = request.POST['vetis_task']
        if vetis_task == 'reload_enterprises':
            business_entity_id = int(request.POST['business_entity_id'])
            result = reload_enterprises(14)
            if result['result'] == 'success':
                messages.add_message(request, messages.INFO, 'Список предприятий успешно обновлен.')
                return redirect(reverse('main:business_entity_detail', kwargs={'id': business_entity_id}))
            else:
                messages.add_message(request, messages.ERROR, result['message'])
                return redirect(reverse('main:vetis_task'))
        
    # Unknown task    
    messages.add_message(request, messages.ERROR, 'Ошибка! Задача не обработана!')
    return TemplateResponse(request, 'main/vetis_task.html', {})