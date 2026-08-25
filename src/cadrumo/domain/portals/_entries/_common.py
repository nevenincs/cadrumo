"""Shared helpers for constructing per-portal entries.

Each entry module in :mod:`cadrumo.domain.portals._entries` calls
:func:`build_entry` to turn a compact set of keyword arguments into a
fully validated :class:`PortalMetadata`. Keeping this glue private
isolates the repetitive construction boilerplate from the per-portal
data tables.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import HttpUrl, TypeAdapter

from ....core.config import Settings
from ....core.i18n import Translatable as tr
from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from ..errors import PortalValidationError
from .._hosts import portal_host_origin
from .._metadata import PortalMetadata

_URL_ADAPTER: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)


def _to_httpurl(value: str) -> HttpUrl:
    """Coerce a plain string to :class:`pydantic.HttpUrl` under strict mode."""
    return _URL_ADAPTER.validate_python(value)


def _resolve_host(subdomain: PortalHost) -> str:
    """Return the absolute origin (``https://host``) for a portal subdomain."""
    return portal_host_origin(subdomain)


def portal_path(portal: Portal) -> str:
    """Return the centralized relative path for a portal catalogue entry.

    The :class:`Portal` value addresses the external-constants portal path
    registry.
    """
    paths = Settings.external_constants().aeat.portal_paths.paths
    try:
        return paths[portal.value]
    except KeyError as exc:
        raise PortalValidationError(f"portal path registry lacks {portal.value!r}") from exc


def build_entry(
    *,
    portal: Portal,
    subdomain: PortalHost,
    category: PortalCategory,
    auth_methods: Iterable[AuthMethod],
    url_stability: UrlStability,
    label: str,
    purpose: str,
    url: str | None = None,
    path: str | None = None,
    active: bool = True,
    replaced_by: Portal | None = None,
    notes: Iterable[str] = (),
) -> PortalMetadata:
    """Assemble a :class:`PortalMetadata` entry for a single portal.

    Exactly one of ``url`` or ``path`` must be supplied. When ``path``
    is given, the absolute origin is resolved from the external
    constants registry against ``subdomain``; this keeps per-portal
    files free of host duplication.

    Args:
        portal: The :class:`Portal` member this entry describes.
        subdomain: The :class:`PortalHost` the URL is hosted on.
        category: The :class:`PortalCategory` classification.
        auth_methods: Iterable of accepted :class:`AuthMethod` values.
        url_stability: The :class:`UrlStability` tier.
        label: Multilingual display label key.
        purpose: Multilingual purpose description key.
        url: Canonical absolute HTTPS URL. Mutually exclusive with ``path``.
        path: Path component (must start with ``/``). The host is
            resolved from the registry via ``subdomain``.
        active: Whether the portal is currently in service.
        replaced_by: When retired, optionally the :class:`Portal`
            member that supersedes this one.
        notes: Iterable of multilingual note keys.

    Returns:
        A validated, frozen :class:`PortalMetadata`.

    Raises:
        PortalValidationError: If neither or both of ``url`` and ``path``
            are supplied, or if ``path`` does not start with ``/``.
    """
    if (url is None) == (path is None):
        raise PortalValidationError("build_entry: pass exactly one of `url=` or `path=`")
    if path is not None:
        if not path.startswith("/"):
            raise PortalValidationError("build_entry: `path` must start with '/'")
        url = f"{_resolve_host(subdomain)}{path}"
    assert url is not None
    return PortalMetadata(
        portal=portal,
        url=_to_httpurl(url),
        subdomain=subdomain,
        category=category,
        auth_methods=frozenset(auth_methods),
        url_stability=url_stability,
        label=tr(label),
        purpose=tr(purpose),
        active=active,
        replaced_by=replaced_by,
        notes=tuple(tr(n) for n in notes),
    )


__all__ = ("build_entry", "portal_path")
