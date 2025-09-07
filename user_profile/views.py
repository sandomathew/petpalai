from django.shortcuts import redirect, render
from .forms import UserForm, UserProfileForm
from django.contrib.auth.decorators import login_required


@login_required
def user_profile_view(request):
    user_form = UserForm(instance=request.user)
    profile_form = UserProfileForm(instance=request.user.profile)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, instance=request.user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('user_profile')

    return render(request,'user_profile/profile.html',{'user_form': user_form,'profile_form': profile_form})
