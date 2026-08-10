from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import AccountCreateForm, AccountEditForm
from .models import Account


class AccountListView(LoginRequiredMixin, ListView):
    model = Account
    template_name = "accounts/list.html"
    context_object_name = "accounts"

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user).active()


class AccountDetailView(LoginRequiredMixin, DetailView):
    model = Account
    template_name = "accounts/detail.html"
    context_object_name = "account"

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)


class AccountCreateView(LoginRequiredMixin, CreateView):
    model = Account
    form_class = AccountCreateForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("accounts:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.instance.user = self.request.user
        form.instance.currency = self.request.user.profile.base_currency
        return form


class AccountUpdateView(LoginRequiredMixin, UpdateView):
    model = Account
    form_class = AccountEditForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("accounts:list")

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class AccountArchiveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        account = get_object_or_404(Account, pk=pk, user=request.user)
        account.archive()
        return redirect("accounts:list")
