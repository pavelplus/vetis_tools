from django import forms
from django.urls import reverse_lazy

from vetis_api.models import BusinessEntity, Enterprise, Product


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
    search_query = forms.CharField(max_length=100, label='Название', required=False)


class StockEntriesFilterForm(forms.Form):
    search_query = forms.CharField(max_length=100, label='Название', required=False, widget=forms.widgets.TextInput(attrs={'autocomplete': 'off'}))
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label='Продукция', required=False)
    has_quantity = forms.BooleanField(label='Непустые', initial=True, required=False)
    date_produced_begin = forms.DateField(label='Выпущено с', required=False, widget=forms.widgets.DateInput(attrs={'type': 'date'}))
    date_produced_end = forms.DateField(label='Выпущено по', required=False, widget=forms.widgets.DateInput(attrs={'type': 'date'}))