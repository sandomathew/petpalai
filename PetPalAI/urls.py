"""
URL configuration for PetPalAI project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('user_profile.urls')),
    path('admin/', admin.site.urls),
    path('petfood/analyze/', include('petfood_analyzer.urls')),
    path('profile/', include('user_profile.urls')),
    path('accounts/', include('accounts.urls')),  # Custom register view
    path('accounts/', include('django.contrib.auth.urls')),  # Built-in login/logout
    path('agent/', include('agent.urls')),
    path('pets/', include('pet_manager.urls')),
]

# Serve media files in development (DO NOT USE IN PRODUCTION)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
