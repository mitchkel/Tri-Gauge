from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from .models import BankAccount, ClassificationRule, HouseholdCycle, ManualOverride, RawTransaction, SyncState, TransactionClassification


def page(request, section):
    return render(request, "household/page.html", {"section": section})


def health(request):
    try:
        # Query every application table: an open SQLite connection alone would
        # incorrectly report readiness before migrations have been applied.
        for model in (BankAccount, RawTransaction, TransactionClassification,
                      ClassificationRule, ManualOverride, HouseholdCycle, SyncState):
            model.objects.exists()
    except DatabaseError:
        return JsonResponse({"status": "unavailable", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})
