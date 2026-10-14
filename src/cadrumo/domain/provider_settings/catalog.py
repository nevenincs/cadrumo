"""The provider catalog cadrumo-agent reports, and its strict parser.

Each entry is one lane the agent can run: one way into a provider identity,
over its API or through its CLI. Cadrumo keeps no list of providers or lanes.
Which exist, how each authenticates, its default gateway URL and the id the
agent keys its credential by are the agent's own declarations, parsed here from
the document the agent serves at run time. Every Cadrumo name for a lane is
constructed from the ids the agent reports.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Final, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, StringConstraints, ValidationError, field_validator, model_validator

from ...core.errors.hierarchy import CoreValidationError, pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

BASE_URL_MAX_LENGTH: Final[int] = 2048
MAX_CATALOG_LANES: Final[int] = 64
_BASE_URL_FORBIDDEN: Final[frozenset[str]] = frozenset("*?[%$")

_PROVIDER_ID_PATTERN: Final[str] = r"^[a-z][a-z0-9_]{0,39}$"
_PROVIDER_ID: Final[re.Pattern[str]] = re.compile(_PROVIDER_ID_PATTERN)

ProviderId = Annotated[str, StringConstraints(pattern=_PROVIDER_ID_PATTERN)]
"""A lane or provider identity id: a lowercase storage-safe slug."""

CliProgram = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
"""The executable name a cli lane runs."""

DEVELOPMENT_KEY_PREFIX: Final = "CADRUMO_LLM_"
DEVELOPMENT_KEY_SUFFIX: Final = "_API_KEY"


def development_key_variable(provider: str) -> str:
    """Return the environment value a development checkout reads for ``provider``.

    The name is constructed from the provider id the agent reports and never
    enumerated: no setting field, declaration or table names a provider.
    """
    return f"{DEVELOPMENT_KEY_PREFIX}{provider.upper()}{DEVELOPMENT_KEY_SUFFIX}"


class ProviderAuthKind(StrEnum):
    """How one lane authenticates."""

    API_KEY = "api_key"
    API_KEY_WITH_BASE_URL = "api_key_with_base_url"
    PROVIDER_SIGN_IN_ONLY = "provider_sign_in_only"

    @property
    def accepts_direct_credential(self) -> bool:
        """Return whether a profile may store a credential for this kind."""
        return self is not ProviderAuthKind.PROVIDER_SIGN_IN_ONLY

    @property
    def accepts_provider_sign_in(self) -> bool:
        """Return whether the provider's own CLI sign-in serves the lane."""
        return self is ProviderAuthKind.PROVIDER_SIGN_IN_ONLY

    @property
    def accepts_base_url(self) -> bool:
        """Return whether a stored credential may carry a gateway base URL."""
        return self is ProviderAuthKind.API_KEY_WITH_BASE_URL


class ProviderConsumer(StrEnum):
    """A capability that consumes lane credentials.

    Only the agent's assistant lanes read provider settings; Cadrumo's own
    extraction keeps its separate configuration.
    """

    ASSISTANT = "assistant"


class ProviderTransport(StrEnum):
    """How a lane reaches its provider identity."""

    API = "api"
    CLI = "cli"


def validate_https_base_url(value: str) -> str:
    """Return ``value`` when it is an acceptable provider gateway URL.

    Only an absolute ``https`` URL with a host is accepted. Embedded
    credentials, a query and a fragment are refused, because a base URL is
    stored as non-secret data and joined with request paths by the consumer.
    The desktop host applies the same rule before a value reaches a child
    process: printable ASCII only, no leading ``-``, and none of the shell or
    pattern characters ``* ? [ % $``.

    Raises:
        ValueError: When the URL is not an acceptable gateway URL.
    """
    if not value or len(value) > BASE_URL_MAX_LENGTH or value != value.strip():
        raise ValueError("base URL must be a non-empty trimmed string within the length bound")
    if any(character.isspace() or not 0x20 < ord(character) < 0x7F for character in value):
        raise ValueError("base URL must be printable ASCII without whitespace")
    if value.startswith("-") or any(character in _BASE_URL_FORBIDDEN for character in value):
        raise ValueError("base URL must not start with '-' or carry a shell or pattern character")
    parts = urlsplit(value)
    if parts.scheme != "https":
        raise ValueError("base URL must use https")
    if not (parts.hostname is not None and parts.hostname):
        raise ValueError("base URL must name a host")
    if parts.username is not None or parts.password is not None:
        raise ValueError("base URL must not embed credentials")
    if parts.query or parts.fragment:
        raise ValueError("base URL must not carry a query or fragment")
    return value


class ProviderCatalogEntry(BaseModel):
    """One lane the agent reports and a profile can manage a credential for."""

    model_config = _STRICT_FROZEN

    id: ProviderId
    """The agent's lane id; commands address a lane by it and its record is keyed by it."""
    provider: ProviderId
    """The agent provider identity this lane reaches."""
    transport: ProviderTransport
    display_name: str = Field(min_length=1, max_length=64)
    """The identity's product name, the same on every lane of that identity."""
    auth_kind: ProviderAuthKind
    default_base_url: str | None
    agent_credential_id: ProviderId | None
    """The id the agent's hosting frame keys this lane's credential by; absent when the lane takes none."""
    cli_programs: tuple[CliProgram, ...]
    """The executables a cli lane runs; empty for an api lane."""

    @field_validator("default_base_url")
    @classmethod
    @pydantic_validation_boundary
    def _default_base_url_is_https(cls, value: str | None) -> str | None:
        return None if value is None else validate_https_base_url(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _entry_is_coherent(self) -> Self:
        if self.id != f"{self.provider}_{self.transport.value}":
            raise ValueError("a lane id is its provider and transport joined by an underscore")
        if (self.transport is ProviderTransport.CLI) != bool(self.cli_programs):
            raise ValueError("a cli lane names its programs and an api lane names none")
        if len(set(self.cli_programs)) != len(self.cli_programs):
            raise ValueError("cli programs must not repeat")
        if (self.agent_credential_id is not None) != self.auth_kind.accepts_direct_credential:
            raise ValueError("a lane declares a credential id exactly when it takes a credential")
        return self

    @property
    def consumers(self) -> tuple[ProviderConsumer, ...]:
        """Return the consumers of this lane: every reported lane serves the agent's assistant."""
        return (ProviderConsumer.ASSISTANT,)

    @property
    def development_variable(self) -> str:
        """Return the environment value a development checkout reads for this lane's provider key."""
        return development_key_variable(self.provider)

    def serves(self, consumer: ProviderConsumer) -> bool:
        """Return whether ``consumer`` may use this lane's credential."""
        return consumer in self.consumers


class ProviderCatalog(BaseModel):
    """The validated lane catalog the agent reported."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    providers: tuple[ProviderCatalogEntry, ...] = Field(min_length=1, max_length=MAX_CATALOG_LANES)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _lanes_are_coherent(self) -> Self:
        ids = [entry.id for entry in self.providers]
        if len(ids) != len(set(ids)):
            raise ValueError("lane ids must be unique")
        credential_ids = [
            entry.agent_credential_id for entry in self.providers if entry.agent_credential_id is not None
        ]
        if len(credential_ids) != len(set(credential_ids)):
            raise ValueError("agent credential ids must be unique")
        names: dict[str, str] = {}
        for entry in self.providers:
            if names.setdefault(entry.provider, entry.display_name) != entry.display_name:
                raise ValueError("every lane of one identity carries the same display name")
        return self

    @property
    def provider_ids(self) -> tuple[str, ...]:
        """Return every lane id in catalog order."""
        return tuple(entry.id for entry in self.providers)

    @property
    def credential_lane_ids(self) -> tuple[str, ...]:
        """Return the lane ids whose credential the agent's hosting frame carries, in catalog order."""
        return tuple(entry.id for entry in self.providers if entry.agent_credential_id is not None)

    def entry(self, provider_id: str) -> ProviderCatalogEntry | None:
        """Return the lane ``provider_id`` names, or ``None`` when the agent did not report it."""
        if not _PROVIDER_ID.fullmatch(provider_id):
            return None
        return next((entry for entry in self.providers if entry.id == provider_id), None)


def parse_provider_catalog(text: str) -> ProviderCatalog:
    """Parse and strictly validate the document the agent serves.

    Unknown fields, an unknown schema version, duplicate lanes and malformed
    values are refused.

    Raises:
        CoreValidationError: When the document is not valid JSON or does not
            satisfy the catalog contract.
    """
    try:
        return ProviderCatalog.model_validate_json(text)
    except ValidationError as exc:
        raise CoreValidationError(
            translated_message=CoreValidationError.code.message_key,
            context={
                "section": "provider_settings.catalog",
                "valid": False,
                "validation_error_type": type(exc).__name__,
            },
        ) from exc


__all__ = [
    "BASE_URL_MAX_LENGTH",
    "DEVELOPMENT_KEY_PREFIX",
    "DEVELOPMENT_KEY_SUFFIX",
    "MAX_CATALOG_LANES",
    "CliProgram",
    "ProviderAuthKind",
    "ProviderCatalog",
    "ProviderCatalogEntry",
    "ProviderConsumer",
    "ProviderId",
    "ProviderTransport",
    "development_key_variable",
    "parse_provider_catalog",
    "validate_https_base_url",
]
