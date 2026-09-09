"""Pydantic contracts for the value-independent filing export proof channels.

The public facade re-exports these contracts from ``export_proof``.  Keeping
the evidence and render-input contracts together gives their shared binding
invariants one home while leaving proof assessment and refusal taxonomy at
the application boundary.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from cadrumo.application.calculations.revision_carry_gate import revision_carry_outcome
from cadrumo.application.filing.producer_snapshot import FilingProducerSnapshot
from cadrumo.core.filing_year import FilingYear
from cadrumo.core.identity import CalculationRevisionId, ContentDigest
from cadrumo.core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.product_identity import AeatProductSoftwareIdentity
from cadrumo.core.time.utc import UtcInstant
from cadrumo.domain.calculations.registry.ids import ModeloId, RevisionId
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.filing.schema import ModeloDraft
from cadrumo.domain.submission.models import ModeloDraftStatus

FilingExportProofToken = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9._:/-]*$")]
_Token = FilingExportProofToken
_DictionaryScalar = str | Decimal | date | bool | int


class FilingExportProofCoordinate(BaseModel):
    """Non-sensitive revision/layout identity shared by both proof channels."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloId
    revision: RevisionId
    snapshot_ref: RegistrySnapshotRef
    layout_ids: tuple[_Token, ...] = ()

    @model_validator(mode="after")
    def _require_coherent_coordinate(self) -> FilingExportProofCoordinate:
        if self.modelo != self.snapshot_ref.modelo or self.revision != self.snapshot_ref.revision_id:
            raise ValueError("proof modelo and revision must match snapshot_ref")
        if len(self.layout_ids) != len(set(self.layout_ids)):
            raise ValueError("proof layout identities must be unique")
        return self


class FilingExportOfficialProbe(BaseModel):
    """One distinct official literal span checked in emitted bytes."""

    model_config = STRICT_FROZEN_CONFIG

    record_id: _Token
    field_id: _Token
    emitted_offset: NonNegativeInt
    length: int = Field(gt=0)


class FilingExportGeneratedOutput(BaseModel):
    """One generated registry fragment bound to its canonical digest."""

    model_config = STRICT_FROZEN_CONFIG

    relative_path: _Token
    sha256: ContentDigest


class FilingExportPublicProvenance(BaseModel):
    """Non-sensitive official-layout and generated-provenance identity."""

    model_config = STRICT_FROZEN_CONFIG

    official_source_ref: _Token
    official_source_sha256: ContentDigest
    design_epoch: _Token
    generation_manifest_sha256: ContentDigest
    semantic_map_sha256: ContentDigest
    render_profile_sha256: ContentDigest
    loader_semantic_sha256: ContentDigest
    generated_outputs: tuple[FilingExportGeneratedOutput, ...] = Field(min_length=1)
    probes: tuple[FilingExportOfficialProbe, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_distinct_probe_spans(self) -> FilingExportPublicProvenance:
        output_paths = tuple(output.relative_path for output in self.generated_outputs)
        if len(output_paths) != len(set(output_paths)):
            raise ValueError("generated output paths must be unique")
        identities = tuple((probe.record_id, probe.field_id) for probe in self.probes)
        if len(identities) != len(set(identities)):
            raise ValueError("official probes must identify distinct fields")
        positions: set[int] = set()
        for probe in self.probes:
            span = set(range(probe.emitted_offset, probe.emitted_offset + probe.length))
            if positions.intersection(span):
                raise ValueError("official probes must cover distinct emitted byte positions")
            positions.update(span)
        return self


class FilingExportDictionaryValue(BaseModel):
    """Strict typed dictionary input for XML-dictionary export layouts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field_id: _Token
    value: _DictionaryScalar


class FilingExportConformanceVectorEvidence(BaseModel):
    """Authority-resolved public mechanism-vector identity and provenance."""

    model_config = STRICT_FROZEN_CONFIG

    authority_id: _Token
    coordinate: FilingExportProofCoordinate
    filing_year: FilingYear
    period: Period
    mechanism_source_ref: _Token
    mechanism_source_sha256: ContentDigest
    provenance: FilingExportPublicProvenance

    @model_validator(mode="after")
    def _require_selected_layout_for_success(self) -> FilingExportConformanceVectorEvidence:
        if not self.coordinate.layout_ids:
            raise ValueError("conformance vector evidence requires one selected filing layout")
        return self


class FilingExportConformanceRenderInputs(BaseModel):
    """Transient render inputs materialised by the canonical vector builder."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    coordinate: FilingExportProofCoordinate
    filing_year: FilingYear
    period: Period
    draft: ModeloDraft
    producer_snapshot: FilingProducerSnapshot
    dictionary_values: tuple[FilingExportDictionaryValue, ...] = ()
    prior_domiciliation_election: PriorDomiciliationElection | None = None
    product_software_identity: AeatProductSoftwareIdentity | None = None

    @model_validator(mode="after")
    def _bind_vector_to_coordinate(self) -> FilingExportConformanceRenderInputs:
        _require_export_inputs_match(
            self.coordinate,
            self.draft,
            self.producer_snapshot,
            filing_year=self.filing_year,
            period=self.period,
        )
        _require_unique_dictionary_fields(self.dictionary_values)
        return self


class FilingExportConformanceReceipt(BaseModel):
    """Secret-free value-independent mechanism-conformance receipt."""

    model_config = STRICT_FROZEN_CONFIG

    coordinate: FilingExportProofCoordinate
    provenance: FilingExportPublicProvenance
    authority_id: _Token
    canonical_writer: Literal["cadrumo.application.filing.export_draft"] = "cadrumo.application.filing.export_draft"
    emitted_bytes: int = Field(gt=0)
    checked_official_offsets: int = Field(gt=0)
    taxpayer_truth_claimed: Literal[False] = False
    source_owned_replay_claimed: Literal[False] = False
    accepted_payload_hash_claimed: Literal[False] = False

    @model_validator(mode="after")
    def _require_probe_count(self) -> FilingExportConformanceReceipt:
        if self.checked_official_offsets != len(self.provenance.probes):
            raise ValueError("checked official-offset count must equal the distinct declared probes")
        return self


class FilingExportSourcePinnedProbeExpectation(BaseModel):
    """Source-owned expected bytes for one official replay probe span."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    probe: FilingExportOfficialProbe
    expected_bytes: bytes = Field(min_length=1)

    @model_validator(mode="after")
    def _require_exact_probe_extent(self) -> FilingExportSourcePinnedProbeExpectation:
        if len(self.expected_bytes) != self.probe.length:
            raise ValueError("source-pinned expected bytes must exactly fill the declared probe span")
        return self


class FilingExportSecureReplayEvidence(BaseModel):
    """Secret-bearing source-owned replay evidence, never a public receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    evidence_id: _Token
    coordinate: FilingExportProofCoordinate
    source_authority_id: _Token
    calculation_revision_id: CalculationRevisionId
    approved_calculation_revision: Literal[True]
    source_owned_draft: Literal[True]
    draft: ModeloDraft
    producer_snapshot: FilingProducerSnapshot
    provenance: FilingExportPublicProvenance
    source_pinned_probe_expectations: tuple[FilingExportSourcePinnedProbeExpectation, ...] = Field(min_length=1)
    dictionary_values: tuple[FilingExportDictionaryValue, ...] = ()
    prior_domiciliation_election: PriorDomiciliationElection | None = None
    product_software_identity: AeatProductSoftwareIdentity | None = None

    @model_validator(mode="after")
    def _bind_source_owned_inputs(self) -> FilingExportSecureReplayEvidence:
        _require_export_inputs_match(
            self.coordinate,
            self.draft,
            self.producer_snapshot,
            filing_year=self.draft.period.filing_year,
            period=self.draft.period,
        )
        _require_unique_dictionary_fields(self.dictionary_values)
        expected_probes = tuple(expectation.probe for expectation in self.source_pinned_probe_expectations)
        if expected_probes != self.provenance.probes:
            raise ValueError("source-owned replay expectations must exactly cover the declared provenance probes")
        return self


class FilingExportSecureCustodyRecord(BaseModel):
    """Secret-bearing encrypted custody record returned inside the service."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    receipt_id: UUID
    coordinate: FilingExportProofCoordinate
    source_authority_id: _Token
    custody_authority_id: _Token
    evidence_id: _Token
    calculation_revision_id: CalculationRevisionId
    draft_id: str = Field(min_length=1, max_length=128)
    payload_sha256: ContentDigest
    emitted_bytes: int = Field(gt=0)
    attested_at: UtcInstant
    valid_until: UtcInstant
    encrypted_at_rest: Literal[True]
    approved_calculation_revision: Literal[True]
    source_owned_draft: Literal[True]
    matching_producer_snapshot: Literal[True]
    value_arrival: Literal[True]
    applicability: Literal[True]
    repeated_record_order: Literal[True]
    emitted_extent: Literal[True]
    source_pinned_probes_passed: Literal[True]

    @model_validator(mode="after")
    def _require_forward_validity_window(self) -> FilingExportSecureCustodyRecord:
        if self.valid_until <= self.attested_at:
            raise ValueError("secure replay validity must end after attestation")
        return self


class FilingExportSecureReplayReceipt(BaseModel):
    """Public replay attestation with no values, path, digest, or byte extent."""

    model_config = STRICT_FROZEN_CONFIG

    receipt_id: UUID
    coordinate: FilingExportProofCoordinate
    provenance: FilingExportPublicProvenance
    source_authority_id: _Token
    custody_authority_id: _Token
    canonical_writer: Literal["cadrumo.application.filing.export_draft"] = "cadrumo.application.filing.export_draft"
    proof_schema_version: Literal["filing-export-secure-replay-v1"] = "filing-export-secure-replay-v1"
    attested_at: UtcInstant
    valid_until: UtcInstant
    replay_passed: Literal[True] = True
    approved_calculation_revision: Literal[True] = True
    source_owned_draft: Literal[True] = True
    matching_producer_snapshot: Literal[True] = True
    value_arrival: Literal[True] = True
    applicability: Literal[True] = True
    repeated_record_order: Literal[True] = True
    emitted_extent: Literal[True] = True
    source_pinned_probes: Literal[True] = True
    taxpayer_values_exposed: Literal[False] = False
    payload_digest_exposed: Literal[False] = False
    accepted_payload_hash_claimed: Literal[False] = False

    @model_validator(mode="after")
    def _require_forward_validity_window(self) -> FilingExportSecureReplayReceipt:
        if self.valid_until <= self.attested_at:
            raise ValueError("secure replay receipt validity must end after attestation")
        return self


class FilingExportProof(BaseModel):
    """Complete two-channel proof for one dynamically selected revision."""

    model_config = STRICT_FROZEN_CONFIG

    coordinate: FilingExportProofCoordinate
    conformance: FilingExportConformanceReceipt
    secure_replay: FilingExportSecureReplayReceipt

    @model_validator(mode="after")
    def _require_one_coordinate_and_provenance(self) -> FilingExportProof:
        if self.conformance.coordinate != self.coordinate or self.secure_replay.coordinate != self.coordinate:
            raise ValueError("both filing export proof channels must identify the assessed coordinate")
        if self.conformance.provenance != self.secure_replay.provenance:
            raise ValueError("both filing export proof channels must identify the same public provenance")
        return self


def _require_export_inputs_match(
    coordinate: FilingExportProofCoordinate,
    draft: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
    *,
    filing_year: int,
    period: Period,
) -> None:
    if draft.snapshot_ref != coordinate.snapshot_ref:
        raise ValueError("proof draft registry coordinate must match the requested coordinate")
    outcome = revision_carry_outcome(coordinate.snapshot_ref)
    if outcome.refused:
        raise ValueError(f"proof registry coordinate cannot be re-confirmed: {outcome.detail}")
    if draft.status is not ModeloDraftStatus.APROBADO:
        raise ValueError("proof draft must be approved")
    if (
        draft.modelo != coordinate.modelo
        or draft.period != period
        or draft.period.filing_year != filing_year
        or producer_snapshot.modelo.value != coordinate.modelo
    ):
        raise ValueError("proof draft and producer snapshot must match the requested coordinate")


def _require_unique_dictionary_fields(values: tuple[FilingExportDictionaryValue, ...]) -> None:
    field_ids = tuple(item.field_id for item in values)
    if len(field_ids) != len(set(field_ids)):
        raise ValueError("proof dictionary field identities must be unique")


__all__ = [
    "FilingExportConformanceReceipt",
    "FilingExportConformanceRenderInputs",
    "FilingExportConformanceVectorEvidence",
    "FilingExportDictionaryValue",
    "FilingExportGeneratedOutput",
    "FilingExportOfficialProbe",
    "FilingExportProof",
    "FilingExportProofCoordinate",
    "FilingExportProofToken",
    "FilingExportPublicProvenance",
    "FilingExportSecureCustodyRecord",
    "FilingExportSecureReplayEvidence",
    "FilingExportSecureReplayReceipt",
    "FilingExportSourcePinnedProbeExpectation",
]
