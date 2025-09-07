from django.db import models
from django.contrib.auth.models import User

class Pet(models.Model):
    SPECIES_CHOICES = [
        ('dog', 'Dog'),
        ('cat', 'Cat'),
        ('bird', 'Bird'),
        ('rabbit', 'Rabbit'),
        ('reptile', 'Reptile'),
        ('other', 'Other'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('neutered male', 'Neutered Male'),
        ('spayed female', 'Spayed Female'),
        ('unknown', 'Unknown'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pets')
    name = models.CharField(max_length=50)
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES)
    breed = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='unknown')
    birth_date = models.DateField(null=True, blank=True)
    weight_lbs = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    color = models.CharField(max_length=30, blank=True)
    microchip_id = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=100, blank=True, help_text="Some states require this.")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def age(self):
        from datetime import date
        if self.birth_date:
            return date.today().year - self.birth_date.year
        return None

    def __str__(self):
        return f"{self.name} ({self.species})"
