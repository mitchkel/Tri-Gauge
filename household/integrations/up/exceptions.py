class UPError(Exception):
    """Errors contain fixed public-safe messages, never upstream details."""


class ConfigurationError(UPError):
    pass


class AuthenticationError(UPError):
    pass


class NetworkError(UPError):
    pass


class RateLimitError(UPError):
    pass


class ResponseError(UPError):
    pass
