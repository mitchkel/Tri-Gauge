from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import BankAccount, ClassificationRule, HouseholdCycle, ManualOverride, RawTransaction, SyncState, TransactionClassification


@override_settings(SECURE_SSL_REDIRECT=False)
class FoundationTests(TestCase):
    def test_navigation_and_secret_not_rendered(self):
        with patch.dict("os.environ", {"UP_BANK_TOKEN": "fake-sensitive-test-value"}):
            for path, heading in [("/", "Dashboard"), ("/ledger/", "Live Ledger"), ("/rules/", "Rules"), ("/settings/", "Settings")]:
                response = self.client.get(path)
                self.assertContains(response, f"<h1>{heading}</h1>")
                self.assertNotContains(response, "fake-sensitive-test-value")
                for destination in ("/ledger/", "/rules/", "/settings/"):
                    self.assertContains(response, f'href="{destination}"')

    def test_health_checks_database_and_handles_failure(self):
        self.assertEqual(self.client.get("/health/").json()["database"], "ok")
        with patch("household.views.BankAccount.objects.exists", side_effect=DatabaseError("private-details")):
            response = self.client.get("/health/")
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "private-details", status_code=503)

    def test_database_relationships_and_exact_money(self):
        account = BankAccount.objects.create(external_id="fake-account", name="Household")
        item = RawTransaction.objects.create(account=account, external_id="fake-transaction", occurred_at=timezone.now(), amount=Decimal("-12.34"))
        cycle = HouseholdCycle.objects.create(name="Example", starts_on=date(2026, 1, 1), ends_on=date(2026, 1, 31))
        rule = ClassificationRule.objects.create(name="Placeholder", category="Groceries")
        TransactionClassification.objects.create(transaction=item, category="Groceries", rule=rule, cycle=cycle)
        ManualOverride.objects.create(transaction=item, category="Household", reason="Example correction")
        SyncState.objects.create(provider="up", cursor="fake-pagination-cursor")
        item.refresh_from_db()
        self.assertEqual(item.amount, Decimal("-12.34"))
        self.assertEqual(item.classification.cycle, cycle)
        self.assertEqual(item.manual_override.category, "Household")
        with self.assertRaises(IntegrityError), transaction.atomic():
            RawTransaction.objects.create(account=account, external_id="fake-transaction", occurred_at=timezone.now(), amount=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HouseholdCycle.objects.create(name="Invalid", starts_on=date(2026, 2, 1), ends_on=date(2026, 1, 1))
