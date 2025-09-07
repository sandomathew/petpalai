# petfood_analyzer/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_label_view, name='analyze_food'), # This view will be the home page
]