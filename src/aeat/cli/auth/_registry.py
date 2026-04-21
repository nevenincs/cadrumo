"""Provider registry for the ``aeat auth`` CLI.

The registry is the single source of truth for provider ordering,
default resolution, and user-facing rendering. Each entry owns its
label and whether a concrete ``AuthProvider`` has shipped. For
implemented kinds the CLI delegates to :func:`aeat.auth.select_provider`
to build the real provider. Subcommands read from this registry; no
command constructs providers directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ...auth import (
    AuthProvider,
    AuthProviderDescription,
    AuthProviderKind,
    select_provider,
)
from ...errors import AeatError

if TYPE_CHECKING:
    from ...config import Settings


class NoConfiguredProviderError(AeatError):
    """No auth provider is configured and no default was specified."""


class UnknownProviderError(AeatError):
    """The requested provider kind is not registered."""


class ProviderNotImplementedError(AeatError):
    """The provider kind is known but no implementation has shipped yet."""


class ProviderRegistryEntry(BaseModel):
    """One row of the auth-provider registry."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: AuthProviderKind
    label: str = Field(min_length=1)
    implemented: bool


REGISTRY: Sequence[ProviderRegistryEntry] = (
    ProviderRegistryEntry(
        kind=AuthProviderKind.CERTIFICATE,
        label="Certificate (FNMT)",
        implemented=True,
    ),
    ProviderRegistryEntry(
        kind=AuthProviderKind.CLAVE_MOVIL,
        label="Cl@ve Móvil",
        implemented=True,
    ),
    ProviderRegistryEntry(
        kind=AuthProviderKind.CLAVE_PERMANENTE,
        label="Cl@ve Permanente",
        implemented=False,
    ),
    ProviderRegistryEntry(
        kind=AuthProviderKind.CLAVE_PIN,
        label="Cl@ve PIN",
        implemented=False,
    ),
)


INTERACTIVE_KINDS: frozenset[AuthProviderKind] = frozenset(
    {
        AuthProviderKind.CLAVE_MOVIL,
        AuthProviderKind.CLAVE_PIN,
    }
)


def iter_entries() -> Sequence[ProviderRegistryEntry]:
    """Return the canonical provider order."""
    return REGISTRY


def get_entry(kind: AuthProviderKind) -> ProviderRegistryEntry:
    """Look up a registry entry by kind."""
    for entry in REGISTRY:
        if entry.kind == kind:
            return entry
    raise UnknownProviderError(f"unknown auth provider kind: {kind}")


def build_provider(kind: AuthProviderKind, settings: Settings) -> AuthProvider:
    """Instantiate the concrete ``AuthProvider`` for a kind.

    Passes the shared production :func:`default_browser_session_factory`
    so the returned provider can drive Playwright without the caller
    having to wire one itself. Raises :class:`ProviderNotImplementedError`
    for registry entries that have a label but no shipped
    implementation — the CLI layer catches that and maps it to an
    actionable exit-code-2 message.
    """
    entry = get_entry(kind)
    if not entry.implemented:
        raise ProviderNotImplementedError(f"provider {kind.value!r} is known but not yet implemented; see EPIC #279")
    from ...browser import default_browser_session_factory

    try:
        return select_provider(
            kind,
            settings=settings,
            browser_session_factory=default_browser_session_factory,
        )
    except NotImplementedError as exc:
        raise ProviderNotImplementedError(str(exc)) from exc


def describe(kind: AuthProviderKind, settings: Settings) -> AuthProviderDescription:
    """Produce an ``AuthProviderDescription`` for a registry kind.

    Implemented providers delegate to the provider's own ``describe()``
    (which fails soft for missing configuration). Not-yet-shipped
    kinds return a fixed "not yet implemented" description so the CLI
    can still list them.
    """
    entry = get_entry(kind)
    if entry.implemented:
        provider = select_provider(kind, settings=settings)
        return provider.describe()
    return AuthProviderDescription(
        kind=entry.kind,
        label=entry.label,
        configured=False,
        available=False,
        health_summary="not yet implemented",
    )


def default_kind(settings: Settings) -> AuthProviderKind:
    """Pick the default provider kind for login/status when ``--provider`` is absent.

    Resolution order:
    1. ``settings.aeat_auth_provider`` (env var ``AEAT_AUTH_PROVIDER``).
    2. The first registry kind whose ``describe()`` is ``configured=True``.
    3. Raise :class:`NoConfiguredProviderError`.
    """
    if settings.aeat_auth_provider is not None:
        return settings.aeat_auth_provider
    for entry in REGISTRY:
        description = describe(entry.kind, settings)
        if description.configured:
            return entry.kind
    raise NoConfiguredProviderError(
        "no AEAT auth provider is configured; set AEAT_AUTH_PROVIDER or pass --provider, "
        "then follow `aeat setup` to configure credentials for the chosen provider"
    )
