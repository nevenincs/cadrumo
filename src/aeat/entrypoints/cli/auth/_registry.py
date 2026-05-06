"""Provider registry for the ``aeat setup auth`` CLI.

The registry is the single source of truth for provider ordering,
default resolution, and user-facing rendering. Only provider kinds that
the CLI can build and describe are listed here. Other lower-level
provider kinds are not selectable CLI paths.

See :func:`build_provider`, :func:`describe`, and :func:`default_kind`
for the three operations the registry mediates.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ....application.auth import (
    AuthProvider,
    AuthProviderDescription,
    AuthProviderKind,
)
from ....core.errors import AeatError

if TYPE_CHECKING:
    from ....core.config import Settings


class NoConfiguredProviderError(AeatError):
    """No auth provider is configured and no default was specified."""


class UnknownProviderError(AeatError):
    """The requested provider kind is not registered."""


class ProviderUnavailableError(AeatError):
    """The provider kind is known but unavailable."""


class ProviderRegistryEntry(BaseModel):
    """One row of the auth-provider registry.

    Attributes:
        kind: The :class:`aeat.application.auth.AuthProviderKind` enum
            member this row covers.
        label: User-facing label rendered by ``aeat setup auth`` listings.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: AuthProviderKind
    label: str = Field(min_length=1)


REGISTRY: Sequence[ProviderRegistryEntry] = (
    ProviderRegistryEntry(
        kind=AuthProviderKind.CERTIFICATE,
        label="Certificate (FNMT)",
    ),
    ProviderRegistryEntry(
        kind=AuthProviderKind.CLAVE_MOVIL,
        label="Cl@ve Móvil",
    ),
)


INTERACTIVE_KINDS: frozenset[AuthProviderKind] = frozenset(
    {
        AuthProviderKind.CLAVE_MOVIL,
    }
)


def iter_entries() -> Sequence[ProviderRegistryEntry]:
    """Return the canonical provider order.

    Returns:
        The registry tuple in display order.
    """
    return REGISTRY


def iter_kinds() -> tuple[AuthProviderKind, ...]:
    """Return provider kinds accepted by the user-facing CLI.

    Returns:
        Tuple of every :class:`aeat.application.auth.AuthProviderKind`
        the CLI exposes, in display order.
    """

    return tuple(entry.kind for entry in REGISTRY)


def get_entry(kind: AuthProviderKind) -> ProviderRegistryEntry:
    """Look up a registry entry by kind.

    Args:
        kind: The provider kind to resolve.

    Returns:
        The matching :class:`ProviderRegistryEntry`.

    Raises:
        UnknownProviderError: When ``kind`` is not registered.
    """
    for entry in REGISTRY:
        if entry.kind == kind:
            return entry
    raise UnknownProviderError(f"unknown auth provider kind: {kind}")


def build_provider(kind: AuthProviderKind, settings: Settings) -> AuthProvider:
    """Instantiate the concrete :class:`aeat.application.auth.AuthProvider` for a kind.

    Passes the shared production
    :func:`aeat.adapters.outbound.aeat.browser.default_browser_session_factory`
    so the returned provider can drive Playwright without the caller
    having to wire one itself.

    Args:
        kind: Which provider to construct.
        settings: Loaded :class:`aeat.core.config.Settings` used by the
            provider for credential discovery.

    Returns:
        A ready-to-use :class:`aeat.application.auth.AuthProvider`.

    Raises:
        UnknownProviderError: When ``kind`` is not registered.
        ProviderUnavailableError: When a registry entry and the
            outbound provider factory drift apart; the CLI
            layer catches this and maps it to an actionable
            exit-code-2 message.
    """
    kind = get_entry(kind).kind
    from ....adapters.outbound.aeat.auth import select_provider
    from ....adapters.outbound.aeat.browser import default_browser_session_factory

    try:
        return select_provider(
            kind,
            settings=settings,
            browser_session_factory=default_browser_session_factory,
        )
    except NotImplementedError as exc:
        raise ProviderUnavailableError(str(exc)) from exc


def describe(kind: AuthProviderKind, settings: Settings) -> AuthProviderDescription:
    """Produce an :class:`aeat.application.auth.AuthProviderDescription` for a registry kind.

    Providers delegate to their own ``describe()`` (which fails soft
    for missing configuration). The browser-session factory is passed
    through even for describe-only calls so providers that grow
    optional I/O in their ``describe()`` do not silently see ``None``
    and break.

    Args:
        kind: Provider kind to inspect.
        settings: Loaded :class:`aeat.core.config.Settings`.

    Returns:
        The provider's self-description.
    """
    entry = get_entry(kind)
    from ....adapters.outbound.aeat.auth import select_provider
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

    - ``settings.aeat_auth_provider`` (env var ``AEAT_AUTH_PROVIDER``).
    - The first registry kind whose ``describe()`` reports
      ``configured=True``.
    - Otherwise raise :exc:`NoConfiguredProviderError`.

    Args:
        settings: Loaded :class:`aeat.core.config.Settings`.

    Returns:
        The selected default :class:`aeat.application.auth.AuthProviderKind`.

    Raises:
        NoConfiguredProviderError: When no provider is configured.
        UnknownProviderError: When ``settings.aeat_auth_provider``
            points at an unregistered kind.
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
        "No AEAT auth provider is configured yet. Run `aeat setup auth configure` "
        "to set up Cl@ve Móvil, or pass `--provider certificate` once your "
        "FNMT certificate is installed."
    )
