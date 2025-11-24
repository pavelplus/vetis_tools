from django import forms
from django.urls import reverse_lazy

from vetis_api.models import BusinessEntity, Enterprise, Product, STOCK_ENTRY_STATUS_CHOICES, VetDocument, AssortGroup


class WorkspaceSelectionForm(forms.Form):
    business_entity = forms.ModelChoiceField(
        queryset=BusinessEntity.objects.exclude(credentials=None),
        required=True,
        label='Хозяйствующий субъект',
        widget=forms.Select(attrs={'hx-get': reverse_lazy('main:select_workspace'), 'hx-target': '#enterprise'})  # reverse('main:enterprise_options')
        )
    enterprise = forms.ModelChoiceField(queryset=Enterprise.objects.all(), label='Предприятие', required=False)


class ProductItemsFilterForm(forms.Form):
    business_entity = forms.ModelChoiceField(queryset=BusinessEntity.objects.all(), label='Владелец', required=False)
    search_query = forms.CharField(max_length=100, label='Название', required=False, widget=forms.widgets.TextInput(attrs={'autocomplete': 'off'}))
    by_levels = forms.BooleanField(label='По уровням', required=False)
    no_assort_group = forms.BooleanField(label='Без группы', required=False)


class ProductItemAssortGroupForm(forms.Form):
    assort_group = forms.ModelChoiceField(queryset=AssortGroup.objects.all(), label='Ассортиментная группа', required=False)


class StockEntriesFilterForm(forms.Form):
    search_query = forms.CharField(max_length=100, label='Наименование', required=False, widget=forms.widgets.TextInput(attrs={'autocomplete': 'off'}))
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label='Тип продукции', required=False)
    status = forms.ChoiceField(label='Исходный статус', choices=((None, '---------'),) + STOCK_ENTRY_STATUS_CHOICES, required=False)
    has_quantity = forms.BooleanField(label='Непустые', initial=True, required=False)
    date_produced_begin = forms.DateField(label='Выпущено с', required=False, widget=forms.widgets.DateInput(attrs={'type': 'date'}))
    date_produced_end = forms.DateField(label='Выпущено по', required=False, widget=forms.widgets.DateInput(attrs={'type': 'date'}))
    date_created_begin = forms.DateField(label='Изменено с', required=False, widget=forms.widgets.DateInput(attrs={'type': 'date'}))
    date_created_end = forms.DateField(label='Изменено по', required=False, widget=forms.widgets.DateInput(attrs={'type': 'date'}))


class StockEntryCommentForm(forms.Form):
    important = forms.BooleanField(required=False, label='Важно')
    text = forms.CharField(max_length=255, required=False, label='Комментарий', widget=forms.widgets.TextInput(attrs={'autocomplete': 'off'}))


class VetDocumentFilterForm(forms.Form):
    vetd_type = forms.ChoiceField(label='Тип документа', choices=((None, '---------'),) + VetDocument.VETDTYPE_CHOICES, required=False)
    issue_date_begin = forms.DateField(label='Дата с', widget=forms.widgets.DateInput(attrs={'type': 'date'}))
    issue_date_end = forms.DateField(label='Дата по', required=False, widget=forms.widgets.DateInput(attrs={'type': 'date'}))
    item_name_search_query = forms.CharField(max_length=100, label='Наименование продукции', required=False, widget=forms.widgets.TextInput(attrs={'autocomplete': 'off'}))
    consignor_search_query = forms.CharField(max_length=100, label='Отправитель', required=False, widget=forms.widgets.TextInput(attrs={'autocomplete': 'off'}))
    consignee_search_query = forms.CharField(max_length=100, label='Получатель', required=False, widget=forms.widgets.TextInput(attrs={'autocomplete': 'off'}))
