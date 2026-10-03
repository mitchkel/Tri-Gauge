"""Server-only, read-only UP client. No persistence, logging, retries or redirects."""
import os
from urllib.parse import urlsplit

import requests
from .exceptions import AuthenticationError, ConfigurationError, NetworkError, RateLimitError, ResponseError
from .mapper import map_account

BASE_URL = 'https://api.up.com.au/api/v1'


def token_available():
    token = os.getenv('UP_BANK_TOKEN', '')
    return bool(token.strip()) and token != 'fake-placeholder-do-not-use'


def validate_url(url, path):
    if not isinstance(url, str):
        raise ResponseError('UP returned an unsafe pagination destination.')
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == 'https' and parts.hostname == 'api.up.com.au'
                 and parts.port in (None, 443) and not parts.username
                 and not parts.password and not parts.fragment and parts.path == path
                 and not any(ord(c) <= 32 or ord(c) == 127 for c in url))
        if valid:
            return url
    except (ValueError, TypeError):
        pass
    raise ResponseError('UP returned an unsafe pagination destination.') from None


class UPClient:
    def _get(self, url, path):
        validate_url(url, path)
        if not token_available():
            raise ConfigurationError('UP_BANK_TOKEN is unavailable.')
        # trust_env remains enabled: preserve the runtime proxy and CA configuration.
        verify = os.getenv('REQUESTS_CA_BUNDLE') or os.getenv('SSL_CERT_FILE') or True
        try:
            with requests.Session() as session:
                response = session.get(url, headers={'Authorization': 'Bearer ' + os.environ['UP_BANK_TOKEN'],
                                                     'Accept': 'application/json'},
                                       timeout=(5, 20), allow_redirects=False, verify=verify)
                try:
                    if response.status_code in (401, 403):
                        raise AuthenticationError('UP authentication failed.')
                    if response.status_code == 429:
                        raise RateLimitError('UP rate limit reached; try again later.')
                    if response.status_code != 200:
                        raise ResponseError('UP returned an unexpected HTTP status; redirects are not followed.')
                    payload = response.json()
                finally:
                    response.close()
        except requests.exceptions.Timeout:
            raise NetworkError('UP request timed out.') from None
        except requests.exceptions.JSONDecodeError:
            raise ResponseError('UP returned malformed JSON.') from None
        except requests.exceptions.RequestException:
            raise NetworkError('UP network request failed.') from None
        if not isinstance(payload, dict):
            raise ResponseError('UP returned an unexpected response structure.')
        return payload

    def ping(self):
        payload = self._get(BASE_URL + '/util/ping', '/api/v1/util/ping')
        meta = payload.get('meta')
        if not (isinstance(meta, dict) and isinstance(meta.get('id'), str) and meta['id']
                and isinstance(meta.get('statusEmoji'), str) and meta['statusEmoji']):
            raise ResponseError('UP returned an unexpected ping structure.')
        # Never return the customer identifier.
        return True

    def accounts(self):
        url = BASE_URL + '/accounts'
        seen_pages, seen_ids, accounts = set(), set(), []
        while url is not None:
            validate_url(url, '/api/v1/accounts')
            if url in seen_pages or len(seen_pages) >= 100:
                raise ResponseError('UP account pagination exceeded its safety limit.')
            seen_pages.add(url)
            payload = self._get(url, '/api/v1/accounts')
            data, links = payload.get('data'), payload.get('links')
            if not (isinstance(data, list) and isinstance(links, dict) and 'next' in links):
                raise ResponseError('UP returned an unexpected accounts structure.')
            for resource in data:
                account = map_account(resource)
                if account.external_id in seen_ids:
                    raise ResponseError('UP returned duplicate accounts.')
                seen_ids.add(account.external_id)
                accounts.append(account)
            url = links['next']
            if url is not None:
                validate_url(url, '/api/v1/accounts')
        return accounts
