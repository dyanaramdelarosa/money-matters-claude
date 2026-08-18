from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from . import services
from .forms import AnalyticsFilterForm


def _resolve_range(request):
    form = AnalyticsFilterForm(request.GET or None)
    if form.is_valid():
        return services.resolve_range(
            form.cleaned_data.get("date_from"), form.cleaned_data.get("date_to")
        )
    return services.resolve_range(None, None)


def _floats(values):
    return [float(value) for value in values]


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_from, date_to = _resolve_range(self.request)
        context["filter_form"] = AnalyticsFilterForm(
            initial={"date_from": date_from, "date_to": date_to}
        )
        return context


class AnalyticsCardView(LoginRequiredMixin, View):
    template_name = None

    def get(self, request):
        date_from, date_to = _resolve_range(request)
        context = self.get_card_context(request.user, date_from, date_to)
        context["base_currency"] = request.user.profile.base_currency
        return render(request, self.template_name, context)

    def get_card_context(self, user, date_from, date_to):
        raise NotImplementedError


class ExpenseByCategoryCardView(AnalyticsCardView):
    template_name = "analytics/cards/_expense_by_category.html"

    def get_card_context(self, user, date_from, date_to):
        data = services.expense_by_category_series(user, date_from, date_to)
        chart = {
            "type": "line",
            "data": {
                "labels": [bucket.isoformat() for bucket in data["buckets"]],
                "datasets": [
                    {"label": name, "data": _floats(values)}
                    for name, values in data["series"].items()
                ],
            },
        }
        return {"chart": chart, "has_data": bool(data["series"])}


class IncomeExpenseTrendCardView(AnalyticsCardView):
    template_name = "analytics/cards/_income_expense_trend.html"

    def get_card_context(self, user, date_from, date_to):
        data = services.income_vs_expense_series(user, date_from, date_to)
        chart = {
            "type": "line",
            "data": {
                "labels": [bucket.isoformat() for bucket in data["buckets"]],
                "datasets": [
                    {"label": "Income", "data": _floats(data["income"])},
                    {"label": "Expense", "data": _floats(data["expense"])},
                ],
            },
        }
        has_data = any(data["income"]) or any(data["expense"])
        return {"chart": chart, "has_data": has_data}


class NetCashFlowCardView(AnalyticsCardView):
    template_name = "analytics/cards/_net_cash_flow.html"

    def get_card_context(self, user, date_from, date_to):
        data = services.net_cash_flow_series(user, date_from, date_to)
        chart = {
            "type": "bar",
            "data": {
                "labels": [bucket.isoformat() for bucket in data["buckets"]],
                "datasets": [{"label": "Net cash flow", "data": _floats(data["net"])}],
            },
        }
        total_net = sum(data["net"], Decimal("0.00"))
        return {"chart": chart, "total_net": total_net, "has_data": any(data["net"])}


class TopCategoriesCardView(AnalyticsCardView):
    template_name = "analytics/cards/_top_categories.html"

    def get_card_context(self, user, date_from, date_to):
        rows = services.top_spending_categories(user, date_from, date_to)
        chart = {
            "type": "doughnut",
            "data": {
                "labels": [row["category__name"] or "Uncategorized" for row in rows],
                "datasets": [{"data": _floats(row["total"] for row in rows)}],
            },
        }
        return {"chart": chart, "rows": rows, "has_data": bool(rows)}


class AccountBalanceHistoryCardView(AnalyticsCardView):
    template_name = "analytics/cards/_account_balance_history.html"

    def get_card_context(self, user, date_from, date_to):
        data = services.account_balance_history(user, date_from, date_to)
        chart = {
            "type": "line",
            "data": {
                "labels": [bucket.isoformat() for bucket in data["buckets"]],
                "datasets": [
                    {"label": account["account"], "data": _floats(account["values"])}
                    for account in data["accounts"]
                ],
            },
        }
        return {"chart": chart, "has_data": bool(data["accounts"])}


class BudgetVsActualCardView(AnalyticsCardView):
    template_name = "analytics/cards/_budget_vs_actual.html"

    def get_card_context(self, user, date_from, date_to):
        rows = services.budget_vs_actual(user, date_from=date_from, date_to=date_to)
        chart = {
            "type": "bar",
            "data": {
                "labels": [
                    [
                        row["label"],
                        f"{row['scope_label']} · {row['period_start']:%b %d}"
                        f"–{row['period_end']:%b %d}",
                    ]
                    for row in rows
                ],
                "datasets": [
                    {"label": "Budgeted", "data": _floats(row["budgeted"] for row in rows)},
                    {"label": "Spent", "data": _floats(row["spent"] for row in rows)},
                ],
            },
        }
        return {"chart": chart, "rows": rows, "has_data": bool(rows)}
