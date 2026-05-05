"""Coverage ledger for registry authority and verification tiers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ._schema import EvidenceTier, RegistrySnapshot

CoverageGateStatus = Literal["satisfied", "gap"]


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
        """Return evidence tiers that have no supporting registry evidence."""

        return tuple(gate for gate in self.gates if gate.status == "gap")


def build_model_law_coverage_ledger(snapshot: RegistrySnapshot) -> ModelLawCoverageLedger:
    """Build the four-tier coverage ledger for a validated registry snapshot."""

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
    workbook_refs = tuple(
        sorted(ref.id for ref in snapshot.workbook_parity_refs.values() if ref.formula_coverage == "formula_form")
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
    workbook_refs = tuple(
        sorted(
            ref.id
            for ref in snapshot.workbook_parity_refs.values()
            if ref.formula_coverage in {"record_design_layout", "unsupported_binary_xls", "static_layout"}
        )
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


def _status(*values: tuple[str, ...]) -> CoverageGateStatus:
    return "satisfied" if any(values) else "gap"
