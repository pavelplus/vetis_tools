from django.urls import path
from . import views


app_name = 'main'

urlpatterns = [
    path('', views.index, name='index'),
    path('select-workspace/', views.select_workspace, name='select_workspace'),
    path('business-entities/', views.business_entities, name='business_entities'),
    path('business-entities/<int:id>', views.business_entity_detail, name='business_entity_detail'),
    path('product-items/', views.product_items, name='product_items'),
    path('product-items/<int:id>', views.product_item_detail, name='product_item_detail'),
    path('stock/', views.stock_entries, name='stock_entries'),
    path('stock/<int:id>', views.stock_entry_detail, name='stock_entry_detail'),
    path('stock-download', views.stock_entries_to_xls, name='stock_entries_to_xls'),
    path('vetd/', views.vet_documents, name='vet_documents'),
    path('vetd/<int:id>', views.vet_document_detail, name='vet_document_detail'),
    path('vetd-uuid/<str:uuid>', views.vet_document_by_uuid, name='vet_document_by_uuid'),
    path('vetis-task/', views.vetis_task, name='vetis_task'),
    path('task-info/', views.task_info, name='task_info'),
    path('statistics/', views.statistics, name='statistics'),
]