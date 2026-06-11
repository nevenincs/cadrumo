"""Pydantic v2 schema for the :mod:`aeat.domain.filing` subpackage.

Every type in this module is a strict, frozen pydantic v2 model
or a closed :class:`enum.StrEnum`. These are the boundary-crossing
records the rest of the project pins against — keep them stable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ...core._period import Period
from ...core.errors import BaseSeverity
from ...core.i18n import Translatable as tr
from ...core.identity import SubjectTaxId
from ..calculations.registry import BindingId, CasillaId, RegistrySnapshotRef
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
        formula_trace: For ``COMPUTED`` values, the casilla IDs
            that fed the computation. ``None`` for non-computed
            kinds.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: CasillaId
    value: ModeloScalar
    kind: ModeloValueKind
    source: str
    formula_trace: tuple[str, ...] | None = None


class ModeloBindingValue(BaseModel):
    """The typed value of one registry binding on a :class:`ModeloDraft`."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    binding_id: BindingId
    value: ModeloScalar
    kind: ModeloValueKind
    source: str
    row_index: int | None = Field(default=None, ge=1)


class ModeloCasillaProvenance(BaseModel):
    """Regulatory grounding for one casilla carried on a filing draft.

    ``formula_id`` is set for computed casillas (those whose value is
    produced by a registry formula) and ``None`` for manual-input or
    bound casillas. ``legal_refs`` and ``source_refs`` are always
    populated from the registry casilla definition when the draft is
    created.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: CasillaId
    formula_id: str | None = None
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: CasillaId | None
    severity: BaseSeverity
    code: str
    message: tr
    references_rules: tuple[str, ...] = Field(default_factory=tuple)


class ModeloApprovalBasis(BaseModel):
    """Persisted approval-basis digests for deterministic stale detection."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    draft_id: str
    modelo: str
    period: Period
    profile_tax_id: str
    # Typed Spanish NIF/NIE/CIF of the filing subject. Defaults to
    # ``None`` so historical records that predate the field remain
    # loadable; new drafts populate this from the validated profile
    # substrate so the identity is re-checkable at persistence time.
    subject_tax_id: SubjectTaxId | None = None
    # Four-axis coordinates identifying the registry snapshot this
    # draft was built against. Replaces the role of the opaque
    # ``schema_version`` string for re-resolution against the live
    # registry catalogue. Defaults to ``None`` for backward
    # compatibility with persisted records that predate the field;
    # newly built drafts populate this from the snapshot used to
    # produce the casilla values.
    snapshot_ref: RegistrySnapshotRef | None = None
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
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
