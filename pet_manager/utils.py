from datetime import datetime

from .models import Pet
from django.contrib.auth.models import User

def create_pet_via_agent(user: User, pet_data: dict) -> str:
    """
    Create a new pet for the given user using structured pet_data.
    Expects keys like: name, species, gender, weight_lbs, breed, etc.
    """
    required_fields = ['name', 'species', 'breed']
    missing = [field for field in required_fields if field not in pet_data or not pet_data[field]]

    if missing:
        return {"success": False,
                "message": f"⚠️ Missing required pet fields: {', '.join(missing)}"
                }

    birth_date_str = pet_data.get('birth_date')
    birth_date = None
    if birth_date_str:
        try:
            # Handle different possible date formats from the LLM
            birth_date = datetime.strptime(birth_date_str, '%m/%d/%Y').date()
        except ValueError:
            return {"success": False,
                    "message": f"⚠️ Invalid date format for birth date: {birth_date_str}. Please use MM/DD/YYYY."
                    }

    # Create Pet object
    pet = Pet.objects.create(
        user=user,
        name=pet_data.get('name').title(),
        species=pet_data.get('species', 'unknown').lower(),
        gender=pet_data.get('gender', 'unknown').lower(),
        weight_lbs=pet_data.get('weight_lbs'),
        breed=pet_data.get('breed', ''),
        birth_date=birth_date,
        color=pet_data.get('color', ''),
        microchip_id=pet_data.get('microchip_id', ''),
        license_number=pet_data.get('license_number', ''),
        notes=pet_data.get('notes', '')
    )

    return {
        "success": True,
        "message": f"🦴 Added pet {pet.name} ({pet.species}) for {user.username}."
    }
