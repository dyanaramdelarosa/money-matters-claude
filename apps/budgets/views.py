from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import BudgetAmountEditForm, BudgetDefinitionForm
from .models import BudgetDefinition
from .services import get_or_create_period, spent_for_period, update_definition_amount


class BudgetListView(LoginRequiredMixin, ListView):
    model = BudgetDefinition
    template_name = "budgets/list.html"
    context_object_name = "budgets"

    def get_queryset(self):
        return (
            BudgetDefinition.objects.filter(user=self.request.user)
            .active()
            .select_related("category")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_currency"] = self.request.user.profile.base_currency
        rows = []
        for definition in context["budgets"]:
            period = get_or_create_period(definition)
            spent = spent_for_period(period)
            rows.append(
                {
                    "definition": definition,
                    "period": period,
                    "spent": spent,
                    "remaining": period.amount - spent,
                    "percent_used": (spent / period.amount * 100) if period.amount else None,
                }
            )
        context["rows"] = rows
        total_budgeted = sum((row["period"].amount for row in rows), Decimal("0.00"))
        total_spent = sum((row["spent"] for row in rows), Decimal("0.00"))
        context["totals"] = {
            "budgeted": total_budgeted,
            "spent": total_spent,
            "remaining": total_budgeted - total_spent,
            "percent_used": (total_spent / total_budgeted * 100) if total_budgeted else None,
        }
        return context


class BudgetCreateView(LoginRequiredMixin, CreateView):
    model = BudgetDefinition
    form_class = BudgetDefinitionForm
    template_name = "budgets/form.html"
    success_url = reverse_lazy("budgets:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.instance.user = self.request.user
        return form


class BudgetUpdateView(LoginRequiredMixin, UpdateView):
    model = BudgetDefinition
    form_class = BudgetAmountEditForm
    template_name = "budgets/form.html"
    success_url = reverse_lazy("budgets:list")

    def get_queryset(self):
        return BudgetDefinition.objects.filter(user=self.request.user)

    def form_valid(self, form):
        update_definition_amount(self.object, form.cleaned_data["amount"])
        return redirect(self.get_success_url())


class BudgetArchiveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        definition = get_object_or_404(BudgetDefinition, pk=pk, user=request.user)
        definition.archive()
        return redirect("budgets:list")
