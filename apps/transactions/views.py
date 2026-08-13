from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from apps.accounts.models import Account

from . import services
from .forms import AccountBalanceCorrectionForm, TransactionFilterForm, TransactionForm
from .models import Transaction, TransactionType


class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "transactions/list.html"
    context_object_name = "transactions"
    paginate_by = 25

    def get_queryset(self):
        qs = Transaction.objects.filter(user=self.request.user).select_related(
            "account", "transfer_to_account", "category"
        )
        self.filter_form = TransactionFilterForm(self.request.GET or None, user=self.request.user)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get("date_from"):
                qs = qs.filter(date__gte=data["date_from"])
            if data.get("date_to"):
                qs = qs.filter(date__lte=data["date_to"])
            if data.get("type"):
                qs = qs.filter(type=data["type"])
            if data.get("account"):
                qs = qs.filter(Q(account=data["account"]) | Q(transfer_to_account=data["account"]))
            if data.get("category"):
                qs = qs.filter(category=data["category"])
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        return context


class TransactionDetailView(LoginRequiredMixin, DetailView):
    model = Transaction
    template_name = "transactions/detail.html"
    context_object_name = "transaction"

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "transactions/form.html"
    success_url = reverse_lazy("transactions:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.instance.user = self.request.user
        return form

    def form_valid(self, form):
        form.instance.currency = form.instance.account.currency
        self.object = services.create_transaction(form.instance)
        return HttpResponseRedirect(self.get_success_url())


class TransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "transactions/form.html"
    success_url = reverse_lazy("transactions:list")

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def dispatch(self, request, *args, **kwargs):
        transaction = self.get_object()
        if transaction.type == TransactionType.ADJUSTMENT:
            messages.error(
                request,
                "Balance corrections can't be edited — delete it and create a new one instead.",
            )
            return redirect("transactions:detail", pk=transaction.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.currency = form.instance.account.currency
        self.object = services.update_transaction(form.instance)
        return HttpResponseRedirect(self.get_success_url())


class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    template_name = "transactions/confirm_delete.html"
    context_object_name = "transaction"
    success_url = reverse_lazy("transactions:list")

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def form_valid(self, form):
        services.delete_transaction(self.object)
        return HttpResponseRedirect(self.get_success_url())


class AccountBalanceCorrectionView(LoginRequiredMixin, FormView):
    form_class = AccountBalanceCorrectionForm
    template_name = "transactions/correct_balance_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.account = get_object_or_404(Account, pk=kwargs["account_pk"], user=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["account"] = self.account
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(account=self.account, **kwargs)

    def form_valid(self, form):
        delta = form.cleaned_data["new_balance"] - self.account.balance
        txn = Transaction(
            user=self.request.user,
            type=TransactionType.ADJUSTMENT,
            amount=delta,
            currency=self.account.currency,
            date=form.cleaned_data["date"],
            account=self.account,
            note=form.cleaned_data["note"],
        )
        services.create_transaction(txn)
        return redirect("accounts:edit", pk=self.account.pk)
