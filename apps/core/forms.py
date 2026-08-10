from django import forms


class UniqueActiveNameFormMixin:
    """Validates that `name` is unique among the user's *active* records of
    this model, mirroring the conditional `UniqueConstraint(condition=Q(is_archived=False))`
    at the DB layer. `user` isn't a form field (it's set server-side by the
    view), so Django's automatic unique-constraint validation excludes it and
    never runs — without this, a name conflict surfaces as a raw
    `IntegrityError` at save() instead of a normal form error.
    """

    name_conflict_message = "You already have an active record with this name."

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"]
        conflicts = self._meta.model.objects.active().filter(user=self.user, name=name)
        if self.instance.pk:
            conflicts = conflicts.exclude(pk=self.instance.pk)
        if conflicts.exists():
            raise forms.ValidationError(self.name_conflict_message)
        return name
