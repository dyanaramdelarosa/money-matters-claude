from django.urls import path

from . import views

app_name = "budgets"

urlpatterns = [
    path("", views.BudgetListView.as_view(), name="list"),
    path("new/", views.BudgetCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.BudgetUpdateView.as_view(), name="edit"),
    path("<int:pk>/archive/", views.BudgetArchiveView.as_view(), name="archive"),
]
