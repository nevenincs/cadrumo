"""Pydantic v2 schema for the :mod:`domain.filing` subpackage.

Every type in this module is a strict, frozen pydantic v2 model
or a closed :class:`enum.StrEnum`. These are the boundary-crossing
records the rest of the project pins against — keep them stable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind, Period
from ...core.errors import BaseSeverity
from ...core.hashing import content_hash_hex
from ...core.i18n import Translatable as tr
from ...core.identity import SubjectTaxId
from ...core.time import UtcInstant
from ..calculations.registry import BindingId, CasillaId, FormulaId, LegalRefId, RegistrySnapshotRef, SourceRefId
from ..submission import ModeloDraftStatus
from ._errors import FilingValidationError

APPROVAL_BASIS_VERSION = "review-basis-v4"


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

    @model_validator(mode="after")
    def _enforce_provenance_matrix(self) -> ModeloValue:
        """Confirm ``value`` and ``formula_trace_casilla_ids`` agree with ``kind``.

        The attribute contract above is a state matrix, not three independent
        fields: a value is absent exactly when the casilla is EMPTY, and a
        formula trace exists exactly when the value was COMPUTED. Left
        unenforced, a directly-constructed or storage-rehydrated draft can carry
        an EMPTY casilla holding a Decimal, a COMPUTED casilla with no trace to
        audit it against, or a LITERAL casilla claiming a formula lineage it
        never had — none of which the builder produces, and none of which the
        downstream formula check sees unless it is explicitly invoked.

        An empty trace tuple is legitimate: a registry formula over constants
        declares no casilla inputs, so COMPUTED requires the trace to be
        *present*, not non-empty.
        """
        if (self.value is None) is not (self.kind is ModeloValueKind.EMPTY):
            raise FilingValidationError(
                f"casilla {self.casilla_id!r}: value is None only for kind EMPTY; "
                f"got kind={self.kind.value!r} with value={self.value!r}",
            )
        if (self.formula_trace_casilla_ids is not None) is not (self.kind is ModeloValueKind.COMPUTED):
            raise FilingValidationError(
                f"casilla {self.casilla_id!r}: formula_trace_casilla_ids is carried only for kind "
                f"COMPUTED; got kind={self.kind.value!r} with trace={self.formula_trace_casilla_ids!r}",
            )
        return self


class ModeloBindingValue(BaseModel):
    """The typed value of one registry binding on a :class:`ModeloDraft`.

    Carries the same regulatory grounding the casilla half exposes via
    :class:`ModeloCasillaProvenance`: ``legal_refs`` and ``source_refs``
    populated from the binding definition, plus a typed
    :class:`~core.BindingSourceKind` ``source`` (replacing the former
    free-text provenance string) so a bound value is operator-traceable at
    parity with a computed casilla.

    Attributes:
        binding_id: Stable registry binding id this value materialises.
        value: The scalar value carried for this binding.
        kind: Provenance kind — literal input, computed, inherited, etc.
        source: Typed registry binding source kind (e.g.
            :attr:`~core.BindingSourceKind.MANUAL_INPUT`,
            :attr:`~core.BindingSourceKind.LEDGER_IVA_AGGREGATION`).
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
            justify the finding (see :class:`domain.manuals.Rule`).
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
    invoice_catalogue_fingerprint: str
    prior_filing_observations_fingerprint: str
    profile_activity_fingerprint: str
    category_profiles_fingerprint: str
    schema_formula_fingerprint: str


def registry_schema_version(*, modelo: str, revision_id: str) -> str:
    """Return the canonical ``registry:{modelo}:{revision}`` schema marker.

    The marker names the registry modelo and revision a filing artefact was
    built against. It is the sole declaration of that format: the runtime
    projection, the draft's ``schema_version``, and the staleness comparisons in
    :mod:`application.filing` all derive it here rather than re-inlining the
    f-string, so the marker and the coherence checks that read it cannot drift
    apart.
    """
    return f"registry:{modelo}:{revision_id}"


class ModeloDraft(BaseModel):
    """A typed, validated draft of one filing.

    The ``draft_id`` is a content-addressed hash of
    ``(modelo, period, profile_tax_id, snapshot_ref, values)``.
    Re-validating a draft preserves its identity because findings,
    status, ``updated_at`` and ``notes`` are deliberately excluded
    from the hash.
    """

    model_config = STRICT_FROZEN_CONFIG

    draft_id: str
    modelo: str
    period: Period
    profile_tax_id: SubjectTaxId
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
    # Lifecycle instants are typed, not bare datetimes: draft ordering and the
    # approval decision compare them, and a naive or offset value makes those
    # comparisons ambiguous. ``UtcInstant`` is the shared core contract, so the
    # refusal lives in the type rather than in a fourth hand-rolled validator.
    created_at: UtcInstant
    updated_at: UtcInstant
    schema_version: str
    notes: str = ""
    approved_at: UtcInstant | None = None
    approved_by: str | None = None
    review_checksum: str | None = None
    approval_basis: ModeloApprovalBasis | None = None

    @model_validator(mode="after")
    def _enforce_draft_invariants(self) -> ModeloDraft:
        """Confirm the draft's cross-field identity invariants hold.

        ``profile_tax_id`` and ``subject_tax_id`` are two axes of one taxpayer
        identity, not two independent parties: the builder copies a single
        validated profile identity into both, and no consumer distinguishes
        them. Typing each as :data:`~core.identity.SubjectTaxId` only checks the
        AEAT checksum of each value in isolation, so two *individually valid*
        but different NIFs pass — a draft naming one taxpayer in the profile
        axis and another in the filing-subject axis, preserved intact across the
        encrypted round-trip. Only ``profile_tax_id`` is hashed into
        ``draft_id``, so the divergence is not even visible in the identity.
        """
        if self.profile_tax_id != self.subject_tax_id:
            raise FilingValidationError(
                f"draft taxpayer identity diverges: profile_tax_id {self.profile_tax_id!r} "
                f"and subject_tax_id {self.subject_tax_id!r} must name one taxpayer",
            )
        if self.modelo != self.snapshot_ref.modelo:
            raise FilingValidationError(
                f"draft modelo {self.modelo!r} does not match its snapshot_ref modelo "
                f"{self.snapshot_ref.modelo!r}",
            )
        expected_schema_version = registry_schema_version(
            modelo=self.snapshot_ref.modelo,
            revision_id=self.snapshot_ref.revision_id,
        )
        if self.schema_version != expected_schema_version:
            raise FilingValidationError(
                f"draft schema_version {self.schema_version!r} does not match the registry marker "
                f"{expected_schema_version!r} derived from snapshot_ref "
                f"(modelo={self.snapshot_ref.modelo!r}, revision={self.snapshot_ref.revision_id!r})",
            )
        self._enforce_snapshot_period_coherence()
        self._enforce_collection_coordinate_uniqueness()
        return self

    def _enforce_snapshot_period_coherence(self) -> None:
        """Confirm ``period`` and ``snapshot_ref`` name the same filing period.

        Scoped to the year and period axes only: the modelo axis is already
        checked above, so this closes the remaining half of the coordinate
        contract rather than restating it.

        The builder derives both from one value --
        ``filing_year, registry_period = period.filing_year, period.registry_token``
        feeds ``modelo_year`` and ``period`` on the ref it constructs -- so
        equality is the invariant, not an approximation of one. Direct
        construction and repository rehydration could otherwise accept a draft
        for 2026/1T carrying a snapshot reference for 2025/4T, and that
        mismatch reaches review, approval, and downstream registry re-resolution
        unchanged, because every later consumer trusts whichever coordinate it
        happens to read.
        """
        if self.snapshot_ref.modelo_year != self.period.filing_year:
            raise FilingValidationError(
                f"draft period filing year {self.period.filing_year!r} does not match its "
                f"snapshot_ref modelo_year {self.snapshot_ref.modelo_year!r}",
            )
        if self.snapshot_ref.period != self.period.registry_token:
            raise FilingValidationError(
                f"draft period token {self.period.registry_token!r} does not match its "
                f"snapshot_ref period {self.snapshot_ref.period!r}",
            )

    def _enforce_collection_coordinate_uniqueness(self) -> None:
        """Confirm no casilla or binding coordinate is claimed twice.

        The draft builders reject duplicate inputs before constructing a draft,
        but that guards only the build path: the persisted tuples had no
        uniqueness rule, so direct construction and rehydration accepted two
        rows for one casilla, or two for one ``(binding_id, row_index)``. Lookup
        then resolves to whichever row comes first and the last writer wins
        silently -- ambiguity inside an otherwise strictly typed aggregate, and
        one that also makes ``draft_id`` a hash over a value whose meaning
        depends on tuple order.

        ``row_index`` is part of the binding coordinate, so a repeating record
        legitimately carries the same ``binding_id`` many times; only a repeated
        pair is a duplicate.
        """
        casilla_ids = [value.casilla_id for value in self.values]
        duplicate_casillas = sorted({key for key in casilla_ids if casilla_ids.count(key) > 1})
        if duplicate_casillas:
            listed = ", ".join(repr(key) for key in duplicate_casillas)
            raise FilingValidationError(f"draft values claim a casilla more than once: {listed}")

        binding_keys = [(value.binding_id, value.row_index) for value in self.binding_values]
        duplicate_bindings = sorted({key for key in binding_keys if binding_keys.count(key) > 1})
        if duplicate_bindings:
            listed = ", ".join(f"{binding_id!r} row {row_index!r}" for binding_id, row_index in duplicate_bindings)
            raise FilingValidationError(f"draft binding_values claim a coordinate more than once: {listed}")


def compute_modelo_draft_id(
    *,
    modelo: str,
    period: Period,
    profile_tax_id: SubjectTaxId,
    snapshot_ref: RegistrySnapshotRef,
    values: tuple[ModeloValue, ...],
    binding_values: tuple[ModeloBindingValue, ...] = (),
) -> str:
    """Compute the stable, content-addressed ``draft_id``.

    The period is serialised as ``{"filing_year": <int>, "code": "<token>"}``
    so the hash is deterministic and self-consistent regardless of the
    human-readable ``str(period)`` form.

    Args:
        modelo: Modelo string ID.
        period: Typed :class:`~core.Period` for the filing period.
        profile_tax_id: Validated taxpayer tax ID.
        snapshot_ref: Typed registry snapshot coordinate this draft was
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
        "snapshot_ref": snapshot_ref.model_dump(mode="json"),
        "values": [v.model_dump(mode="json") for v in sorted_values],
        "binding_values": [v.model_dump(mode="json") for v in sorted_binding_values],
    }
    return content_hash_hex(payload)[:16]
