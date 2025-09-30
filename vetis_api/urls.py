from django.urls import path
from . import views


app_name = 'vetis_api'

urlpatterns = [
    path('', views.apitest, name='apitest'),
    path('history/', views.api_requests_history, name='api_requests_history'),
]