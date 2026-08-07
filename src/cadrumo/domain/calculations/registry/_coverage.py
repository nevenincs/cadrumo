"""Coverage ledger for registry authority and verification tiers.

Audits every :class:`ModeloDefinition` and :class:`ModeloRevision` in the
registry for the four mandatory evidence tiers (legal authority, official
source guidance, executable parity, and layout authority). Each revision
is examined through a :class:`RegistrySnapshot` so referential integrity is
verified before coverage is assessed.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr, computed_field, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ._errors import RegistryValidationError
from ._ids import BindingId, CrossReferenceId, LegalRefId, SourceRefId, WorkbookParityRefId
from ._schema import (
    DataBindingDefinition,
    EvidenceTier,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    RegistryCatalogues,
    RegistrySnapshot,
    RelationDefinition,
)
from ._snapshot import build_validated_snapshot
from ._validate import RegistryValidator

CoverageGateStatus = Literal["satisfied", "gap"]
RequiredCoverageTier = Literal["legal_authority", "official_source_guidance", "layout_authority"]

REQUIRED_COVERAGE_TIERS: tuple[RequiredCoverageTier, ...] = (
    "legal_authority",
    "official_source_guidance",
    "layout_authority",
)
"""The evidence tiers a revision cannot be filing-grade without.

Public because the distinction is load-bearing outside this module too: a gap on
one of these is a failure, while a gap on ``executable_parity_evidence`` is a
reported absence, and a consumer that cannot tell them apart reports an expected
absence as a defect.
"""


class CoverageModel(BaseModel):
    """Strict frozen base for coverage reports."""

    model_config = STRICT_FROZEN_CONFIG


class EvidenceTierCoverageGate(CoverageModel):
    """Coverage state for one evidence tier."""

    tier: EvidenceTier
    status: CoverageGateStatus
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    workbook_refs: tuple[WorkbookParityRefId, ...] = ()
    cross_reference_refs: tuple[CrossReferenceId, ...] = ()
    detail: str

    @model_validator(mode="after")
    def _validate_status_matches_evidence(self) -> EvidenceTierCoverageGate:
        has_evidence = bool(
            self.legal_refs or self.source_refs or self.workbook_refs or self.cross_reference_refs,
        )
        if self.status == "satisfied" and not has_evidence:
            raise RegistryValidationError(f"{self.tier} coverage cannot be satisfied without evidence refs")
        if self.status == "gap" and has_evidence:
            raise RegistryValidationError(f"{self.tier} coverage gap cannot carry evidence refs")
        return self


class ModelLawCoverageLedger(CoverageModel):
    """Per-modelo/revision coverage ledger for legal, source, parity, and layout evidence."""

    modelo: str
    revision: str
    gates: tuple[EvidenceTierCoverageGate, ...]

    @property
    def gaps(self) -> tuple[EvidenceTierCoverageGate, ...]:
        """Return :class:`EvidenceTierCoverageGate` entries that have no supporting registry evidence."""
        return tuple(gate for gate in self.gates if gate.status == "gap")


class RegistryCoverageAudit(CoverageModel):
    """Audit result for model-law coverage across the committed registry."""

    ledgers: tuple[ModelLawCoverageLedger, ...]
    required_gate_failures: tuple[str, ...]
    executable_parity_gaps: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether every mandatory model-law evidence tier is covered."""
        return not self.required_gate_failures


ConstructEvidenceKind = Literal["formula", "parameter", "binding", "relation", "selector"]
ConstructEvidenceStatus = Literal["grounded", "inherited", "unresolved", "unmeasured", "unvalidated"]


class _AuthorityCheckProof:
    """Opaque proof object held only by the validated audit fold."""

    __slots__ = ()


_AUTHORITY_CHECK_PROOF = _AuthorityCheckProof()


class ConstructEvidenceRow(CoverageModel):
    """Legal/source evidence for one revision-level calculation construct.

    A selector is a typed child of a binding and has no independent legal/source
    fields in the registry schema. Its row therefore carries the owning binding
    references with ``status='inherited'`` and says so in ``reason``. This keeps
    the selector visible without turning binding evidence into an independent
    selector claim.
    """

    kind: ConstructEvidenceKind
    construct_id: str = Field(min_length=1, max_length=160)
    binding_id: BindingId | None = None
    status: ConstructEvidenceStatus
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    reason: str = Field(min_length=1, max_length=1024)
    _authority_proof: _AuthorityCheckProof | None = PrivateAttr(default=None)

    @computed_field
    @property
    def authority_checked(self) -> bool:
        """Return whether this row was created through the validated audit fold."""
        return self._authority_proof is _AUTHORITY_CHECK_PROOF

    @model_validator(mode="after")
    def _validate_evidence_shape(self) -> ConstructEvidenceRow:
        if self.kind == "selector":
            if self.binding_id is None:
                raise RegistryValidationError("selector evidence rows must identify their owning binding")
            if self.construct_id != self.binding_id:
                raise RegistryValidationError("selector evidence construct_id must equal binding_id")
        elif self.binding_id is not None:
            raise RegistryValidationError("only selector evidence rows may declare binding_id")

        has_legal = bool(self.legal_refs)
        has_source = bool(self.source_refs)
        if self.status == "grounded" and not (has_legal and has_source):
            raise RegistryValidationError("grounded construct evidence requires legal and source refs")
        if self.status == "inherited":
            if self.kind != "selector":
                raise RegistryValidationError("only selector evidence may be inherited")
            if not (has_legal and has_source):
                raise RegistryValidationError("inherited selector evidence requires owning binding refs")
        if self.status in {"grounded", "inherited"} and not self.authority_checked:
            raise RegistryValidationError(
                "complete construct evidence requires an authority-checked registry validation boundary",
            )
        if self.status == "unvalidated" and not (has_legal and has_source):
            raise RegistryValidationError("unvalidated construct evidence requires declared legal and source refs")
        if self.status == "unresolved" and has_legal and has_source:
            raise RegistryValidationError("unresolved construct evidence cannot carry complete refs")
        if self.status == "unmeasured" and (has_legal or has_source):
            raise RegistryValidationError("unmeasured construct evidence cannot carry refs")
        return self


class ConstructEvidenceLedger(CoverageModel):
    """Per-modelo/revision construct evidence rows, separate from casilla floors."""

    modelo: str
    revision: str
    rows: tuple[ConstructEvidenceRow, ...]

    @model_validator(mode="after")
    def _rows_are_unique(self) -> ConstructEvidenceLedger:
        coordinates = [(row.kind, row.construct_id) for row in self.rows]
        if len(coordinates) != len(set(coordinates)):
            raise RegistryValidationError("construct evidence rows must have unique kind/id coordinates")
        return self

    @property
    def gaps(self) -> tuple[ConstructEvidenceRow, ...]:
        """Return construct rows whose own or inherited evidence is incomplete."""
        return tuple(row for row in self.rows if row.status in {"unresolved", "unmeasured", "unvalidated"})


class RegistryConstructEvidenceAudit(CoverageModel):
    """Registry-wide construct evidence audit with an explicit finite denominator."""

    ledgers: tuple[ConstructEvidenceLedger, ...]

    @property
    def gaps(self) -> tuple[ConstructEvidenceRow, ...]:
        """Return all unresolved, unmeasured, or unvalidated construct rows."""
        return tuple(row for ledger in self.ledgers for row in ledger.gaps)

    @property
    def ok(self) -> bool:
        """Return whether every enumerated construct has complete evidence."""
        return not self.gaps


def audit_registry_model_law_coverage(
    modelos: Iterable[ModeloDefinition],
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
) -> RegistryCoverageAudit:
    """Validate registry coverage ledgers and return a :class:`RegistryCoverageAudit`.

    Legal authority, official guidance, and layout authority are mandatory for
    every revision because the registry cannot be filing-grade without them.
    Executable parity remains a reported gap unless an official safe calculator
    or formula workbook exists for the revision.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances to audit.
        catalogues: Legal and source catalogues for reference validation.
        source_root: Filesystem root for resolving source artefacts.
    """
    modelo_tuple = tuple(sorted(modelos, key=lambda item: item.id))
    RegistryValidator(catalogues, source_root=source_root).validate_registry(modelo_tuple)

    ledgers: list[ModelLawCoverageLedger] = []
    required_gate_failures: list[str] = []
    executable_parity_gaps: list[str] = []
    for modelo in modelo_tuple:
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            snapshot = build_validated_snapshot(
                modelo,
                catalogues,
                filing_year=_representative_year(revision),
                period=revision.period_selector.periods[0],
                revision_id=revision.id,
            )
            ledger = build_model_law_coverage_ledger(snapshot)
            ledgers.append(ledger)
            gates = {gate.tier: gate for gate in ledger.gates}
            for tier in REQUIRED_COVERAGE_TIERS:
                gate = gates[tier]
                if gate.status == "gap":
                    required_gate_failures.append(f"modelo {modelo.id} revision {revision.id}: {tier} coverage gap")
            parity_gate = gates["executable_parity_evidence"]
            if parity_gate.status == "gap" and (revision.formulas or revision.algorithm_bindings):
                executable_parity_gaps.append(
                    f"modelo {modelo.id} revision {revision.id}: executable_parity_evidence coverage gap",
                )

    return RegistryCoverageAudit(
        ledgers=tuple(ledgers),
        required_gate_failures=tuple(required_gate_failures),
        executable_parity_gaps=tuple(executable_parity_gaps),
    )


def audit_registry_construct_evidence(
    modelos: Iterable[ModeloDefinition],
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
) -> RegistryConstructEvidenceAudit:
    """Build construct evidence ledgers from the validated registry authority.

    The fold validates the given :class:`ModeloDefinition` set and enumerates
    only revision-level declarations. It deliberately does
    not turn revision evidence floors or casilla declarations into construct
    evidence, and it never supplies a reference that is absent from the owning
    declaration.
    """
    modelo_tuple = tuple(sorted(modelos, key=lambda item: item.id))
    RegistryValidator(catalogues, source_root=source_root).validate_registry(modelo_tuple)

    ledgers: list[ConstructEvidenceLedger] = []
    for modelo in modelo_tuple:
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            snapshot = build_validated_snapshot(
                modelo,
                catalogues,
                filing_year=_representative_year(revision),
                period=revision.period_selector.periods[0],
                revision_id=revision.id,
            )
            ledgers.append(_build_construct_evidence_ledger(snapshot, authority_proof=_AUTHORITY_CHECK_PROOF))
    return RegistryConstructEvidenceAudit(ledgers=tuple(ledgers))


def build_model_law_coverage_ledger(snapshot: RegistrySnapshot) -> ModelLawCoverageLedger:
    """Build the four-tier coverage ledger for a validated registry snapshot.

    Args:
        snapshot: The :class:`RegistrySnapshot` to assess for model-law coverage.

    Returns:
        A :class:`ModelLawCoverageLedger` summarising coverage across all evidence tiers.
    """
    return ModelLawCoverageLedger(
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        gates=(
            _legal_authority_gate(snapshot),
            _source_guidance_gate(snapshot),
            _executable_parity_gate(snapshot),
            _layout_authority_gate(snapshot),
        ),
    )


def build_construct_evidence_ledger(
    snapshot: RegistrySnapshot,
) -> ConstructEvidenceLedger:
    """Build declared legal/source rows from a :class:`RegistrySnapshot`.

    Reads the snapshot's declarations as given, claiming no registry validation.
    """
    return _build_construct_evidence_ledger(snapshot, authority_proof=None)


def _build_construct_evidence_ledger(
    snapshot: RegistrySnapshot,
    *,
    authority_proof: _AuthorityCheckProof | None,
) -> ConstructEvidenceLedger:
    """Build construct rows, optionally under the private validated-audit proof."""
    revision = snapshot.revision
    rows: list[ConstructEvidenceRow] = []
    rows.extend(
        _declared_construct_evidence_row(declaration, kind="formula", authority_proof=authority_proof)
        for declaration in revision.formulas
    )
    rows.extend(
        _declared_construct_evidence_row(declaration, kind="parameter", authority_proof=authority_proof)
        for declaration in revision.parameters
    )
    rows.extend(
        _declared_construct_evidence_row(declaration, kind="binding", authority_proof=authority_proof)
        for declaration in revision.bindings
    )
    rows.extend(
        _declared_construct_evidence_row(declaration, kind="relation", authority_proof=authority_proof)
        for declaration in revision.relations
    )

    for binding in revision.bindings:
        declared_status = _status_for_declared_refs(binding.legal_refs, binding.source_refs)
        authority_checked = authority_proof is _AUTHORITY_CHECK_PROOF
        if declared_status == "grounded" and authority_checked:
            selector_status: ConstructEvidenceStatus = "inherited"
            reason = f"selector evidence is inherited from binding {binding.id!r}"
        elif declared_status == "grounded":
            selector_status = "unvalidated"
            reason = f"selector evidence has refs but no validated registry authority for binding {binding.id!r}"
        else:
            selector_status = declared_status
            reason = f"selector evidence cannot inherit complete refs from binding {binding.id!r}"
        rows.append(
            _construct_evidence_row(
                kind="selector",
                construct_id=binding.id,
                binding_id=binding.id,
                status=selector_status,
                legal_refs=tuple(binding.legal_refs),
                source_refs=tuple(binding.source_refs),
                reason=(f"authority-checked {reason}" if authority_checked else reason),
                authority_proof=authority_proof,
            ),
        )

    rows.sort(key=lambda row: (row.kind, row.construct_id))
    return ConstructEvidenceLedger(modelo=snapshot.modelo.id, revision=revision.id, rows=tuple(rows))


def _declared_construct_evidence_row(
    declaration: FormulaDefinition | ParameterDefinition | DataBindingDefinition | RelationDefinition,
    *,
    kind: ConstructEvidenceKind,
    authority_proof: _AuthorityCheckProof | None,
) -> ConstructEvidenceRow:
    declared_status = _status_for_declared_refs(declaration.legal_refs, declaration.source_refs)
    authority_checked = authority_proof is _AUTHORITY_CHECK_PROOF
    status: ConstructEvidenceStatus = (
        declared_status if authority_checked or declared_status != "grounded" else "unvalidated"
    )
    return _construct_evidence_row(
        kind=kind,
        construct_id=declaration.id,
        status=status,
        legal_refs=tuple(declaration.legal_refs),
        source_refs=tuple(declaration.source_refs),
        reason=(
            f"authority-checked {kind} declaration {declaration.id!r} carries its own legal/source refs"
            if authority_checked
            else f"{kind} declaration {declaration.id!r} carries its own legal/source refs"
        ),
        authority_proof=authority_proof,
    )


def _construct_evidence_row(
    *,
    kind: ConstructEvidenceKind,
    construct_id: str,
    binding_id: BindingId | None = None,
    status: ConstructEvidenceStatus,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
    reason: str,
    authority_proof: _AuthorityCheckProof | None,
) -> ConstructEvidenceRow:
    """Create a row and attach the private proof only after shape validation."""
    if authority_proof is not _AUTHORITY_CHECK_PROOF or status not in {"grounded", "inherited"}:
        return ConstructEvidenceRow(
            kind=kind,
            construct_id=construct_id,
            binding_id=binding_id,
            status=status,
            legal_refs=legal_refs,
            source_refs=source_refs,
            reason=reason,
        )

    unvalidated_row = ConstructEvidenceRow(
        kind=kind,
        construct_id=construct_id,
        binding_id=binding_id,
        status="unvalidated",
        legal_refs=legal_refs,
        source_refs=source_refs,
        reason=reason,
    )
    object.__setattr__(unvalidated_row, "status", status)
    object.__setattr__(unvalidated_row, "_authority_proof", _AUTHORITY_CHECK_PROOF)
    return unvalidated_row


def _status_for_declared_refs(
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> Literal["grounded", "unresolved", "unmeasured"]:
    if legal_refs and source_refs:
        return "grounded"
    if legal_refs or source_refs:
        return "unresolved"
    return "unmeasured"


def _legal_authority_gate(snapshot: RegistrySnapshot) -> EvidenceTierCoverageGate:
    refs = tuple(sorted(ref for ref, item in snapshot.legal.items() if item.evidence_tier == "legal_authority"))
    return EvidenceTierCoverageGate(
        tier="legal_authority",
        status=_status(refs),
        legal_refs=refs,
        detail="BOE or other binding legal references for filing-grade calculation",
    )


def _source_guidance_gate(snapshot: RegistrySnapshot) -> EvidenceTierCoverageGate:
    source_refs = _sources_for_tier(snapshot, "official_source_guidance")
    cross_refs = _cross_refs_for_tier(snapshot, "official_source_guidance")
    return EvidenceTierCoverageGate(
        tier="official_source_guidance",
        status=_status(source_refs, cross_refs),
        source_refs=source_refs,
        cross_reference_refs=cross_refs,
        detail="AEAT instructions, manuals, or static official guidance that explain model behaviour",
    )


def _executable_parity_gate(snapshot: RegistrySnapshot) -> EvidenceTierCoverageGate:
    source_refs = _sources_for_tier(snapshot, "executable_parity_evidence")
    workbook_refs = _workbook_refs_for_tier(
        snapshot,
        coverage_kinds=("formula_form",),
        tier="executable_parity_evidence",
    )
    cross_refs = _cross_refs_for_tier(snapshot, "executable_parity_evidence")
    return EvidenceTierCoverageGate(
        tier="executable_parity_evidence",
        status=_status(source_refs, workbook_refs, cross_refs),
        source_refs=source_refs,
        workbook_refs=workbook_refs,
        cross_reference_refs=cross_refs,
        detail="Safe executable parity from true formula workbooks or guarded AEAT live/help surfaces",
    )


def _layout_authority_gate(snapshot: RegistrySnapshot) -> EvidenceTierCoverageGate:
    source_refs = _sources_for_tier(snapshot, "layout_authority")
    workbook_refs = _workbook_refs_for_tier(
        snapshot,
        coverage_kinds=("record_design_layout", "unsupported_binary_xls", "static_layout"),
        tier="layout_authority",
    )
    cross_refs = _cross_refs_for_tier(snapshot, "layout_authority")
    return EvidenceTierCoverageGate(
        tier="layout_authority",
        status=_status(source_refs, workbook_refs, cross_refs),
        source_refs=source_refs,
        workbook_refs=workbook_refs,
        cross_reference_refs=cross_refs,
        detail="AEAT record designs and file-layout artefacts for import/export verification",
    )


def _sources_for_tier(snapshot: RegistrySnapshot, tier: EvidenceTier) -> tuple[SourceRefId, ...]:
    return tuple(sorted(ref for ref, item in snapshot.sources.items() if item.evidence_tier == tier))


def _cross_refs_for_tier(snapshot: RegistrySnapshot, tier: EvidenceTier) -> tuple[CrossReferenceId, ...]:
    return tuple(sorted(ref for ref, item in snapshot.live_cross_references.items() if item.evidence_tier == tier))


def _workbook_refs_for_tier(
    snapshot: RegistrySnapshot,
    *,
    coverage_kinds: tuple[str, ...],
    tier: EvidenceTier,
) -> tuple[WorkbookParityRefId, ...]:
    return tuple(
        sorted(
            ref.id
            for ref in snapshot.workbook_parity_refs.values()
            if ref.formula_coverage in coverage_kinds and snapshot.sources[ref.workbook_source].evidence_tier == tier
        ),
    )


def _status(*values: tuple[object, ...]) -> CoverageGateStatus:
    return "satisfied" if any(values) else "gap"


def _representative_year(revision: ModeloRevision) -> int:
    selector = revision.period_selector
    if selector.years:
        return selector.years[0]
    if selector.year_from is None:
        raise RegistryValidationError(f"revision {revision.id!r} has no representative filing year")
    return selector.year_from
