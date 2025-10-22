from django.urls import path
from . import views


app_name = 'main'

urlpatterns = [
    path('', views.index, name='index'),
    path('select-workspace/', views.select_workspace, name='select_workspace'),
    path('business_entities/', views.business_entities, name='business_entities'),
    path('business_entities/<int:id>', views.business_entity_detail, name='business_entity_detail'),
    path('product-items/', views.product_items, name='product_items'),
    path('product-items/<int:id>', views.product_item_detail, name='product_item_detail'),
    path('stock/', views.stock_entries, name='stock_entries'),
    path('vetis-task/', views.vetis_task, name='vetis_task'),
    path('task-info/', views.task_info, name='task_info'),
]