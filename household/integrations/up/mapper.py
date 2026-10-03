from dataclasses import dataclass, field
from .exceptions import ResponseError

ACCOUNT_TYPES = frozenset({'SAVER', 'TRANSACTIONAL', 'HOME_LOAN'})


@dataclass(frozen=True)
class Account:
    # Suppress private fields from accidental repr/logging. No model writes.
    external_id: str = field(repr=False)
    name: str = field(repr=False)
    currency: str
    account_type: str

    def model_fields(self):
        return {'external_id': self.external_id, 'name': self.name, 'currency': self.currency}


def map_account(resource):
    try:
        attributes = resource['attributes']
        identifier = resource['id']
        name = attributes['displayName']
        currency = attributes['balance']['currencyCode']
        account_type = attributes['accountType']
        valid = (resource['type'] == 'accounts'
                 and isinstance(identifier, str) and 0 < len(identifier) <= 128
                 and isinstance(name, str) and 0 < len(name) <= 200
                 and isinstance(currency, str) and len(currency) == 3
                 and currency.isascii() and currency.isalpha() and currency.isupper()
                 and isinstance(account_type, str) and account_type in ACCOUNT_TYPES)
        if valid:
            return Account(identifier, name, currency, account_type)
    except (KeyError, TypeError):
        pass
    raise ResponseError('UP returned an unexpected account structure.') from None
