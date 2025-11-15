import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True, primary_key=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    symbol_position = models.CharField(
        max_length=10,
        choices=[('before', 'Before'), ('after', 'After')],
        default='before'
    )
    thousands_separator = models.CharField(max_length=1, default=',')
    decimal_separator = models.CharField(max_length=1, default='.')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Currencies'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Rate(models.Model):
    source = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rates_as_source'
    )
    target = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rates_as_target'
    )
    mean = models.DecimalField(max_digits=20, decimal_places=6)
    buying = models.DecimalField(max_digits=20, decimal_places=6)
    selling = models.DecimalField(max_digits=20, decimal_places=6)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['source', 'target']
        ordering = ['source', 'target']

    def __str__(self):
        return f"{self.source.code}/{self.target.code}: {self.mean}"


class Quote(models.Model):
    quote_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='quotes_as_source'
    )
    target_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='quotes_as_target'
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    rate = models.DecimalField(max_digits=20, decimal_places=6)
    result = models.DecimalField(max_digits=20, decimal_places=6)
    time_created = models.DateTimeField(auto_now_add=True)
    time_updated = models.DateTimeField(auto_now=True)
    expiration_time = models.DateTimeField()

    class Meta:
        ordering = ['-time_created']

    def __str__(self):
        return f"Quote {self.quote_id}: {self.amount} {self.source_currency.code} → {self.target_currency.code}"

    def save(self, *args, **kwargs):
        if not self.expiration_time:
            quote_validity = getattr(settings, 'QUOTE_VALIDITY', 60)
            self.expiration_time = timezone.now() + timedelta(seconds=quote_validity)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expiration_time
