from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.index, name='index'),
    path('business_entities/', views.business_entities, name='business_entities'),
    path('business_entities/<int:id>', views.business_entity_detail, name='business_entity_detail'),
    path('vetis-task/', views.vetis_task, name='vetis_task'),
]