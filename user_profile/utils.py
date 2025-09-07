from django.contrib.auth.models import User
from .models import  UserProfile

def register_user_via_agent(name, email):
    username = email.split('@')[0]

    # Check if user exists
    if User.objects.filter(email=email).exists():
        return f"🔁 A user with email *{email}* already exists." , User.objects.filter(email=email)

    # Create the user (uses default Django User model)
    user = User.objects.create_user(
        username=username,
        email=email,
        password='Temp@123'  # Temporary password
    )

    # Create a profile with the given name as nickname
    UserProfile.objects.create(
        user=user,
        nickname=name
    )

    return {"success": True,
            "message": f"🎉 Registered *{name}* with email *{email}*. Temporary password: `Temp@123`"
            } , user

