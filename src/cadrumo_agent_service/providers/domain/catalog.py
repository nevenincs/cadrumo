"""The provider catalog cadrumo-agent reports, and its strict parser.

Each entry is one lane the agent can run: one way into a provider identity,
over its API or through its CLI. Cadrumo keeps no list of providers or lanes.
Which exist, how each authenticates, its default gateway URL, whether it sends
material off this computer, the id the agent keys its credential by, the models
it declares with their stated facts, its recommended models and what a
background run on it takes are the agent's own declarations, parsed here from
the document the agent serves at run time. Every Cadrumo name for a lane is
constructed from the ids the agent reports.
"""

from __future__ import annotations

import re
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Final, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, JsonValue, PositiveInt, StringConstraints, ValidationError, model_validator

from cadrumo.core.errors.hierarchy import CoreValidationError, pydantic_validation_boundary
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

BASE_URL_MAX_LENGTH: Final[int] = 2048
MAX_CATALOG_LANES: Final[int] = 64
_BASE_URL_FORBIDDEN: Final[frozenset[str]] = frozenset("*?[%$")
_LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})
_MAX_PORT: Final[int] = 65535
RECOMMENDED_KEY_MAX_LENGTH: Final[int] = 64
RECOMMENDED_VALUE_MAX_LENGTH: Final[int] = 256
MODEL_ID_MAX_LENGTH: Final[int] = 256

_PROVIDER_ID_PATTERN: Final[str] = r"^[a-z][a-z0-9_]{0,39}$"
_PROVIDER_ID: Final[re.Pattern[str]] = re.compile(_PROVIDER_ID_PATTERN)

ProviderId = Annotated[str, StringConstraints(pattern=_PROVIDER_ID_PATTERN)]
"""A lane or provider identity id: a lowercase storage-safe slug."""

CliProgram = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
"""The executable name a cli lane runs."""

LicenceDigest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
"""The digest of a licence text the agent ships: ``sha256:`` and 64 lowercase hex digits."""


class ProviderAuthKind(StrEnum):
    """How one lane authenticates."""

    API_KEY = "api_key"
    API_KEY_WITH_BASE_URL = "api_key_with_base_url"
    PROVIDER_SIGN_IN_ONLY = "provider_sign_in_only"
    NONE = "none"
    """A keyless lane: it takes no stored credential and no provider sign-in, and reaches a server on this computer."""

    @property
    def accepts_direct_credential(self) -> bool:
        """Return whether a profile may store a credential for this kind."""
        return self in {ProviderAuthKind.API_KEY, ProviderAuthKind.API_KEY_WITH_BASE_URL}

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


def validate_loopback_http_base_url(value: str) -> str:
    """Return ``value`` when it is an ``http`` origin on this computer.

    A keyless lane reaches only a local server, so its endpoint is plain
    ``http`` to the host ``127.0.0.1``, ``localhost`` or ``[::1]``, with any
    port and no path beyond ``/``. Embedded credentials, a query and a fragment
    are refused. The message never repeats the value.

    Raises:
        ValueError: When the URL is not a loopback ``http`` origin.
    """
    if not value or len(value) > BASE_URL_MAX_LENGTH or value != value.strip():
        raise ValueError("base URL must be a non-empty trimmed string within the length bound")
    if any(character.isspace() or not 0x20 < ord(character) < 0x7F for character in value):
        raise ValueError("base URL must be printable ASCII without whitespace")
    # The brackets of ``[::1]`` are the one pattern character a loopback origin may carry.
    if any(mark in value for mark in "?#@\\") or any(character in _BASE_URL_FORBIDDEN - {"["} for character in value):
        raise ValueError("base URL must not carry credentials, a query, a fragment or a pattern character")
    parts = urlsplit(value)
    if parts.scheme != "http" or not value.startswith("http://"):
        raise ValueError("a keyless lane's base URL must use http")
    if parts.path not in {"", "/"}:
        raise ValueError("a keyless lane's base URL must carry no path")
    if parts.hostname not in _LOOPBACK_HOSTS:
        raise ValueError("a keyless lane's base URL must name 127.0.0.1, localhost or [::1]")
    try:
        port = parts.port
    except ValueError:
        raise ValueError("base URL port must be a number") from None
    if parts.netloc.endswith(":") or (port is not None and not 0 < port <= _MAX_PORT):
        raise ValueError("base URL port must be a number from 1 to 65535")
    return value


class ModelLicence(BaseModel):
    """The licence the agent states for one model, shown to the person and never judged by Cadrumo."""

    model_config = _STRICT_FROZEN

    spdx: str | None = Field(min_length=1, max_length=128)
    """The SPDX identifier, when the licence has one."""
    name: str = Field(min_length=1, max_length=256)
    digest: LicenceDigest
    """The digest of the licence text the agent serves for this model."""


class ProviderCatalogModel(BaseModel):
    """One model a lane declares, with the facts the agent states for it.

    A fact the agent does not state is ``None``; nothing is inferred in its place.
    """

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1, max_length=MODEL_ID_MAX_LENGTH)
    """The model value a run names on its lane."""
    display_name: str = Field(min_length=1)
    effort: dict[str, JsonValue]
    """The agent's effort control for the model, carried as declared."""
    vision: bool | None
    """Whether the model reads images; ``None`` when the agent does not state it."""
    size_bytes: PositiveInt | None
    """The model's download size in bytes, when the agent states it."""
    context_length: PositiveInt | None
    """The model's context window in tokens, when the agent states it."""
    licence: ModelLicence | None


class BackgroundInput(StrEnum):
    """An input family a background run on a lane may carry, in the agent's declared order."""

    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"


class BackgroundOption(StrEnum):
    """A run option a background request on a lane may set, in the agent's declared order."""

    TEMPERATURE = "temperature"
    CONTEXT_TOKENS = "context_tokens"
    RESPONSE_SCHEMA = "response_schema"


class LaneBackground(BaseModel):
    """What a background run on one lane takes, as the agent declares it."""

    model_config = _STRICT_FROZEN

    runnable: bool
    """Whether the lane runs background requests at all."""
    inputs: tuple[BackgroundInput, ...]
    options: tuple[BackgroundOption, ...]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _declaration_is_coherent(self) -> Self:
        if not _in_declared_order(self.inputs, tuple(BackgroundInput)):
            raise ValueError("background inputs are unique and in declared order")
        if not _in_declared_order(self.options, tuple(BackgroundOption)):
            raise ValueError("background options are unique and in declared order")
        if not self.runnable and self.inputs:
            raise ValueError("a lane that runs no background request takes no input")
        return self


def _in_declared_order[T](values: tuple[T, ...], vocabulary: tuple[T, ...]) -> bool:
    """Return whether ``values`` is a repetition-free subsequence of ``vocabulary``."""
    positions = [vocabulary.index(value) for value in values]
    return all(earlier < later for earlier, later in pairwise(positions))


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
    description: str
    auth_kind: ProviderAuthKind
    default_base_url: str | None
    reads_off_host: bool
    """Whether a run on this lane sends material off this computer; the agent's typed declaration, never inferred."""
    agent_credential_id: ProviderId | None
    """The id the agent's hosting frame keys this lane's credential by; absent when the lane takes none."""
    cli_programs: tuple[CliProgram, ...]
    """The executables a cli lane runs; empty for an api lane."""
    icon: dict[str, JsonValue] | None = None
    platform: dict[str, JsonValue] = Field(default_factory=dict)
    default_model: str | None = None
    models: tuple[ProviderCatalogModel, ...] = ()
    unread: tuple[dict[str, JsonValue], ...] = ()
    recommended: dict[
        Annotated[str, StringConstraints(min_length=1, max_length=RECOMMENDED_KEY_MAX_LENGTH)],
        Annotated[str, StringConstraints(min_length=1, max_length=RECOMMENDED_VALUE_MAX_LENGTH)],
    ]
    """The agent's recommended model id per capability; empty when it states none, never applied by Cadrumo."""
    background: LaneBackground
    """What a background run on this lane takes."""

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
        if self.auth_kind is ProviderAuthKind.NONE:
            if self.default_base_url is None:
                raise ValueError("a keyless lane declares its loopback base URL")
            validate_loopback_http_base_url(self.default_base_url)
        elif self.default_base_url is not None:
            validate_https_base_url(self.default_base_url)
        model_ids = [model.id for model in self.models]
        if len(model_ids) != len(set(model_ids)):
            raise ValueError("a lane's model ids must be unique")
        if not set(self.recommended.values()) <= set(model_ids):
            raise ValueError("a recommended entry names one of its lane's models")
        return self

    def model(self, model_id: str) -> ProviderCatalogModel | None:
        """Return the model this lane declares under ``model_id``, or ``None`` when it declares none."""
        return next((model for model in self.models if model.id == model_id), None)

    @property
    def consumers(self) -> tuple[ProviderConsumer, ...]:
        """Return the consumers of this lane: every reported lane serves the agent's assistant."""
        return (ProviderConsumer.ASSISTANT,)

    def serves(self, consumer: ProviderConsumer) -> bool:
        """Return whether ``consumer`` may use this lane's credential."""
        return consumer in self.consumers


class ProviderCatalog(BaseModel):
    """The validated lane catalog the agent reported."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[5]
    providers: tuple[ProviderCatalogEntry, ...] = Field(min_length=1, max_length=MAX_CATALOG_LANES)
    icon_attribution: dict[str, JsonValue]

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
    "MAX_CATALOG_LANES",
    "MODEL_ID_MAX_LENGTH",
    "RECOMMENDED_KEY_MAX_LENGTH",
    "RECOMMENDED_VALUE_MAX_LENGTH",
    "BackgroundInput",
    "BackgroundOption",
    "CliProgram",
    "LaneBackground",
    "LicenceDigest",
    "ModelLicence",
    "ProviderAuthKind",
    "ProviderCatalog",
    "ProviderCatalogEntry",
    "ProviderCatalogModel",
    "ProviderConsumer",
    "ProviderId",
    "ProviderTransport",
    "parse_provider_catalog",
    "validate_https_base_url",
    "validate_loopback_http_base_url",
]
