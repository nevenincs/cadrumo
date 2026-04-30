"""Strict pydantic model for a single modelo's authoritative metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.i18n import Translatable
from ..portals import Portal
from ._applicability import ModeloApplicability
from ._categories import ModeloCadence, ModeloCategory
from ._citations import LegalCitation
from ._codes import ModeloCode


class ModeloMetadata(BaseModel):
    """Authoritative, curated metadata for a single AEAT modelo.

    One instance per modelo in the registry. The model is strict,
    frozen, and rejects unknown keys. Cross-reference invariants that
    span the registry as a whole (``caps_into`` resolution,
    ``submission_portal`` round-trip against ``PORTAL_REGISTRY``) are
    enforced at registry-assembly time, not here, so individual entries
    can be constructed in isolation in unit tests.

    Attributes:
        code: The :class:`ModeloCode` this entry describes.
        official_name_es: Authoritative Spanish name of the modelo.
            Non-empty after stripping.
        display_label: Trilingual display label with non-empty
            ``es`` / ``en`` / ``hu`` keys.
        category: Functional :class:`ModeloCategory`.
        cadence: Canonical filing :class:`ModeloCadence`. Exact
            windows are resolved at query time via the deadline
            engine.
        legal_basis: Non-empty tuple of :class:`LegalCitation`
            objects backing the modelo.
        applicability: :class:`ModeloApplicability` partition over
            :class:`TaxpayerProfile`.
        caps_into: Optional :class:`ModeloCode` the pagos fraccionados
            / retenciones cap into (e.g. 130 caps into 100, 303 caps
            into 390). ``None`` when there is no cap relationship.
        related_modelos: Tuple of related :class:`ModeloCode` entries
            (``receives_from`` / ``replaces`` / sibling forms).
        submission_portal: Typed cross-reference into the AEAT portal
            catalogue. Required non-``None`` for every v1 modelo; the
            field type is ``Portal | None`` to keep the schema open
            for future modelos that may not have a dedicated portal.
        known_gotchas: Tuple of Spanish short-form gotcha strings
            copied from the research doc.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    code: ModeloCode
    official_name_es: str = Field(min_length=1)
    display_label: Translatable
    category: ModeloCategory
    cadence: ModeloCadence
    legal_basis: tuple[LegalCitation, ...] = Field(min_length=1)
    applicability: ModeloApplicability
    caps_into: ModeloCode | None = None
    related_modelos: tuple[ModeloCode, ...] = ()
    submission_portal: Portal | None = None
    known_gotchas: tuple[str, ...] = ()

    @field_validator("official_name_es")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Reject whitespace-only strings on string fields."""
        if not value.strip():
            raise ValueError("value must not be empty or whitespace-only")
        return value

    @field_validator("display_label")
    @classmethod
    def _display_label_trilingual(cls, value: Translatable) -> Translatable:
        """Require non-empty ``es`` / ``en`` / ``hu`` keys on display_label."""
        for key in ("es", "en", "hu"):
            raw = value.get(key)  # type: ignore[misc]
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError(f"display_label.{key} must be a non-empty string")
        return value
