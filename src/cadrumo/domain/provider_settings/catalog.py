"""The cadrumo-agent lane catalog and its strict loader.

Each entry is one lane: one way into a cadrumo-agent provider identity, over its
API or through its CLI. The lane id is the agent's own execution-lane id;
``provider`` is the identity the lane belongs to, so the Claude API lane and the
Claude CLI lane share ``provider = "claude"``. Which credential each lane takes,
its default gateway URL and the agent settings field that receives the
credential are bundled data (``cadrumo/_data/provider_settings/catalog.toml``)
generated from the agent's own definitions by a development generator, never
hand-edited. This module validates that document once per process.

The catalog lives beside the other shipped runtime data rather than under
``_data/registry/cadrumo``: that tree is a compiler input excluded from every
distribution, so a runtime reader there would work in a checkout and fail in an
installed build.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from functools import cache
from typing import Annotated, Final, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, StringConstraints, ValidationError, field_validator, model_validator

from ...core.config import Settings
from ...core.errors.hierarchy import CoreValidationError, pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.resources.bundled_data import packaged_data
from ...core.toml import TomlDecodeError, parse_toml

PROVIDER_CATALOG_DATA_PARTS: Final[tuple[str, ...]] = ("provider_settings", "catalog.toml")
BASE_URL_MAX_LENGTH: Final[int] = 2048
_BASE_URL_FORBIDDEN: Final[frozenset[str]] = frozenset("*?[%$")

_PROVIDER_ID_PATTERN: Final[str] = r"^[a-z][a-z0-9_]{0,39}$"
_PROVIDER_ID: Final[re.Pattern[str]] = re.compile(_PROVIDER_ID_PATTERN)

ProviderId = Annotated[str, StringConstraints(pattern=_PROVIDER_ID_PATTERN)]
"""A lane or provider identity id: a lowercase storage-safe slug."""

CredentialField = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
"""The name of the cadrumo-agent settings field that receives a credential."""

CliProgram = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
"""The executable name a cli lane runs."""


class ProviderAuthKind(StrEnum):
    """How one lane authenticates."""

    API_KEY = "api_key"
    API_KEY_WITH_BASE_URL = "api_key_with_base_url"
    OAUTH_OR_PROVIDER_SIGN_IN = "oauth_token_or_provider_sign_in"
    PROVIDER_SIGN_IN_ONLY = "provider_sign_in_only"

    @property
    def accepts_direct_credential(self) -> bool:
        """Return whether a profile may store a credential for this kind."""
        return self is not ProviderAuthKind.PROVIDER_SIGN_IN_ONLY

    @property
    def carries_api_key(self) -> bool:
        """Return whether the credential is a plain API key, the only kind cadrumo-agent's hosting frame carries."""
        return self in {ProviderAuthKind.API_KEY, ProviderAuthKind.API_KEY_WITH_BASE_URL}

    @property
    def accepts_provider_sign_in(self) -> bool:
        """Return whether the provider's own CLI sign-in can serve the lane."""
        return self in {ProviderAuthKind.OAUTH_OR_PROVIDER_SIGN_IN, ProviderAuthKind.PROVIDER_SIGN_IN_ONLY}

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
    """One cadrumo-agent lane a profile can manage a credential for."""

    model_config = _STRICT_FROZEN

    id: ProviderId
    """The agent's execution-lane id; commands address a lane by it."""
    provider: ProviderId
    """The agent provider identity this lane reaches."""
    transport: ProviderTransport
    display_name: str = Field(min_length=1, max_length=64)
    """The identity's product name, the same on every lane of that identity."""
    auth_kind: ProviderAuthKind
    consumers: tuple[ProviderConsumer, ...] = Field(min_length=1)
    default_base_url: str | None = None
    credential_field: CredentialField | None = None
    """The agent settings field that receives this lane's credential; the frame is keyed by it."""
    cli_program: CliProgram | None = None
    """The executable a cli lane runs; absent for an api lane."""
    development_setting: str | None = Field(default=None, min_length=1)
    """The Cadrumo settings field read for an unset record in development storage mode only."""

    @field_validator("default_base_url")
    @classmethod
    @pydantic_validation_boundary
    def _default_base_url_is_https(cls, value: str | None) -> str | None:
        return None if value is None else validate_https_base_url(value)

    @field_validator("development_setting")
    @classmethod
    @pydantic_validation_boundary
    def _development_setting_names_a_secret_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        field = Settings.model_fields.get(value)
        if field is None or field.annotation != (SecretStr | None):
            raise ValueError("development_setting must name a secret Cadrumo settings field")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _entry_is_coherent(self) -> Self:
        if len(set(self.consumers)) != len(self.consumers):
            raise ValueError("consumers must not repeat")
        if self.default_base_url is not None and not self.auth_kind.accepts_base_url:
            raise ValueError("only api_key_with_base_url lanes declare a default base URL")
        if (self.transport is ProviderTransport.CLI) != (self.cli_program is not None):
            raise ValueError("a cli lane names its program and an api lane names none")
        if self.transport is ProviderTransport.API and self.auth_kind is not ProviderAuthKind.API_KEY:
            raise ValueError("an api lane authenticates with a direct API key")
        if self.id != f"{self.provider}_{self.transport.value}":
            raise ValueError("a lane id is its provider and transport joined by an underscore")
        if (self.credential_field is not None) != self.auth_kind.accepts_direct_credential:
            raise ValueError("a lane names a credential field exactly when it takes a credential")
        if self.development_setting is not None and not self.auth_kind.accepts_direct_credential:
            raise ValueError("a provider-sign-in-only lane has no development credential")
        return self

    @property
    def agent_credential_id(self) -> str | None:
        """Return the id cadrumo-agent's hosting frame keys this lane's credential by, or ``None``.

        The agent keys an API key by its provider's own name. A lane that
        authenticates by OAuth token or by the provider's own sign-in has no
        such id: neither ever travels in the frame.
        """
        return self.provider if self.auth_kind.carries_api_key else None

    def serves(self, consumer: ProviderConsumer) -> bool:
        """Return whether ``consumer`` may use this lane's credential."""
        return consumer in self.consumers


class ProviderCatalogSource(BaseModel):
    """Which cadrumo-agent definitions the catalog was generated from."""

    model_config = _STRICT_FROZEN

    agent_version: str = Field(min_length=1, max_length=64)
    agent_source_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ProviderCatalog(BaseModel):
    """The validated lane catalog."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    source: ProviderCatalogSource
    providers: tuple[ProviderCatalogEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _lanes_are_coherent(self) -> Self:
        ids = [entry.id for entry in self.providers]
        if len(ids) != len(set(ids)):
            raise ValueError("lane ids must be unique")
        fields = [entry.credential_field for entry in self.providers if entry.credential_field is not None]
        if len(fields) != len(set(fields)):
            raise ValueError("credential fields must be unique")
        names: dict[str, str] = {}
        for entry in self.providers:
            if names.setdefault(entry.provider, entry.display_name) != entry.display_name:
                raise ValueError("every lane of one identity carries the same display name")
        return self

    @property
    def provider_ids(self) -> tuple[str, ...]:
        """Return every lane id in catalog order."""
        return tuple(entry.id for entry in self.providers)

    def entry(self, provider_id: str) -> ProviderCatalogEntry | None:
        """Return the lane ``provider_id`` names, or ``None`` when it is not catalogued."""
        if not _PROVIDER_ID.fullmatch(provider_id):
            return None
        return next((entry for entry in self.providers if entry.id == provider_id), None)


def parse_provider_catalog(text: str) -> ProviderCatalog:
    """Parse and strictly validate a lane catalog document.

    Raises:
        CoreValidationError: When the document is not valid TOML or does not
            satisfy the catalog contract.
    """
    try:
        document = parse_toml(text)
        # Strict models take enum and tuple values from JSON input only.
        return ProviderCatalog.model_validate_json(json.dumps(document))
    except (TomlDecodeError, ValidationError) as exc:
        raise CoreValidationError(
            translated_message=CoreValidationError.code.message_key,
            context={
                "section": "provider_settings.catalog",
                "valid": False,
                "validation_error_type": type(exc).__name__,
            },
        ) from exc


@cache
def load_provider_catalog() -> ProviderCatalog:
    """Return the bundled lane catalog, validated once per process."""
    return parse_provider_catalog(packaged_data(*PROVIDER_CATALOG_DATA_PARTS).read_text(encoding="utf-8"))


__all__ = [
    "BASE_URL_MAX_LENGTH",
    "PROVIDER_CATALOG_DATA_PARTS",
    "CliProgram",
    "CredentialField",
    "ProviderAuthKind",
    "ProviderCatalog",
    "ProviderCatalogEntry",
    "ProviderCatalogSource",
    "ProviderConsumer",
    "ProviderId",
    "ProviderTransport",
    "load_provider_catalog",
    "parse_provider_catalog",
    "validate_https_base_url",
]
