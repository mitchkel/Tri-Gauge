import io
import os
from unittest.mock import Mock, patch

import requests
from django.core.management import call_command
from django.test import TestCase, override_settings

from household.integrations.up.client import BASE_URL, UPClient
from household.integrations.up.exceptions import AuthenticationError, ConfigurationError, NetworkError, RateLimitError, ResponseError
from household.models import BankAccount

FAKE_TOKEN = 'fake-test-credential'


def account(identifier='fake-account', kind='TRANSACTIONAL'):
    return {'type': 'accounts', 'id': identifier, 'attributes': {
        'displayName': 'Fake household account', 'accountType': kind,
        'balance': {'currencyCode': 'AUD', 'value': '0.00'}}}


def response(payload=None, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    return result


@override_settings(SECURE_SSL_REDIRECT=False)
class UPTests(TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'UP_BANK_TOKEN': FAKE_TOKEN})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.session_patch = patch('household.integrations.up.client.requests.Session')
        self.session = self.session_patch.start().return_value.__enter__.return_value
        self.addCleanup(self.session_patch.stop)
        self.client_up = UPClient()

    def test_missing_token(self):
        with patch.dict(os.environ, {'UP_BANK_TOKEN': ''}):
            with self.assertRaises(ConfigurationError):
                self.client_up.ping()
        self.session.get.assert_not_called()

    def test_ping_and_transport_safety(self):
        self.session.get.return_value = response({'meta': {'id': 'fake-customer', 'statusEmoji': 'ok'}})
        self.assertIs(self.client_up.ping(), True)
        args, kwargs = self.session.get.call_args
        self.assertEqual(args[0], BASE_URL + '/util/ping')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer ' + FAKE_TOKEN)
        self.assertEqual(kwargs['timeout'], (5, 20))
        self.assertIs(kwargs['allow_redirects'], False)
        self.assertIsNot(kwargs['verify'], False)

    def test_http_failures_are_sanitized(self):
        for status, exception in [(401, AuthenticationError), (403, AuthenticationError),
                                  (429, RateLimitError), (500, ResponseError), (302, ResponseError)]:
            with self.subTest(status=status):
                self.session.get.return_value = response({'private': FAKE_TOKEN}, status)
                with self.assertRaises(exception) as caught:
                    self.client_up.ping()
                self.assertNotIn(FAKE_TOKEN, str(caught.exception))
                self.session.get.return_value.json.assert_not_called()

    def test_network_and_timeout_errors(self):
        for error in [requests.ConnectionError(FAKE_TOKEN), requests.Timeout(FAKE_TOKEN)]:
            self.session.get.side_effect = error
            with self.assertRaises(NetworkError) as caught:
                self.client_up.ping()
            self.assertNotIn(FAKE_TOKEN, str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)

    def test_malformed_json_and_ping_structures(self):
        result = response()
        result.json.side_effect = requests.exceptions.JSONDecodeError('private', FAKE_TOKEN, 0)
        self.session.get.return_value = result
        with self.assertRaises(ResponseError):
            self.client_up.ping()
        for payload in [[], {}, {'meta': {}}, {'meta': {'id': 123, 'statusEmoji': 'ok'}}]:
            self.session.get.return_value = response(payload)
            with self.assertRaises(ResponseError):
                self.client_up.ping()

    def test_accounts_multiple_pages_and_no_persistence(self):
        next_url = BASE_URL + '/accounts?page[after]=fake-cursor'
        self.session.get.side_effect = [
            response({'data': [account()], 'links': {'next': next_url}}),
            response({'data': [account('fake-saver', 'SAVER')], 'links': {'next': None}})]
        result = self.client_up.accounts()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].model_fields(), {'external_id': 'fake-account', 'name': 'Fake household account', 'currency': 'AUD'})
        self.assertEqual(result[1].account_type, 'SAVER')
        self.assertNotIn('Fake household', repr(result))
        self.assertFalse(BankAccount.objects.exists())
        self.assertEqual(self.session.get.call_args_list[1].args[0], next_url)

    def test_unsafe_pagination_not_requested(self):
        for url in ['https://evil.example/api/v1/accounts', 'http://api.up.com.au/api/v1/accounts',
                    'https://api.up.com.au:444/api/v1/accounts', 'https://user@api.up.com.au/api/v1/accounts',
                    'https://api.up.com.au/api/v1/transactions', '//evil.example/accounts',
                    'https://api.up.com.au/api/v1/accounts#fragment', 42, {}]:
            with self.subTest(url=url):
                self.session.get.reset_mock()
                self.session.get.return_value = response({'data': [], 'links': {'next': url}})
                with self.assertRaises(ResponseError):
                    self.client_up.accounts()
                self.assertEqual(self.session.get.call_count, 1)

    def test_bad_accounts_and_pagination_loop(self):
        for payload in [{}, {'data': {}, 'links': {'next': None}},
                        {'data': [{}], 'links': {'next': None}},
                        {'data': [], 'links': {'next': BASE_URL + '/accounts'}}]:
            self.session.get.return_value = response(payload)
            with self.assertRaises(ResponseError):
                self.client_up.accounts()

    def test_pages_health_and_status_make_no_bank_requests(self):
        for path in ['/', '/ledger/', '/rules/', '/settings/', '/health/']:
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200)
            self.assertNotIn(FAKE_TOKEN, result.content.decode())
        out = io.StringIO()
        call_command('check_up', stdout=out)
        self.assertIn('up_connection: not checked', out.getvalue())
        self.session.get.assert_not_called()

    def test_live_command_only_outputs_safe_summary(self):
        self.session.get.side_effect = [response({'meta': {'id': 'fake-customer', 'statusEmoji': 'ok'}}),
                                       response({'data': [account()], 'links': {'next': None}})]
        out = io.StringIO()
        with patch('logging.Logger._log') as log:
            call_command('check_up', live=True, stdout=out)
        output = out.getvalue()
        self.assertIn('up_connection: successful', output)
        self.assertIn('account_count: 1', output)
        for private in [FAKE_TOKEN, 'fake-customer', 'fake-account', 'Fake household account']:
            self.assertNotIn(private, output)
            self.assertNotIn(private, repr(log.call_args_list))
        self.assertFalse(BankAccount.objects.exists())

    def test_command_error_does_not_leak_network_details(self):
        from django.core.management.base import CommandError
        self.session.get.side_effect = requests.ConnectionError(FAKE_TOKEN + ' private-response')
        out = io.StringIO()
        with patch('logging.Logger._log') as log:
            with self.assertRaises(CommandError) as caught:
                call_command('check_up', live=True, stdout=out)
        self.assertNotIn(FAKE_TOKEN, str(caught.exception))
        self.assertNotIn('private-response', str(caught.exception))
        self.assertNotIn(FAKE_TOKEN, out.getvalue())
        self.assertNotIn(FAKE_TOKEN, repr(log.call_args_list))
        self.assertTrue(caught.exception.__suppress_context__)
