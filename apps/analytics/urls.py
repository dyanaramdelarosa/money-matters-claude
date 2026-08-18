from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path(
        "cards/expense-by-category/",
        views.ExpenseByCategoryCardView.as_view(),
        name="card-expense-by-category",
    ),
    path(
        "cards/income-expense-trend/",
        views.IncomeExpenseTrendCardView.as_view(),
        name="card-income-expense-trend",
    ),
    path("cards/net-cash-flow/", views.NetCashFlowCardView.as_view(), name="card-net-cash-flow"),
    path(
        "cards/top-categories/", views.TopCategoriesCardView.as_view(), name="card-top-categories"
    ),
    path(
        "cards/account-balance-history/",
        views.AccountBalanceHistoryCardView.as_view(),
        name="card-account-balance-history",
    ),
    path(
        "cards/budget-vs-actual/",
        views.BudgetVsActualCardView.as_view(),
        name="card-budget-vs-actual",
    ),
]
