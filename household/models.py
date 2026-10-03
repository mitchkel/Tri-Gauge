from django.db import models


class BankAccount(models.Model):
    external_id = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=200)
    currency = models.CharField(max_length=3, default="AUD")
    created_at = models.DateTimeField(auto_now_add=True)


class HouseholdCycle(models.Model):
    name = models.CharField(max_length=100)
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_on__gte=models.F("starts_on")), name="cycle_dates_ordered")]


class RawTransaction(models.Model):
    account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="transactions")
    external_id = models.CharField(max_length=128, unique=True)
    occurred_at = models.DateTimeField(db_index=True)
    description = models.TextField(blank=True)
    # Signed decimal amount; never use floating-point arithmetic for money.
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="AUD")
    raw_payload = models.JSONField(default=dict)
    imported_at = models.DateTimeField(auto_now_add=True)


class ClassificationRule(models.Model):
    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=0)
    criteria = models.JSONField(default=dict)
    category = models.CharField(max_length=100)
    # Criteria format and execution are intentionally deferred.


class TransactionClassification(models.Model):
    transaction = models.OneToOneField(RawTransaction, on_delete=models.CASCADE, related_name="classification")
    category = models.CharField(max_length=100)
    rule = models.ForeignKey(ClassificationRule, null=True, blank=True, on_delete=models.SET_NULL)
    cycle = models.ForeignKey(HouseholdCycle, null=True, blank=True, on_delete=models.SET_NULL)
    classified_at = models.DateTimeField(auto_now=True)


class ManualOverride(models.Model):
    transaction = models.OneToOneField(RawTransaction, on_delete=models.CASCADE, related_name="manual_override")
    category = models.CharField(max_length=100)
    reason = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class SyncState(models.Model):
    provider = models.CharField(max_length=50, unique=True)
    cursor = models.TextField(blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    # Pagination state only. Never store credentials or authorization headers here.
