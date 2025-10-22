from django.urls import path
from . import views


app_name = 'vetis_api'

urlpatterns = [
    path('', views.apitest, name='apitest'),
    path('history/', views.api_requests_history, name='api_requests_history'),
    path('history/<int:id>', views.api_requests_history_detail, name='api_requests_history_detail'),
    path('task-info/', views.task_info, name='task_info'),
]