from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Pet

@login_required
def my_pets(request):
    pets = Pet.objects.filter(user=request.user)
    return render(request, 'pet_manager/my_pets.html', {'pets': pets})

