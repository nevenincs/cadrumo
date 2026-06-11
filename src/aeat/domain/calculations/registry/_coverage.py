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

from pydantic import BaseModel, ConfigDict

from ._errors import RegistryValidationError
from ._schema import EvidenceTier, ModeloDefinition, ModeloRevision, RegistryCatalogues, RegistrySnapshot
from ._snapshot import _build_validated_snapshot
from ._validate import RegistryValidator

CoverageGateStatus = Literal["satisfied", "gap"]
RequiredCoverageTier = Literal["legal_authority", "official_source_guidance", "layout_authority"]

_REQUIRED_COVERAGE_TIERS: tuple[RequiredCoverageTier, ...] = (
    "legal_authority",
    "official_source_guidance",
    "layout_authority",
)


class CoverageModel(BaseModel):
    """Strict frozen base for coverage reports."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class EvidenceTierCoverageGate(CoverageModel):
    """Coverage state for one evidence tier."""

    tier: EvidenceTier
    status: CoverageGateStatus
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    workbook_refs: tuple[str, ...] = ()
    cross_reference_refs: tuple[str, ...] = ()
    detail: str


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
            snapshot = _build_validated_snapshot(
                modelo,
                catalogues,
                filing_year=_representative_year(revision),
                period=revision.period_selector.periods[0],
                revision_id=revision.id,
            )
            ledger = build_model_law_coverage_ledger(snapshot)
            ledgers.append(ledger)
            gates = {gate.tier: gate for gate in ledger.gates}
            for tier in _REQUIRED_COVERAGE_TIERS:
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


def _sources_for_tier(snapshot: RegistrySnapshot, tier: EvidenceTier) -> tuple[str, ...]:
    return tuple(sorted(ref for ref, item in snapshot.sources.items() if item.evidence_tier == tier))


def _cross_refs_for_tier(snapshot: RegistrySnapshot, tier: EvidenceTier) -> tuple[str, ...]:
    return tuple(sorted(ref for ref, item in snapshot.live_cross_references.items() if item.evidence_tier == tier))


def _workbook_refs_for_tier(
    snapshot: RegistrySnapshot,
    *,
    coverage_kinds: tuple[str, ...],
    tier: EvidenceTier,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            ref.id
            for ref in snapshot.workbook_parity_refs.values()
            if ref.formula_coverage in coverage_kinds and snapshot.sources[ref.workbook_source].evidence_tier == tier
        ),
    )


def _status(*values: tuple[str, ...]) -> CoverageGateStatus:
    return "satisfied" if any(values) else "gap"


def _representative_year(revision: ModeloRevision) -> int:
    selector = revision.period_selector
    if selector.years:
        return selector.years[0]
    if selector.year_from is None:
        raise RegistryValidationError(f"revision {revision.id!r} has no representative filing year")
    return selector.year_from
