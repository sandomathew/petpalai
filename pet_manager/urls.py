from django.urls import path
from .views import my_pets

urlpatterns = [
    path('my-pets/', my_pets, name='my_pets'),
]