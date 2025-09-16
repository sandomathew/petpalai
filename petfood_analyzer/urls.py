# petfood_analyzer/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('analyze_label/', views.upload_label_view, name='analyze_food'), # This view will be the home page
    path('start_stream/', views.start_stream_analysis, name='start_stream_analysis'),
    path('stream_data/<str:task_id>/', views.event_stream, name='stream_data'),

]