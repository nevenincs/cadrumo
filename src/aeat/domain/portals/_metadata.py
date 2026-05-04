"""Strict pydantic model for a single portal's metadata."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from ...core.i18n import Translatable
from ._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from ._codes import Portal

_G_CODE_PATH_RE: re.Pattern[str] = re.compile(r"^/Sede/procedimientoini/G[A-Z0-9]{3}\.shtml$")


class PortalMetadata(BaseModel):
    """Curated metadata for a single AEAT portal.

    One instance per :class:`Portal` member in the registry. The model
    is strict, frozen, and rejects unknown keys. Structural
    cross-reference invariants that span the registry as a whole are
    enforced at registry-assembly time by
    :func:`aeat.domain.portals._registry._finalise_registry` rather than
    here, so individual entries can be constructed in isolation.

    Attributes:
        portal: The :class:`Portal` this entry describes.
        url: Canonical HTTPS URL.
        subdomain: The :class:`Subdomain` the URL is hosted on. Must
            match ``url.host``.
        category: :class:`PortalCategory` the portal belongs to.
        auth_methods: Non-empty frozenset of accepted
            :class:`AuthMethod` values. ``AuthMethod.ANONYMOUS`` is
            mutually exclusive with every other method.
        url_stability: :class:`UrlStability` tier for read-only portal
            monitoring priority.
        label: Translation key for the display label.
        purpose_es: One-sentence Spanish purpose, non-empty after
            stripping.
        active: ``False`` marks retired portals preserved for
            historical lookup.
        replaced_by: When ``active is False``, optionally points to the
            :class:`Portal` member that supersedes this one. When
            ``None`` and ``active is False``, ``notes_es`` must carry
            a non-empty discontinuation rationale.
        notes_es: Tuple of Spanish short-form notes / gotchas.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    portal: Portal
    url: HttpUrl
    subdomain: Subdomain
    category: PortalCategory
    auth_methods: frozenset[AuthMethod] = Field(min_length=1)
    url_stability: UrlStability
    label: Translatable
    purpose_es: str = Field(min_length=1)
    active: bool = True
    replaced_by: Portal | None = None
    notes_es: tuple[str, ...] = ()

    @field_validator("purpose_es")
    @classmethod
    def _purpose_not_blank(cls, value: str) -> str:
        """Reject whitespace-only purpose strings."""
        if not value.strip():
            raise ValueError("purpose_es must not be empty or whitespace-only")
        return value

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, value: Translatable) -> Translatable:
        """Reject whitespace-only label keys."""
        if not value.strip():
            raise ValueError("label must not be empty or whitespace-only")
        return value

    @field_validator("url")
    @classmethod
    def _url_is_https(cls, value: HttpUrl) -> HttpUrl:
        """Reject non-HTTPS URLs."""
        if value.scheme != "https":
            raise ValueError(f"url scheme must be https, got {value.scheme!r}")
        return value

    @model_validator(mode="after")
    def _validate_invariants(self) -> PortalMetadata:
        """Enforce cross-field invariants on a single entry."""
        # ANONYMOUS exclusivity.
        if AuthMethod.ANONYMOUS in self.auth_methods and len(self.auth_methods) != 1:
            raise ValueError("AuthMethod.ANONYMOUS must be the sole method when present")

        # Subdomain must match URL host.
        host = self.url.host
        if host != self.subdomain.value:
            raise ValueError(f"url host {host!r} does not match subdomain {self.subdomain.value!r}")

        # G-code path check for active FILING / CENSUS entries.
        if self.active and self.category in {PortalCategory.FILING, PortalCategory.CENSUS}:
            path = self.url.path or ""
            if not _G_CODE_PATH_RE.match(path):
                raise ValueError(
                    f"active {self.category.value} portal url path must match "
                    f"/Sede/procedimientoini/G<code>.shtml, got {path!r}"
                )

        # Retired-without-replacement fallback.
        if not self.active and self.replaced_by is None and not self.notes_es:
            raise ValueError("retired portal without replaced_by must carry a non-empty notes_es rationale")

        # Replaced-by may only be set when active is False.
        if self.active and self.replaced_by is not None:
            raise ValueError("replaced_by must be None when active is True")

        return self
