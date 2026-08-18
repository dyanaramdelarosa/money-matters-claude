from django import forms

_DISPATCH_ON_CHANGE = "document.dispatchEvent(new Event('analytics:filter-changed'))"


class AnalyticsFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "onchange": _DISPATCH_ON_CHANGE}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "onchange": _DISPATCH_ON_CHANGE}),
    )
