from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from .models import Profile


class ProfileView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = "users/profile.html"
    context_object_name = "profile"

    def get_object(self, queryset=None):
        return self.request.user.profile
