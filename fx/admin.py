from django.contrib import admin
from .models import Currency, Rate, Quote


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'active', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['code', 'name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Rate)
class RateAdmin(admin.ModelAdmin):
    list_display = ['source', 'target', 'mean', 'buying', 'selling', 'last_updated']
    list_filter = ['source', 'target', 'last_updated']
    search_fields = ['source__code', 'target__code']
    readonly_fields = ['last_updated']


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ['quote_id', 'source_currency', 'target_currency', 'amount', 'rate', 'result', 'time_created', 'expiration_time', 'is_expired']
    list_filter = ['source_currency', 'target_currency', 'time_created']
    search_fields = ['quote_id', 'source_currency__code', 'target_currency__code']
    readonly_fields = ['quote_id', 'time_created', 'time_updated', 'expiration_time']

    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
