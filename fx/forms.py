from django import forms
from .models import Currency, Rate


class QuoteRequestForm(forms.Form):
    source_currency = forms.CharField(max_length=3)
    target_currency = forms.CharField(max_length=3)
    amount = forms.DecimalField(max_digits=20, decimal_places=2, min_value=0.01)

    def clean_source_currency(self):
        code = self.cleaned_data['source_currency'].upper()
        try:
            currency = Currency.objects.get(code=code, active=True)
            return currency
        except Currency.DoesNotExist:
            raise forms.ValidationError(f"Currency {code} is invalid or inactive")

    def clean_target_currency(self):
        code = self.cleaned_data['target_currency'].upper()
        try:
            currency = Currency.objects.get(code=code, active=True)
            return currency
        except Currency.DoesNotExist:
            raise forms.ValidationError(f"Currency {code} is invalid or inactive")

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get('source_currency')
        target = cleaned_data.get('target_currency')

        if source and target and source == target:
            raise forms.ValidationError("Source and target currencies must be different")

        if source and target:
            try:
                Rate.objects.get(source=source, target=target)
            except Rate.DoesNotExist:
                raise forms.ValidationError(f"Exchange rate not available for {source.code}/{target.code}")

        return cleaned_data
