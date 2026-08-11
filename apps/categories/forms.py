from django import forms

from apps.core.forms import UniqueActiveNameFormMixin

from .models import Category


class CategoryForm(UniqueActiveNameFormMixin, forms.ModelForm):
    name_conflict_message = "You already have an active category with this name."

    class Meta:
        model = Category
        fields = ["name", "kind"]
