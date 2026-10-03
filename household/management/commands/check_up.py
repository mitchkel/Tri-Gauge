from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from household.views import health
from household.integrations.up.client import UPClient, token_available
from household.integrations.up.exceptions import UPError


class Command(BaseCommand):
    help = 'Report internal readiness; --live deliberately pings UP and retrieves accounts without saving them.'

    def add_arguments(self, parser):
        parser.add_argument('--live', action='store_true', help='Make authenticated, read-only UP requests.')

    def handle(self, *args, **options):
        self.stdout.write('application: ok')
        database_ok = health(None).status_code == 200
        self.stdout.write('database: ' + ('ok' if database_ok else 'unavailable'))
        configured = token_available()
        self.stdout.write('UP_BANK_TOKEN: ' + ('available' if configured else 'unavailable'))
        self.stdout.write('up_connection: not checked')
        if not options['live']:
            return
        if not database_ok:
            raise CommandError('Database is not ready; no UP requests made.')
        client = UPClient()
        try:
            client.ping()
        except UPError as error:
            self.stdout.write('up_connection: failed')
            raise CommandError(str(error)) from None
        self.stdout.write('up_connection: successful')
        try:
            accounts = client.accounts()
        except UPError as error:
            raise CommandError('Account retrieval failed. ' + str(error)) from None
        self.stdout.write('account_count: ' + str(len(accounts)))
        counts = Counter(account.account_type for account in accounts)
        self.stdout.write('account_types: ' + (', '.join(f'{kind} ({count})' for kind, count in sorted(counts.items())) or 'none'))
