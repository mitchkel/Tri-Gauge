from django.urls import path
from household import views

urlpatterns = [
    path("", views.page, {"section": "Dashboard"}, name="dashboard"),
    path("ledger/", views.page, {"section": "Live Ledger"}, name="ledger"),
    path("rules/", views.page, {"section": "Rules"}, name="rules"),
    path("settings/", views.page, {"section": "Settings"}, name="settings"),
    path("health/", views.health, name="health"),
]
