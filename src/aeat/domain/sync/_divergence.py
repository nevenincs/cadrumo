"""Divergence taxonomy and record types.

Every divergence emitted by the classifier is a concrete member of
:data:`DivergencePayload`, a discriminated union over the
:class:`DivergenceKind`-tagged payload models. Each member carries only
the semantic data needed to describe the delta; classification is
assigned per-kind via the static :data:`_CLASSIFICATION_TABLE` and is
therefore deterministic.

The bounded-auto-heal invariant -- classification in ``ADDITIVE`` AND
kind in the allowlist -- is enforced by the healing dispatcher; this
module only provides the typed building blocks.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from ...core.i18n import Translatable
from ._protocols import ModeloIdentifier, PortalIdentifier


class DivergenceClassification(StrEnum):
    """Semantic bucket for any single divergence.

    Attributes:
        ADDITIVE: Live is a pure superset of local; safe to heal when
            the kind is allowlisted.
        BREAKING: Live contradicts local in a way that requires human
            review.
        BENIGN: Cosmetic / audit-only delta.
        SUSPICIOUS: Unexpected shape; always escalates and triggers
            the suspicious runbook.
    """

    ADDITIVE = "additive"
    BREAKING = "breaking"
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"


class DivergenceKind(StrEnum):
    """Concrete shape of a single divergence.

    Every member of :data:`DivergencePayload` uses one of these as its
    ``kind`` discriminator. Additive kinds that are auto-heal candidates
    are listed first; the remaining kinds are either breaking or
    suspicious.

    Attributes:
        CASILLA_ADDED_WITH_DEFAULT: Live introduced a new casilla with
            an explicit default value.
        LABEL_TRANSLATION_ADDED: A new language key appeared inside a
            :class:`aeat.core.i18n.Translatable` label.
        VIGENCIA_EXTENDED: The modelo's ``vigencia_end`` moved forward.
        CASILLA_REMOVED: A casilla present locally is missing live.
        CASILLA_TYPE_CHANGED: The type of an existing casilla changed.
        FORMULA_CHANGED: The formula on a casilla changed.
        LABEL_ES_CHANGED: The authoritative ``es`` label on a casilla
            changed.
        PORTAL_URL_CHANGED: A portal link URL changed.
        FILING_STATUS_CHANGED: A filing entry's status changed live.
        UNKNOWN_SHAPE: Live payload shape failed semantic recognition.
    """

    CASILLA_ADDED_WITH_DEFAULT = "casilla_added_with_default"
    LABEL_TRANSLATION_ADDED = "label_translation_added"
    VIGENCIA_EXTENDED = "vigencia_extended"
    CASILLA_REMOVED = "casilla_removed"
    CASILLA_TYPE_CHANGED = "casilla_type_changed"
    FORMULA_CHANGED = "formula_changed"
    LABEL_ES_CHANGED = "label_es_changed"
    PORTAL_URL_CHANGED = "portal_url_changed"
    FILING_STATUS_CHANGED = "filing_status_changed"
    UNKNOWN_SHAPE = "unknown_shape"


class ResolutionState(StrEnum):
    """Operator-facing resolution state for a divergence record.

    Attributes:
        PENDING: Awaiting triage; the default for newly emitted records.
        AUTO_HEALED: Healed automatically by an additive strategy.
        HUMAN_APPROVED: Operator confirmed the divergence and applied a
            healing action.
        REJECTED: Operator explicitly refused to heal.
    """

    PENDING = "pending"
    AUTO_HEALED = "auto_healed"
    HUMAN_APPROVED = "human_approved"
    REJECTED = "rejected"


class _PayloadBase(BaseModel):
    """Shared config for every concrete :class:`DivergencePayload` member."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class CasillaAddedWithDefault(_PayloadBase):
    """A new casilla appeared live with a default value; local was absent."""

    kind: Literal[DivergenceKind.CASILLA_ADDED_WITH_DEFAULT] = DivergenceKind.CASILLA_ADDED_WITH_DEFAULT
    modelo: ModeloIdentifier
    casilla_id: str
    default: str
    label: Translatable


class LabelTranslationAdded(_PayloadBase):
    """A new language key appeared inside a ``Translatable``."""

    kind: Literal[DivergenceKind.LABEL_TRANSLATION_ADDED] = DivergenceKind.LABEL_TRANSLATION_ADDED
    modelo: ModeloIdentifier
    casilla_id: str
    language: str
    value: str


class VigenciaExtended(_PayloadBase):
    """The modelo's vigencia end date moved forward."""

    kind: Literal[DivergenceKind.VIGENCIA_EXTENDED] = DivergenceKind.VIGENCIA_EXTENDED
    modelo: ModeloIdentifier
    previous_end: date
    new_end: date


class CasillaRemoved(_PayloadBase):
    """A casilla present locally is missing from the live payload."""

    kind: Literal[DivergenceKind.CASILLA_REMOVED] = DivergenceKind.CASILLA_REMOVED
    modelo: ModeloIdentifier
    casilla_id: str


class CasillaTypeChanged(_PayloadBase):
    """The type of a casilla changed on the live side."""

    kind: Literal[DivergenceKind.CASILLA_TYPE_CHANGED] = DivergenceKind.CASILLA_TYPE_CHANGED
    modelo: ModeloIdentifier
    casilla_id: str
    previous_type: str
    new_type: str


class FormulaChanged(_PayloadBase):
    """The formula on a casilla changed."""

    kind: Literal[DivergenceKind.FORMULA_CHANGED] = DivergenceKind.FORMULA_CHANGED
    modelo: ModeloIdentifier
    casilla_id: str
    previous_formula: str | None
    new_formula: str | None


class LabelEsChanged(_PayloadBase):
    """The authoritative ``es`` label on a casilla changed."""

    kind: Literal[DivergenceKind.LABEL_ES_CHANGED] = DivergenceKind.LABEL_ES_CHANGED
    modelo: ModeloIdentifier
    casilla_id: str
    previous_es: str
    new_es: str


class PortalUrlChanged(_PayloadBase):
    """A portal link URL changed on the live manifest."""

    kind: Literal[DivergenceKind.PORTAL_URL_CHANGED] = DivergenceKind.PORTAL_URL_CHANGED
    portal: PortalIdentifier
    previous_url: AnyHttpUrl
    new_url: AnyHttpUrl


class FilingStatusChanged(_PayloadBase):
    """A filing entry's status changed on the live history."""

    kind: Literal[DivergenceKind.FILING_STATUS_CHANGED] = DivergenceKind.FILING_STATUS_CHANGED
    modelo: ModeloIdentifier
    period: str
    previous_status: str
    new_status: str


class UnknownShape(_PayloadBase):
    """Live payload failed semantic classification; shape is unrecognised."""

    kind: Literal[DivergenceKind.UNKNOWN_SHAPE] = DivergenceKind.UNKNOWN_SHAPE
    detail: str


DivergencePayload = Annotated[
    CasillaAddedWithDefault
    | LabelTranslationAdded
    | VigenciaExtended
    | CasillaRemoved
    | CasillaTypeChanged
    | FormulaChanged
    | LabelEsChanged
    | PortalUrlChanged
    | FilingStatusChanged
    | UnknownShape,
    Field(discriminator="kind"),
]


_CLASSIFICATION_TABLE: Mapping[DivergenceKind, DivergenceClassification] = MappingProxyType(
    {
        DivergenceKind.CASILLA_ADDED_WITH_DEFAULT: DivergenceClassification.ADDITIVE,
        DivergenceKind.LABEL_TRANSLATION_ADDED: DivergenceClassification.ADDITIVE,
        DivergenceKind.VIGENCIA_EXTENDED: DivergenceClassification.ADDITIVE,
        DivergenceKind.CASILLA_REMOVED: DivergenceClassification.BREAKING,
        DivergenceKind.CASILLA_TYPE_CHANGED: DivergenceClassification.BREAKING,
        DivergenceKind.FORMULA_CHANGED: DivergenceClassification.BREAKING,
        DivergenceKind.LABEL_ES_CHANGED: DivergenceClassification.BREAKING,
        DivergenceKind.PORTAL_URL_CHANGED: DivergenceClassification.SUSPICIOUS,
        DivergenceKind.FILING_STATUS_CHANGED: DivergenceClassification.BENIGN,
        DivergenceKind.UNKNOWN_SHAPE: DivergenceClassification.SUSPICIOUS,
    }
)


def classify_kind(kind: DivergenceKind) -> DivergenceClassification:
    """Return the static classification bucket for a divergence kind.

    Args:
        kind: The :class:`DivergenceKind` discriminator.

    Returns:
        The deterministic :class:`DivergenceClassification` bucket
        registered for ``kind`` in the static classification table.
    """
    return _CLASSIFICATION_TABLE[kind]


class DivergenceRecord(BaseModel):
    """Persistable divergence record for a single delta.

    Attributes:
        record_id: Stable identifier (typically a hex UUID).
        detected_at: UTC timestamp when the classifier emitted the
            record.
        modelo: Optional :class:`aeat.domain.sync._protocols.ModeloIdentifier`
            scoping the divergence; ``None`` for portal-level deltas.
        classification: Bucket assigned by :func:`classify_kind`.
        payload: The concrete typed payload describing the delta.
        resolution_state: Operator-facing lifecycle state; defaults to
            :attr:`ResolutionState.PENDING` on creation.
        notes: Optional free-text reviewer note.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record_id: str = Field(min_length=1, max_length=128)
    detected_at: datetime
    modelo: ModeloIdentifier | None
    classification: DivergenceClassification
    payload: DivergencePayload
    resolution_state: ResolutionState = ResolutionState.PENDING
    notes: str | None = None
