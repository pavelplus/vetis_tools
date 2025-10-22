from celery.result import AsyncResult

from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http import Http404
from django.template.response import TemplateResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from vetis_api.models import BusinessEntity, Enterprise, ProductItem, StockEntry
from vetis_api.tasks import test_task, reload_enterprises, reload_product_items, reload_product_subproduct, update_stock_entries
from .util import build_url
from .forms import WorkspaceSelectionForm, ProductItemsFilterForm, StockEntriesFilterForm


def index(request):
    return TemplateResponse(request, 'main/index.html', {})


def select_workspace(request):
    be_id = request.session.get('business_entity', 0)
    ent_id = request.session.get('enterprise', 0)

    if request.headers.get('HX-Request', False):
        get_be_id = request.GET.get('business_entity', 0) or 0
        form = WorkspaceSelectionForm()
        form.fields['enterprise'].queryset = Enterprise.objects.filter(business_entity_id=get_be_id)
        context = {
            'form': form,
        }
        return TemplateResponse(request, 'main/includes/enterprise_select_field.html', context)

    if request.method == 'POST':
        post_be_id = request.POST.get('business_entity', 0)
        post_ent_id = request.POST.get('enterprise', 0)
        form = WorkspaceSelectionForm(request.POST)
        form.fields['enterprise'].queryset = Enterprise.objects.filter(business_entity_id=post_be_id)
        if form.is_valid():
            be = get_object_or_404(BusinessEntity, id=post_be_id)
            if post_ent_id:
                ent = get_object_or_404(Enterprise, id=post_ent_id)

            request.session['business_entity'] = post_be_id
            request.session['enterprise'] = post_ent_id
            request.session['workspace_name'] = be.name
            if post_ent_id:
                request.session['workspace_name'] += f' - {ent}'

            return redirect('main:index')
            
    else:
        form = WorkspaceSelectionForm(initial={'business_entity': be_id, 'enterprise': ent_id})
        form.fields['enterprise'].queryset = Enterprise.objects.filter(business_entity_id=be_id)
    
    context = {
        'be_id': be_id,
        'ent_id': ent_id,
        'form': form,
    }

    return TemplateResponse(request, 'main/select_workspace.html', context)


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


def product_items(request):

    product_items = ProductItem.objects.none()

    if request.method == 'POST':
        product_items = ProductItem.objects.all()
        form = ProductItemsFilterForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['business_entity']:
                product_items = product_items.filter(producer=form.cleaned_data['business_entity'])

            if form.cleaned_data['search_query']:
                product_items = product_items.filter(name__icontains=form.cleaned_data['search_query'])
    else:
        form = ProductItemsFilterForm()

    context = {
        'form': form,
        'product_items': product_items,
    }
    return TemplateResponse(request, 'main/product_items.html', context=context)


def product_item_detail(request, id):
    product_item = get_object_or_404(ProductItem, id=id)

    context = {
        'product_item': product_item
    }

    return TemplateResponse(request, 'main/product_item_detail.html', context=context)


def stock_entries(request):
    ent_id = request.session.get('enterprise', 0)

    if not ent_id:
        messages.add_message(request, messages.WARNING, 'Не выбрано активное предприятие!')
        return redirect('main:select_workspace')

    stock_entries = StockEntry.objects.none()
    if request.method == 'POST':
        pass
    else:
        form = StockEntriesFilterForm()

    context = {
        'form': form,
        'stock_entries': stock_entries,
    }
    return TemplateResponse(request, 'main/stock_entries.html', context=context)



# htmx partial render
def task_info(request):

    task_id = request.GET.get('task_id')
    task_result = AsyncResult(task_id)
    
    context = {}
    if task_result:
        context['task_info'] = {
            'task_id': task_id,
            'state': task_result.state,
            'ready': task_result.ready(),
            'result': task_result.result,
        }

        http_status = 286 if task_result.ready() else 200
        return TemplateResponse(request, 'main/includes/task_info.html', context, status=http_status)
    else:
        raise Http404("Task not found.")


@login_required
def vetis_task(request):
    vetis_task = None
    if request.method == 'POST':
        vetis_task = request.POST.get('vetis_task')
        be_id = request.session.get('business_entity', 0)
        ent_id = request.session.get('enterprise', 0)

        try:
            be = BusinessEntity.objects.get(id=be_id)
            credentials_id = be.credentials.id
        except:
            credentials_id = None

        if vetis_task == 'test_task':
            task_id = test_task.delay()
            return redirect(build_url('main:vetis_task', task_id=task_id))

        if credentials_id:
            if vetis_task == 'reload_enterprises':
                business_entity_id = int(request.POST.get('business_entity_id'))
                task_id = reload_enterprises.delay(credentials_id, business_entity_id)
                next = reverse('main:business_entity_detail', args=[business_entity_id])
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))
            
            if vetis_task == 'reload_product_items':
                task_id = reload_product_items.delay(credentials_id, be.id)
                next = reverse('main:product_items')
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))
            
            if vetis_task == 'reload_product_subproduct':
                task_id = reload_product_subproduct.delay(credentials_id)
                next = reverse('main:product_items')
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))
            
            if vetis_task == 'update_stock_entries':
                if request.user.vetis_login:
                    task_id = update_stock_entries.delay(credentials_id, request.user.vetis_login, ent_id)
                    next = reverse('main:product_items')
                    return redirect(build_url('main:vetis_task', task_id=task_id, next=next))
                else:
                    messages.add_message(request, messages.ERROR, 'Для пользователя не задан логин Ветис!')

        else:
            messages.add_message(request, messages.ERROR, 'Не выбрано подключение!')
        
    # display task info
    context = {}
    return TemplateResponse(request, 'main/vetis_task.html', context)