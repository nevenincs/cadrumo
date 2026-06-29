"""Pydantic v2 schema for the :mod:`aeat.domain.filing` subpackage.

Every type in this module is a strict, frozen pydantic v2 model
or a closed :class:`enum.StrEnum`. These are the boundary-crossing
records the rest of the project pins against — keep them stable.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind, Period
from ...core.errors import BaseSeverity
from ...core.hashing import content_hash_hex
from ...core.i18n import Translatable as tr
from ...core.identity import SubjectTaxId
from ..calculations.registry import BindingId, CasillaId, FormulaId, LegalRefId, RegistrySnapshotRef, SourceRefId
from ..submission import ModeloDraftStatus

APPROVAL_BASIS_VERSION = "review-basis-v1"


class ModeloValueKind(StrEnum):
    """Provenance kind of a :class:`ModeloValue`."""

    LITERAL = "LITERAL"
    COMPUTED = "COMPUTED"
    INHERITED = "INHERITED"
    DEFAULT = "DEFAULT"
    EMPTY = "EMPTY"


# A type alias for the small set of primitive value types a casilla
# can carry. Pydantic will parse JSON values back into the right
# Python type via this union (Decimal is preferred over float for
# any monetary value).
ModeloScalar = Decimal | int | str | bool | date | None


class ModeloValue(BaseModel):
    """The typed value of one casilla on a :class:`ModeloDraft`.

    Attributes:
        casilla_id: Stable casilla ID (e.g. ``"03"``).
        value: The scalar value carried by this casilla. ``None``
            iff ``kind`` is :attr:`ModeloValueKind.EMPTY`.
        kind: Provenance kind — literal user input, computed,
            inherited from a previous draft, default from the
            casilla schema, or empty.
        source: Free-text provenance string — e.g.
            ``"user-supplied"``, ``"computed from 01,02"``,
            ``"default per modelo schema"``.
        formula_trace_casilla_ids: For ``COMPUTED`` values, the casilla IDs
            that fed the computation. ``None`` for non-computed
            kinds.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    value: ModeloScalar
    kind: ModeloValueKind
    source: str
    formula_trace_casilla_ids: tuple[CasillaId, ...] | None = None


class ModeloBindingValue(BaseModel):
    """The typed value of one registry binding on a :class:`ModeloDraft`.

    Carries the same regulatory grounding the casilla half exposes via
    :class:`ModeloCasillaProvenance`: ``legal_refs`` and ``source_refs``
    populated from the binding definition, plus a typed
    :class:`~aeat.core.BindingSourceKind` ``source`` (replacing the former
    free-text provenance string) so a bound value is operator-traceable at
    parity with a computed casilla.

    Attributes:
        binding_id: Stable registry binding id this value materialises.
        value: The scalar value carried for this binding.
        kind: Provenance kind — literal input, computed, inherited, etc.
        source: Typed registry binding source kind (e.g.
            :attr:`~aeat.core.BindingSourceKind.MANUAL_INPUT`,
            :attr:`~aeat.core.BindingSourceKind.LEDGER_IVA_AGGREGATION`).
        legal_refs: Legal references carried from the binding definition.
        source_refs: Source references carried from the binding definition.
        row_index: 1-based row index for multi-row (detail-record) bindings.
    """

    model_config = STRICT_FROZEN_CONFIG

    binding_id: BindingId
    value: ModeloScalar
    kind: ModeloValueKind
    source: BindingSourceKind
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    row_index: int | None = Field(default=None, ge=1)


class ModeloCasillaProvenance(BaseModel):
    """Regulatory grounding for one casilla carried on a filing draft.

    ``formula_id`` is set for computed casillas (those whose value is
    produced by a registry formula) and ``None`` for manual-input or
    bound casillas. ``legal_refs`` and ``source_refs`` are always
    populated from the registry casilla definition when the draft is
    created.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    formula_id: FormulaId | None = None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class ModeloValidationFinding(BaseModel):
    """One finding produced by the validator.

    Attributes:
        casilla_id: The casilla the finding is about, or ``None``
            for cross-cutting findings such as deadline checks.
        severity: ERROR / WARNING / INFO.
        code: A stable machine-readable code (e.g.
            ``"casilla-required-missing"``).
        message: A strictly-typed :class:`Translatable` key.
        references_rules: Tuple of Manual práctico Rule IDs that
            justify the finding (see :class:`aeat.domain.manuals.Rule`).
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId | None
    severity: BaseSeverity
    code: str
    message: tr
    references_rules: tuple[str, ...] = Field(default_factory=tuple)


class ModeloApprovalBasis(BaseModel):
    """Persisted approval-basis digests for deterministic stale detection."""

    model_config = STRICT_FROZEN_CONFIG

    version: str = APPROVAL_BASIS_VERSION
    draft_payload_fingerprint: str
    draft_review_fingerprint: str
    transaction_catalogue_fingerprint: str
    category_profiles_fingerprint: str
    schema_formula_fingerprint: str


class ModeloDraft(BaseModel):
    """A typed, validated draft of one filing.

    The ``draft_id`` is a content-addressed hash of
    ``(modelo, period, profile_tax_id, schema_version, values)``.
    Re-validating a draft preserves its identity because findings,
    status, ``updated_at`` and ``notes`` are deliberately excluded
    from the hash.
    """

    model_config = STRICT_FROZEN_CONFIG

    draft_id: str
    modelo: str
    period: Period
    profile_tax_id: str
    # Typed Spanish NIF/NIE/CIF of the filing subject. New drafts
    # populate this from the validated profile substrate so the
    # identity is re-checkable at persistence time.
    subject_tax_id: SubjectTaxId
    # Four-axis coordinates identifying the registry snapshot this
    # draft was built against. Replaces the role of the opaque
    # ``schema_version`` string for re-resolution against the live
    # registry catalogue. Newly built drafts populate this from the
    # snapshot used to produce the casilla values.
    snapshot_ref: RegistrySnapshotRef
    status: ModeloDraftStatus
    values: tuple[ModeloValue, ...]
    binding_values: tuple[ModeloBindingValue, ...] = Field(default_factory=tuple)
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    findings: tuple[ModeloValidationFinding, ...] = Field(default_factory=tuple)
    created_at: datetime
    updated_at: datetime
    schema_version: str
    notes: str = ""
    approved_at: datetime | None = None
    approved_by: str | None = None
    review_checksum: str | None = None
    approval_basis: ModeloApprovalBasis | None = None


def compute_modelo_draft_id(
    *,
    modelo: str,
    period: Period,
    profile_tax_id: str,
    schema_version: str,
    values: tuple[ModeloValue, ...],
    binding_values: tuple[ModeloBindingValue, ...] = (),
) -> str:
    """Compute the stable, content-addressed ``draft_id``.

    The period is serialised as ``{"filing_year": <int>, "code": "<token>"}``
    so the hash is deterministic and self-consistent regardless of the
    human-readable ``str(period)`` form.

    Args:
        modelo: Modelo string ID.
        period: Typed :class:`~aeat.core.Period` for the filing period.
        profile_tax_id: Taxpayer tax ID.
        schema_version: The casilla DB version this draft was
            built against.
        values: The tuple of :class:`ModeloValue` records to hash.
        binding_values: Optional tuple of :class:`ModeloBindingValue` records
            included in the hash; defaults to an empty tuple.

    Returns:
        A 16-character lowercase hex SHA-256 prefix.
    """
    sorted_values = sorted(values, key=lambda v: v.casilla_id)
    sorted_binding_values = sorted(binding_values, key=lambda v: (v.binding_id, v.row_index or 0))
    payload = {
        "modelo": modelo,
        "period": {"filing_year": period.filing_year, "code": period.registry_token},
        "profile_tax_id": profile_tax_id,
        "schema_version": schema_version,
        "values": [v.model_dump(mode="json") for v in sorted_values],
        "binding_values": [v.model_dump(mode="json") for v in sorted_binding_values],
    }
    return content_hash_hex(payload)[:16]
