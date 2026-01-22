import json

from celery.result import AsyncResult
from datetime import datetime, date, time
from django_celery_results.models import TaskResult

from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from vetis_api.models import *
from vetis_api.tasks import (
    test_task,
    maintenance_task,
    reload_enterprises_task,
    reload_product_items_task,
    reload_product_subproduct_task,
    update_stock_entries_task,
    update_stock_entry_history_task,
    update_stock_entry_main_records_task,
    update_vet_documents_task
    )
from .util import build_url
from .forms import *
from .xls import xls_tools


def warning_messages(request):
    not_populated_main_count = StockEntryMain.objects.filter(is_populated=False).count()
    if not_populated_main_count:
        messages.add_message(request, messages.WARNING, f'Имеются не заполненные головные записи журнала ({not_populated_main_count})!')

    no_assort_group_count = ProductItem.objects.filter(assort_group__isnull=True).count()
    if no_assort_group_count:
        messages.add_message(request, messages.WARNING, f'Имеются наименования продукции без указанной ассортиментной группы ({no_assort_group_count})!')


def index(request):
    stock_entries_expiry = StockEntry.objects.filter(
        is_last=True,
        is_active=True,
        volume__gt=0,
        date_expiry__lte=(datetime.now(tz=TZ_MOSCOW)+timedelta(days=30))
        ).select_related('main').order_by('date_expiry', 'entry_number')

    last_updated_stock_entries = Enterprise.objects.filter(
        stock_entries_last_updated__isnull=False,
        stock_entries_last_updated__lte=(datetime.now(tz=TZ_MOSCOW)-timedelta(hours=3))
    ).order_by('stock_entries_last_updated')

    warning_messages(request)

    context = {
        'stock_entries_expiry': stock_entries_expiry,
        'last_updated_stock_entries': last_updated_stock_entries,
    }

    return TemplateResponse(request, 'main/index.html', context)


def select_workspace(request):
    be_id = request.session.get('business_entity', 0)
    ent_id = request.session.get('enterprise', 0)

    if request.headers.get('HX-Request', False):
        get_be_id = request.GET.get('business_entity', 0) or 0
        form = WorkspaceSelectionForm()
        form.fields['enterprise'].queryset = Enterprise.objects.filter(business_entity_id=get_be_id, is_allowed=True)
        context = {
            'form': form,
        }
        return TemplateResponse(request, 'main/includes/enterprise_select_field.html', context)

    if request.method == 'POST':
        post_be_id = request.POST.get('business_entity', 0)
        post_ent_id = request.POST.get('enterprise', 0)
        form = WorkspaceSelectionForm(request.POST)
        form.fields['enterprise'].queryset = Enterprise.objects.filter(business_entity_id=post_be_id, is_allowed=True)
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
    business_entity = get_object_or_404(BusinessEntity, id=id)
    context = {
        'business_entity': business_entity,
    }
    return TemplateResponse(request, 'main/business_entity_detail.html', context=context)


def product_items(request):

    product_items = ProductItem.objects.none()
    # product_items = ProductItem.objects.filter(is_active=True).select_related('product', 'subproduct').order_by('product_type', 'product__name', 'subproduct__name', 'name')
    show_business_entity = True
    by_levels = False

    if request.method == 'POST':
        form = ProductItemsFilterForm(request.POST)
        if form.is_valid():
            by_levels = form.cleaned_data['by_levels']
            order_by_clause = ['product_type', 'product__name', 'subproduct__name', 'name'] if by_levels else ['name']
            product_items = ProductItem.objects.select_related('product', 'subproduct').order_by(*order_by_clause)
            if form.cleaned_data['business_entity']:
                product_items = product_items.filter(producer=form.cleaned_data['business_entity'])
                show_business_entity = False
            if form.cleaned_data['search_query']:
                product_items = product_items.filter(name__icontains=form.cleaned_data['search_query'])
            if form.cleaned_data['no_assort_group']:
                product_items = product_items.filter(assort_group__isnull=True)

    else:
        form = ProductItemsFilterForm()

    context = {
        'form': form,
        'by_levels': by_levels,
        'show_business_entity': show_business_entity,
        'product_items': product_items,
    }
    return TemplateResponse(request, 'main/product_items.html', context=context)


def product_item_detail(request, id):
    product_item = get_object_or_404(ProductItem, id=id)

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.add_message(request, messages.ERROR, 'Пользователю запрещено менять ассортиментную группу.')
            return redirect(reverse('main:product_item_detail', kwargs={'id': product_item.id}))

        assort_form = ProductItemAssortGroupForm(request.POST)
        if assort_form.is_valid():
            if assort_form.cleaned_data['assort_group']:
                assort_group = get_object_or_404(AssortGroup, id=assort_form.cleaned_data['assort_group'].id)
                product_item.assort_group = assort_group
                messages.add_message(request, messages.INFO, 'Ассортиментная группа изменена.')
            else:
                product_item.assort_group = None
                messages.add_message(request, messages.WARNING, 'Ассортиментная группа удалена.')
            product_item.save()
            return redirect(reverse('main:product_item_detail', kwargs={'id': product_item.id}))


    else:
        assort_form = ProductItemAssortGroupForm(initial={'assort_group': product_item.assort_group})

    context = {
        'product_item': product_item,
        'assort_form': assort_form,
    }

    return TemplateResponse(request, 'main/product_item_detail.html', context=context)


def stock_entries(request):
    ent_id = request.session.get('enterprise', 0)

    if not ent_id:
        messages.add_message(request, messages.WARNING, 'Не выбрано активное предприятие!')
        return redirect('main:select_workspace')
    
    enterprise = get_object_or_404(Enterprise, id=ent_id)

    last_updated_entry = StockEntry.objects.filter(enterprise=enterprise).order_by('-date_updated').first()
    if last_updated_entry is not None:
        print(last_updated_entry.date_updated)
        entries_last_updated = last_updated_entry.date_updated.astimezone(TZ_MOSCOW).strftime('%d.%m.%Y %H:%M:%S')
    else:
        entries_last_updated = None

    if enterprise.stock_entries_last_updated:
        stock_last_updated = enterprise.stock_entries_last_updated.astimezone(TZ_MOSCOW).strftime('%d.%m.%Y %H:%M:%S')
    else:
        stock_last_updated = None

    has_collapsed_filters = False

    stock_entries = StockEntry.objects.none()
    if request.method == 'POST':
        form = StockEntriesFilterForm(request.POST)
        if form.is_valid():
            stock_entries = StockEntry.objects.filter(enterprise=enterprise, is_last=True, is_active=True).select_related('main').order_by('date_expiry', 'entry_number')
            if form.cleaned_data['status']:
                stock_entries = stock_entries.filter(main__initial_status=form.cleaned_data['status'])
            if form.cleaned_data['search_query']:
                print(f'...{form.cleaned_data['search_query']}...')
                for query in form.cleaned_data['search_query'].split():
                    if query[0] == '-' and len(query) > 1:
                        stock_entries = stock_entries.exclude(product_item_name__icontains=query[1:])
                    else:
                        stock_entries = stock_entries.filter(product_item_name__icontains=query)
            if form.cleaned_data['has_quantity']:
                stock_entries = stock_entries.filter(volume__gt=0)
            if form.cleaned_data['date_produced_begin']:
                date_produced_begin = datetime.combine(form.cleaned_data['date_produced_begin'], time(hour=0), tzinfo=TZ_MOSCOW)
                stock_entries = stock_entries.filter(date_produced__gte=date_produced_begin)
                has_collapsed_filters = True
            if form.cleaned_data['date_produced_end']:
                date_produced_end = datetime.combine(form.cleaned_data['date_produced_end'], time(hour=23, minute=59, second=59), tzinfo=TZ_MOSCOW)
                stock_entries = stock_entries.filter(date_produced__lte=date_produced_end)
                has_collapsed_filters = True
            if form.cleaned_data['date_created_begin']:
                date_created_begin = datetime.combine(form.cleaned_data['date_created_begin'], time(hour=0), tzinfo=TZ_MOSCOW)
                stock_entries = stock_entries.filter(date_created__gte=date_created_begin)
                has_collapsed_filters = True
            if form.cleaned_data['date_created_end']:
                date_created_end = datetime.combine(form.cleaned_data['date_created_end'], time(hour=23, minute=59, second=59), tzinfo=TZ_MOSCOW)
                stock_entries = stock_entries.filter(date_created__lte=date_created_end)
                has_collapsed_filters = True
            if form.cleaned_data['product']:
                stock_entries = stock_entries.filter(product= form.cleaned_data['product'])
                has_collapsed_filters = True

            stock_entries = stock_entries[:1000]

    else:
        form = StockEntriesFilterForm()

    # date_to_compare = datetime.now()

    warning_messages(request)

    context = {
        'form': form,
        'entries_last_updated': entries_last_updated,
        'stock_last_updated': stock_last_updated,
        # 'date_to_compare': date_to_compare,
        'stock_entries': stock_entries,
        'show_origin_detail': True,
        'btn_filters_class': 'btn-warning' if has_collapsed_filters else 'btn-secondary',
    }
    return TemplateResponse(request, 'main/stock_entries.html', context=context)


def stock_entry_detail(request, id):
    stock_entry = get_object_or_404(StockEntry, id=id)

    stock_entry_history = StockEntry.objects.filter(guid=stock_entry.guid).order_by('date_created')

    # comment = StockEntryComment.objects.filter(stock_entry_guid=stock_entry.guid).first()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.add_message(request, messages.ERROR, 'Пользователю запрещено обновление комментариев.')
            return redirect(reverse('main:stock_entry_detail', kwargs={'id': stock_entry.id}))

        comment_form = StockEntryCommentForm(request.POST)
        if comment_form.is_valid():
            if comment_form.cleaned_data['text']:
                stock_entry.main.comment_text = comment_form.cleaned_data['text']
                stock_entry.main.comment_important= comment_form.cleaned_data['important']
                messages.add_message(request, messages.INFO, 'Комментарий сохранен.')
            else:
                stock_entry.main.comment_text = ''
                stock_entry.main.comment_important = False
                messages.add_message(request, messages.WARNING, 'Комментарий удален.')

            stock_entry.main.save()
            return redirect(reverse('main:stock_entry_detail', kwargs={'id': stock_entry.id}))

    else:
        comment_form = StockEntryCommentForm()
        comment_form.initial={'important': stock_entry.main.comment_important, 'text': stock_entry.main.comment_text}

    context = {
        'stock_entry': stock_entry,
        'comment_form': comment_form,
        'stock_entry_history': stock_entry_history,
    }
    return TemplateResponse(request, 'main/stock_entry_detail.html', context=context)


def stock_entries_to_xls(request):

    ent_id = request.session.get('enterprise', 0)

    if not ent_id:
        messages.add_message(request, messages.WARNING, 'Не выбрано активное предприятие!')
        return redirect('main:select_workspace')
    
    enterprise = get_object_or_404(Enterprise, id=ent_id)

    filepath = xls_tools.stock_entries_to_xls(enterprise)

    if not filepath:
        messages.add_message(request, messages.ERROR, 'Не удалось сформировать файл!')
        return redirect('main:stock_entries')

    return FileResponse(open(filepath, 'rb'))


def vet_documents(request):
    ent_id = request.session.get('enterprise', 0)

    if not ent_id:
        messages.add_message(request, messages.WARNING, 'Не выбрано активное предприятие!')
        return redirect('main:select_workspace')
    
    enterprise = get_object_or_404(Enterprise, id=ent_id)

    ent_filter = Q(consignor_ent_guid=enterprise.guid) | Q(consignee_ent_guid=enterprise.guid) | Q(producer_ent_guid=enterprise.guid)

    last_updated_vetd = VetDocument.objects.filter(ent_filter).order_by('-date_updated').first()
    if last_updated_vetd is not None:
        vetd_records_last_updated = last_updated_vetd.date_updated.astimezone(TZ_MOSCOW).strftime('%d.%m.%Y %H:%M:%S')
    else:
        vetd_records_last_updated = None

    if enterprise.vet_documents_last_updated:
        vetd_last_updated = enterprise.vet_documents_last_updated.astimezone(TZ_MOSCOW).strftime('%d.%m.%Y %H:%M:%S')
    else:
        vetd_last_updated = None

    has_collapsed_filters = False

    vet_documents = VetDocument.objects.none()

    if request.method == 'POST':
        form = VetDocumentFilterForm(request.POST)
        vet_documents = VetDocument.objects.filter(ent_filter).order_by('-issue_date', '-date_updated')
        if form.is_valid():
            if form.cleaned_data['issue_date_begin']:
                vet_documents = vet_documents.filter(issue_date__gte=form.cleaned_data['issue_date_begin'])
            if form.cleaned_data['issue_date_end']:
                vet_documents = vet_documents.filter(issue_date__lte=form.cleaned_data['issue_date_end'])
            if form.cleaned_data['item_name_search_query']:
                for query in form.cleaned_data['item_name_search_query'].split():
                    if query[0] == '-' and len(query) > 1:
                        vet_documents = vet_documents.exclude(product_item_name__icontains=query[1:])
                    else:
                        vet_documents = vet_documents.filter(product_item_name__icontains=query)
            if form.cleaned_data['vetd_type']:
                vet_documents = vet_documents.filter(vetd_type=form.cleaned_data['vetd_type'])
                has_collapsed_filters = True
            if form.cleaned_data['consignor_search_query']:
                entity_search_filter = (
                    Q(consignor_be_name__icontains=form.cleaned_data['consignor_search_query'])
                    | Q(consignor_ent_name__icontains=form.cleaned_data['consignor_search_query'])
                )
                vet_documents = vet_documents.filter(entity_search_filter)
                has_collapsed_filters = True
            if form.cleaned_data['consignee_search_query']:
                entity_search_filter = (
                    Q(consignee_be_name__icontains=form.cleaned_data['consignee_search_query'])
                    | Q(consignee_ent_name__icontains=form.cleaned_data['consignee_search_query'])
                )
                vet_documents = vet_documents.filter(entity_search_filter)
                has_collapsed_filters = True

            vet_documents = vet_documents[:1000]

    else:
        form = VetDocumentFilterForm(initial={'issue_date_begin': date.today().isoformat()})

    context = {
        'form': form,
        'btn_filters_class': 'btn-warning' if has_collapsed_filters else 'btn-secondary',
        'vet_documents': vet_documents,
        'vetd_last_updated': vetd_last_updated,
        'vetd_records_last_updated': vetd_records_last_updated,
    }
    return TemplateResponse(request, 'main/vet_documents.html', context=context)


def vet_document_by_uuid(request, uuid):
    vet_document = VetDocument.objects.filter(uuid=uuid).first()

    if vet_document:
        return vet_document_detail(request, vet_document.id)
    
    messages.add_message(request, messages.ERROR, f'В базу не загружен ветеринарный документ с uuid={uuid}')
    return redirect('main:vet_documents')


def vet_document_detail(request, id):

    vet_document = get_object_or_404(VetDocument, id=id)

    context = {
        'vet_document': vet_document,
    }
    return TemplateResponse(request, 'main/vet_document_detail.html', context=context)


# htmx partial render
def task_info(request):

    task_id = request.GET.get('task_id')
    task_result = AsyncResult(task_id)

    context = {}
    if task_result:
        context = {
            'task_id': task_id,
            'task_ready': task_result.ready(),
            'task_result': task_result,
            'result_is_dict': isinstance(task_result.result, dict),
            'tick': ('.'*10)[:datetime.now().second%10+1] if not task_result.ready() else '',
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
        
        if not request.user.vetis_login:
            messages.add_message(request, messages.ERROR, 'Для пользователя не задан логин Ветис!')

        if credentials_id:
            if vetis_task == 'maintenance_task':
                task_id = maintenance_task.delay(credentials_id)
                return redirect(build_url('main:vetis_task', task_id=task_id))

            if vetis_task == 'reload_enterprises':
                business_entity_id = int(request.POST.get('business_entity_id'))
                task_id = reload_enterprises_task.delay(credentials_id, business_entity_id)
                next = reverse('main:business_entity_detail', args=[business_entity_id])
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))
            
            if vetis_task == 'reload_product_items':
                task_id = reload_product_items_task.delay(credentials_id, be.id)
                next = reverse('main:product_items')
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))
            
            if vetis_task == 'reload_product_subproduct':
                task_id = reload_product_subproduct_task.delay(credentials_id)
                next = reverse('main:product_items')
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))
            
            if vetis_task == 'update_stock_entries' and request.user.vetis_login:
                task_id = update_stock_entries_task.delay(credentials_id, request.user.vetis_login, ent_id)
                next = reverse('main:stock_entries')
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))

            if vetis_task == 'reload_stock_entry_history' and request.user.vetis_login:
                stock_entry_id = int(request.POST.get('stock_entry_id'))
                task_id = update_stock_entry_history_task.delay(credentials_id, request.user.vetis_login, stock_entry_id)
                next = reverse('main:stock_entry_detail', kwargs={'id': stock_entry_id})
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))
            
            if vetis_task == 'update_stock_entry_main_records' and request.user.vetis_login:
                task_id = update_stock_entry_main_records_task.delay(credentials_id, request.user.vetis_login, ent_id)
                return redirect(build_url('main:vetis_task', task_id=task_id))
            
            if vetis_task == 'update_vet_documents' and request.user.vetis_login:
                task_id = update_vet_documents_task.delay(credentials_id, request.user.vetis_login, ent_id)
                next = reverse('main:vet_documents')
                return redirect(build_url('main:vetis_task', task_id=task_id, next=next))

        else:
            messages.add_message(request, messages.ERROR, 'Не выбрано подключение!')

        messages.add_message(request, messages.ERROR, 'Запрос не обработан!')
        return redirect('.')
        
    # display task info
    context = {}
    return TemplateResponse(request, 'main/vetis_task.html', context)


def statistics(request):
    database_records = {
        'Хозяйствующие субъекты': BusinessEntity.objects.count(),
        'Предприятия': Enterprise.objects.count(),
        'Информация о прочих ХС': BusinessEntityInfo.objects.count(),
        'Информация о прочих предприятиях': EnterpriseInfo.objects.count(),
        'Информация о прочих предприятиях': EnterpriseInfo.objects.count(),
        'Типы продукции (product)': Product.objects.count(),
        'Продукция (subproduct)': SubProduct.objects.count(),
        'Наименования продукции': ProductItem.objects.count(),
        'Единицы измерения': Unit.objects.count(),
        'Виды упаковок': PackingType.objects.count(),
        'Записи журнала': StockEntryMain.objects.count(),
        'Версии записей журнала': StockEntry.objects.count(),
        'Ветеринарные документы': VetDocument.objects.count(),
        'История запросов Ветис': ApiRequestsHistoryRecord.objects.count(),
        'Результаты задач celery': TaskResult.objects.count(),
    }

    context = {
        'database_records': database_records
    }

    return TemplateResponse(request, 'main/statistics.html', context)