"""The declarative model-provider catalog and its strict loader.

Which providers a profile can hold a credential for, the kind of credential
each takes, its default gateway URL and the Cadrumo consumers allowed to use it
are bundled data (``cadrumo/_data/provider_settings/catalog.toml``), not code
branches. This module validates that document once per process and answers
lookups by provider id.

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
PROVIDER_CATALOG_SCHEMA_VERSION: Final[int] = 1
BASE_URL_MAX_LENGTH: Final[int] = 2048

_PROVIDER_ID_PATTERN: Final[str] = r"^[a-z][a-z0-9_]{0,31}$"
_PROVIDER_ID: Final[re.Pattern[str]] = re.compile(_PROVIDER_ID_PATTERN)

ProviderId = Annotated[str, StringConstraints(pattern=_PROVIDER_ID_PATTERN)]
"""A catalog provider identifier: a lowercase storage-safe slug."""


class ProviderAuthKind(StrEnum):
    """How one provider authenticates."""

    API_KEY = "api_key"
    API_KEY_WITH_BASE_URL = "api_key_with_base_url"
    OAUTH_OR_PROVIDER_SIGN_IN = "oauth_token_or_provider_sign_in"
    PROVIDER_SIGN_IN_ONLY = "provider_sign_in_only"

    @property
    def accepts_direct_credential(self) -> bool:
        """Return whether a profile may store a credential for this kind."""
        return self is not ProviderAuthKind.PROVIDER_SIGN_IN_ONLY

    @property
    def accepts_provider_sign_in(self) -> bool:
        """Return whether the provider's own CLI sign-in can serve the assistant."""
        return self in {ProviderAuthKind.OAUTH_OR_PROVIDER_SIGN_IN, ProviderAuthKind.PROVIDER_SIGN_IN_ONLY}

    @property
    def accepts_base_url(self) -> bool:
        """Return whether a stored credential may carry a gateway base URL."""
        return self is ProviderAuthKind.API_KEY_WITH_BASE_URL


class ProviderConsumer(StrEnum):
    """A Cadrumo capability that consumes provider credentials."""

    EXTRACTION = "extraction"
    ASSISTANT = "assistant"


def validate_https_base_url(value: str) -> str:
    """Return ``value`` when it is an acceptable provider gateway URL.

    Only an absolute ``https`` URL with a host is accepted. Embedded
    credentials, a query and a fragment are refused, because a base URL is
    stored as non-secret data and joined with request paths by the consumer.

    Raises:
        ValueError: When the URL is not an acceptable gateway URL.
    """
    if not value or len(value) > BASE_URL_MAX_LENGTH or value != value.strip():
        raise ValueError("base URL must be a non-empty trimmed string within the length bound")
    if any(character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError("base URL must not contain whitespace or control characters")
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
    """One provider the profile can manage a credential for."""

    model_config = _STRICT_FROZEN

    id: ProviderId
    display_name: str = Field(min_length=1, max_length=64)
    auth_kind: ProviderAuthKind
    consumers: tuple[ProviderConsumer, ...] = Field(min_length=1)
    default_base_url: str | None = None
    development_setting: str | None = Field(default=None, min_length=1)
    agent_credential_id: ProviderId | None = None
    """The id cadrumo-agent keys this credential by in the hosted-agent frame, if it receives one."""

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
            raise ValueError("only api_key_with_base_url providers declare a default base URL")
        if ProviderConsumer.EXTRACTION in self.consumers and self.auth_kind is not ProviderAuthKind.API_KEY:
            raise ValueError("extraction consumes direct API keys only")
        if self.development_setting is not None and not self.auth_kind.accepts_direct_credential:
            raise ValueError("a provider-sign-in-only provider has no development credential")
        if self.agent_credential_id is not None and (
            ProviderConsumer.ASSISTANT not in self.consumers or self.auth_kind.accepts_provider_sign_in
        ):
            raise ValueError("only a direct assistant key reaches the hosted agent")
        return self

    def serves(self, consumer: ProviderConsumer) -> bool:
        """Return whether ``consumer`` may use this provider's credential."""
        return consumer in self.consumers


class ProviderCatalog(BaseModel):
    """The validated provider catalog."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    providers: tuple[ProviderCatalogEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _provider_ids_are_unique(self) -> Self:
        ids = [entry.id for entry in self.providers]
        if len(ids) != len(set(ids)):
            raise ValueError("provider ids must be unique")
        agent_ids = [entry.agent_credential_id for entry in self.providers if entry.agent_credential_id is not None]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("agent credential ids must be unique")
        return self

    @property
    def provider_ids(self) -> tuple[str, ...]:
        """Return every provider id in catalog order."""
        return tuple(entry.id for entry in self.providers)

    def entry(self, provider_id: str) -> ProviderCatalogEntry | None:
        """Return the entry for ``provider_id``, or ``None`` when it is not catalogued."""
        if not _PROVIDER_ID.fullmatch(provider_id):
            return None
        return next((entry for entry in self.providers if entry.id == provider_id), None)


def parse_provider_catalog(text: str) -> ProviderCatalog:
    """Parse and strictly validate a provider catalog document.

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
    """Return the bundled provider catalog, validated once per process."""
    return parse_provider_catalog(packaged_data(*PROVIDER_CATALOG_DATA_PARTS).read_text(encoding="utf-8"))


__all__ = [
    "BASE_URL_MAX_LENGTH",
    "PROVIDER_CATALOG_DATA_PARTS",
    "PROVIDER_CATALOG_SCHEMA_VERSION",
    "ProviderAuthKind",
    "ProviderCatalog",
    "ProviderCatalogEntry",
    "ProviderConsumer",
    "ProviderId",
    "load_provider_catalog",
    "parse_provider_catalog",
    "validate_https_base_url",
]
