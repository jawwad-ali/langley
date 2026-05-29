"""Exception hierarchy for langley_risk.

A single base (`LangleyRiskError`) lets callers catch everything from this package,
while specific subclasses let them handle individual failure modes. Provider
failures are modeled precisely because the agent's *abstain* behavior depends on
distinguishing "token genuinely not found" from "data source is down".
"""

from __future__ import annotations


class LangleyRiskError(Exception):
    """Base class for all errors raised by langley_risk."""


class ConfigError(LangleyRiskError):
    """Raised when configuration/settings are missing or invalid."""


class ProviderError(LangleyRiskError):
    """Base class for data-provider failures."""


class TokenNotFoundError(ProviderError):
    """The requested token/pair does not exist at the provider."""

    def __init__(self, query: str) -> None:
        self.query = query
        super().__init__(f"No token or pair found for query: {query!r}")


class ProviderRateLimitedError(ProviderError):
    """The provider rejected the request due to rate limiting (HTTP 429)."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Provider {provider!r} rate-limited the request")


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the configured timeout."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Provider {provider!r} timed out")


class ProviderResponseInvalidError(ProviderError):
    """The provider responded, but the payload could not be parsed as expected."""

    def __init__(self, provider: str, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(f"Invalid response from provider {provider!r}: {detail}")


class AgentError(LangleyRiskError):
    """Raised when the agent run fails or returns output that cannot be used."""
