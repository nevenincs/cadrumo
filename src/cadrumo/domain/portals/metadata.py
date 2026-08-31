"""Define :class:`PortalMetadata` for one :class:`Portal` catalogue entry.

The model binds each URL to its :class:`PortalHost`,
:class:`PortalCategory`, accepted :class:`AuthMethod` values, and
:class:`UrlStability` tier before registry assembly.
"""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from ...core.external_constants import load_external_constants
from ...core.i18n import Translatable as tr
from ...core.models import STRICT_FROZEN_CONFIG
from .categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .codes import Portal
from .errors import PortalValidationError
from .hosts import portal_host_name


@lru_cache(maxsize=1)
def _filing_censo_path_re() -> re.Pattern[str]:
    """Return the centralized AEAT filing/censo portal path pattern."""
    return re.compile(load_external_constants().aeat.portal_paths.filing_censo_path_regex)


def _filing_censo_path_description() -> str:
    """Return the centralized human-readable filing/censo portal path shape."""
    return load_external_constants().aeat.portal_paths.filing_censo_path_description


class PortalMetadata(BaseModel):
    """Curated metadata for a single AEAT portal.

    One instance per :class:`Portal` member in the registry. The model
    is strict, frozen, and rejects unknown keys. Structural
    cross-reference invariants that span the registry as a whole are
    enforced at registry-assembly time by
    :func:`cadrumo.domain.portals.registry._finalise_registry` rather than
    here, so individual entries can be constructed in isolation.

    Attributes:
        portal: The :class:`Portal` this entry describes.
        url: Canonical HTTPS URL.
        subdomain: The :class:`PortalHost` the URL is hosted on. Must
            match ``url.host``.
        category: :class:`PortalCategory` the portal belongs to.
        auth_methods: Non-empty frozenset of accepted
            :class:`AuthMethod` values. ``AuthMethod.ANONYMOUS`` is
            mutually exclusive with every other method.
        url_stability: :class:`UrlStability` tier for read-only portal
            monitoring priority.
        label: Translation key for the display label.
        purpose: Translation key for the purpose description.
        active: ``False`` marks retired portals preserved for
            historical lookup.
        replaced_by: When ``active is False``, optionally points to the
            :class:`Portal` member that supersedes this one. When
            ``None`` and ``active is False``, ``notes`` must carry
            a non-empty discontinuation rationale.
        notes: Tuple of translation keys for notes.
    """

    model_config = STRICT_FROZEN_CONFIG

    portal: Portal
    url: HttpUrl
    subdomain: PortalHost
    category: PortalCategory
    auth_methods: frozenset[AuthMethod] = Field(min_length=1)
    url_stability: UrlStability
    label: tr
    purpose: tr
    active: bool = True
    replaced_by: Portal | None = None
    notes: tuple[tr, ...] = ()

    @field_validator("purpose")
    @classmethod
    def _purpose_not_blank(cls, value: tr) -> tr:
        """Reject whitespace-only purpose keys."""
        if not value.strip():
            raise PortalValidationError("purpose must not be empty or whitespace-only")
        return value

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, value: tr) -> tr:
        """Reject whitespace-only label keys."""
        if not value.strip():
            raise PortalValidationError("label must not be empty or whitespace-only")
        return value

    @field_validator("url")
    @classmethod
    def _url_is_https(cls, value: HttpUrl) -> HttpUrl:
        """Reject non-HTTPS URLs."""
        if value.scheme != "https":
            raise PortalValidationError(f"url scheme must be https, got {value.scheme!r}")
        return value

    @model_validator(mode="after")
    def _validate_invariants(self) -> PortalMetadata:
        """Enforce cross-field invariants on a single entry."""
        _validate_auth_method_exclusivity(self)
        _validate_portal_host(self)
        _validate_active_portal_path(self)
        _validate_portal_lifecycle(self)
        return self


def _validate_auth_method_exclusivity(metadata: PortalMetadata) -> None:
    if AuthMethod.ANONYMOUS in metadata.auth_methods and len(metadata.auth_methods) != 1:
        raise PortalValidationError("AuthMethod.ANONYMOUS must be the sole method when present")


def _validate_portal_host(metadata: PortalMetadata) -> None:
    host = metadata.url.host
    expected_host = portal_host_name(metadata.subdomain)
    if host != expected_host:
        raise PortalValidationError(f"url host {host!r} does not match subdomain {expected_host!r}")


def _validate_active_portal_path(metadata: PortalMetadata) -> None:
    if not metadata.active or metadata.category not in {PortalCategory.FILING, PortalCategory.CENSO}:
        return
    path = metadata.url.path or ""
    if not _filing_censo_path_re().match(path):
        raise PortalValidationError(
            f"active {metadata.category.value} portal url path must match "
            f"{_filing_censo_path_description()}, got {path!r}",
        )


def _validate_portal_lifecycle(metadata: PortalMetadata) -> None:
    if not metadata.active and metadata.replaced_by is None and not metadata.notes:
        raise PortalValidationError("retired portal without replaced_by must carry a non-empty notes rationale")
    if metadata.replaced_by is not None and metadata.replaced_by == metadata.portal:
        raise PortalValidationError(f"portal {metadata.portal!r} cannot be replaced by itself")
    if metadata.active and metadata.replaced_by is not None:
        raise PortalValidationError("replaced_by must be None when active is True")


__all__ = ["PortalMetadata"]
