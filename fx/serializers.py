from rest_framework import serializers
from .models import Currency, Rate, Quote


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        exclude = ['active', 'created_at', 'updated_at']


class RateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate
        exclude = ['last_updated']


class QuoteSerializer(serializers.ModelSerializer):
    source_currency = CurrencySerializer(read_only=True)
    target_currency = CurrencySerializer(read_only=True)

    class Meta:
        model = Quote
        fields = ['quote_id', 'source_currency', 'target_currency', 'amount', 'rate', 'result', 'expiration_time']
