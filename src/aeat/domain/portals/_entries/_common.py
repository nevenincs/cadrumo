"""Shared helpers for constructing per-portal entries.

Each entry module in :mod:`aeat.domain.portals._entries` calls
:func:`build_entry` to turn a compact set of keyword arguments into a
fully validated :class:`PortalMetadata`. Keeping this glue private
isolates the repetitive construction boilerplate from the per-portal
data tables.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import HttpUrl, TypeAdapter

from ....core.i18n import Translatable
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata

_URL_ADAPTER: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)


def _to_httpurl(value: str) -> HttpUrl:
    """Coerce a plain string to :class:`pydantic.HttpUrl` under strict mode."""
    return _URL_ADAPTER.validate_python(value)


def build_entry(
    *,
    portal: Portal,
    url: str,
    subdomain: Subdomain,
    category: PortalCategory,
    auth_methods: Iterable[AuthMethod],
    url_stability: UrlStability,
    label: str,
    purpose: str,
    active: bool = True,
    replaced_by: Portal | None = None,
    notes: Iterable[str] = (),
) -> PortalMetadata:
    """Assemble a :class:`PortalMetadata` entry for a single portal.

    Args:
        portal: The :class:`Portal` member this entry describes.
        url: Canonical HTTPS URL as a plain string.
        subdomain: The :class:`Subdomain` the URL is hosted on.
        category: The :class:`PortalCategory` classification.
        auth_methods: Iterable of accepted :class:`AuthMethod` values.
        url_stability: The :class:`UrlStability` tier.
        label: Multilingual display label key.
        purpose: Multilingual purpose description key.
        active: Whether the portal is currently in service.
        replaced_by: When retired, optionally the :class:`Portal`
            member that supersedes this one.
        notes: Iterable of multilingual note keys.

    Returns:
        A validated, frozen :class:`PortalMetadata`.
    """
    return PortalMetadata(
        portal=portal,
        url=_to_httpurl(url),
        subdomain=subdomain,
        category=category,
        auth_methods=frozenset(auth_methods),
        url_stability=url_stability,
        label=Translatable(label),
        purpose=Translatable(purpose),
        active=active,
        replaced_by=replaced_by,
        notes=tuple(Translatable(n) for n in notes),
    )


__all__ = ("build_entry",)
