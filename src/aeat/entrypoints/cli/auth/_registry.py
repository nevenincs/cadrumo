"""Provider registry for the ``aeat auth`` CLI.

The registry is the single source of truth for provider ordering,
default resolution, and user-facing rendering. Only providers with a
concrete ``AuthProvider`` implementation are listed here; unsupported
kinds can still exist in lower-level contracts for compatibility, but
the CLI must not advertise them as selectable auth paths.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ....application.auth import (
    AuthProvider,
    AuthProviderDescription,
    AuthProviderKind,
    select_provider,
)
from ....core.errors import AeatError

if TYPE_CHECKING:
    from ....core.config import Settings


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
)


INTERACTIVE_KINDS: frozenset[AuthProviderKind] = frozenset(
    {
        AuthProviderKind.CLAVE_MOVIL,
    }
)


def iter_entries() -> Sequence[ProviderRegistryEntry]:
    """Return the canonical provider order."""
    return REGISTRY


def iter_kinds() -> tuple[AuthProviderKind, ...]:
    """Return provider kinds accepted by the user-facing CLI."""

    return tuple(entry.kind for entry in REGISTRY)


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
    if a registry entry and the application-layer provider factory ever
    drift apart; the CLI layer catches that and maps it to an
    actionable exit-code-2 message.
    """
    kind = get_entry(kind).kind
    from ....adapters.outbound.aeat.browser import default_browser_session_factory

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

    Providers delegate to their own ``describe()`` (which fails soft
    for missing configuration). The browser-session factory is passed
    through even for describe-only calls so providers that grow
    optional I/O in their describe() do not silently see ``None`` and
    break.
    """
    entry = get_entry(kind)
    from ....adapters.outbound.aeat.browser import default_browser_session_factory

    provider = select_provider(
        entry.kind,
        settings=settings,
        browser_session_factory=default_browser_session_factory,
    )
    return provider.describe()


def default_kind(settings: Settings) -> AuthProviderKind:
    """Pick the default provider kind for login/status when ``--provider`` is absent.

    Resolution order:
    1. ``settings.aeat_auth_provider`` (env var ``AEAT_AUTH_PROVIDER``).
    2. The first registry kind whose ``describe()`` is ``configured=True``.
    3. Raise :class:`NoConfiguredProviderError`.
    """
    if settings.aeat_auth_provider is not None:
        configured = AuthProviderKind(settings.aeat_auth_provider.value)
        get_entry(configured)
        return configured
    for entry in REGISTRY:
        description = describe(entry.kind, settings)
        if description.configured:
            return entry.kind
    raise NoConfiguredProviderError(
        "No AEAT auth provider is configured yet. Run `aeat auth configure` "
        "to set up Cl@ve Móvil, or pass `--provider certificate` once your "
        "FNMT certificate is installed."
    )
