"""Live filing-export proof over canonical generation and production bytes.

This development authority is intentionally not a serialisable catalogue of
success claims.  An entry only supplies the filing inputs and the acceptance
values that an independent emitted-byte review recorded.  Every lookup reopens
the canonical authored sources, drives the generator's verifier, executes the
production filing writer, and compares the resulting bytes before it returns a
proof to the application closure composer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cadrumo.application.filing import (
    FilingExportConformanceReceipt,
    FilingExportConformanceRenderInputs,
    FilingExportConformanceRequest,
    FilingExportConformanceVectorEvidence,
    FilingExportProofAssessment,
    FilingExportProofChannel,
    FilingExportProofCoordinate,
    FilingExportProofRefusal,
    FilingExportProofRefusalReason,
    FilingExportPublicProvenance,
    FilingExportSecureReplayCustody,
    FilingExportSecureReplayReceipt,
    FilingExportSecureReplayRequest,
    FilingExportSecureReplaySourceAuthority,
    FilingProducerSnapshot,
    build_runtime_schema_provider,
    prove_export_conformance,
    prove_secure_export_replay,
)
from cadrumo.application.filing import (
    FilingExportProof as TwoChannelFilingExportProof,
)
from cadrumo.application.registry import (
    FilingExportProof,
    FilingExportProofConflictError,
)
from cadrumo.core import (
    AeatProductSoftwareIdentity,
    Period,
    PriorDomiciliationElection,
    RegistryAuthorityGrade,
    sha256_hex,
)
from cadrumo.core.time import now
from cadrumo.domain.calculations.registry import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ModeloId,
    RegistryRevisionInspection,
    RegistryValidationError,
    RevisionId,
    ValidatedRegistryAuthority,
    render_fixed_width_export_field,
)
from cadrumo.domain.filing import FilingExportError, ModeloDraft

from .pipeline._provenance_manifest import (
    ExportFragmentTarget,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    verify_export_fragment_provenance_manifest,
)
from .pipeline._record_design_ir import load_record_design_intermediate
from .pipeline._render_profile import (
    RenderProfileSourceEvidence,
    load_render_profile,
    load_render_profile_source_evidence,
)
from .pipeline._semantic_map_join import join_record_design_semantics
from .pipeline._semantic_map_loader import load_semantic_map

__all__ = [
    "CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS",
    "CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES",
    "CanonicalTwoChannelFilingExportProofAuthority",
    "FilingExportConformanceVector",
    "FilingExportConformanceVectorBuilder",
    "FilingExportLiveProofEntry",
    "FilingExportOfficialOffsetProbe",
    "LiveFilingExportProofAuthority",
    "canonical_live_filing_export_proof_authority",
    "canonical_two_channel_filing_export_proof_authority",
    "verify_filing_export_payload_acceptance",
]

_CONFORMANCE_AUTHORITY_ID = "dev.registry.filing-export-conformance"


@dataclass(frozen=True, slots=True)
class FilingExportOfficialOffsetProbe:
    """One generator-grounded literal field checked in production output."""

    record_id: str
    field_id: str


@dataclass(frozen=True, slots=True)
class FilingExportLiveProofEntry:
    """Inputs and independently recorded acceptance values for one revision."""

    modelo: ModeloId
    revision: RevisionId
    design_epoch: str
    filing_year: int
    period: Period
    draft: ModeloDraft
    producer_snapshot: FilingProducerSnapshot
    expected_payload_sha256: str
    expected_emitted_bytes: int
    official_offset_probes: tuple[FilingExportOfficialOffsetProbe, ...]
    prior_domiciliation_election: PriorDomiciliationElection | None = None
    product_software_identity: AeatProductSoftwareIdentity | None = None
    dictionary_values: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        """Refuse internally inconsistent or structurally empty acceptance input."""
        if self.period.filing_year != self.filing_year:
            raise ValueError("filing export live proof period must belong to its filing year")
        if self.draft.modelo != self.modelo or self.draft.period != self.period:
            raise ValueError("filing export live proof draft identity must match its coordinate")
        if self.producer_snapshot.modelo.value != self.modelo:
            raise ValueError("filing export live proof producer modelo must match its coordinate")
        if len(self.expected_payload_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.expected_payload_sha256
        ):
            raise ValueError("filing export live proof expected payload digest must be lowercase SHA-256")
        if self.expected_emitted_bytes <= 0:
            raise ValueError("filing export live proof expected byte extent must be positive")
        if not self.official_offset_probes:
            raise ValueError("filing export live proof requires at least one official-offset probe")
        probe_identities = tuple((probe.record_id, probe.field_id) for probe in self.official_offset_probes)
        if len(probe_identities) != len(set(probe_identities)):
            raise ValueError("filing export live proof official-offset probes must identify distinct fields")


# Live filing proof is enrolled only after a revision has independently reviewed
# generation inputs and emitted bytes.  An empty tuple is an honest authority
# with no successful entries; it is not permission to infer proof from layouts.
CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES: tuple[FilingExportLiveProofEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class FilingExportConformanceVector:
    """One explicitly public mechanism vector; never taxpayer truth."""

    evidence: FilingExportConformanceVectorEvidence
    builder: FilingExportConformanceVectorBuilder


class FilingExportConformanceVectorBuilder(Protocol):
    """Materialise transient canonical-writer inputs from public vector source."""

    def build(
        self,
        evidence: FilingExportConformanceVectorEvidence,
    ) -> FilingExportConformanceRenderInputs:
        """Return source-derived inputs without storing taxpayer values in the vector."""


# S85 owns dynamic enrollment.  Empty inputs are deliberate and yield typed
# per-channel refusals; they are never treated as a waiver or proof.
CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS: tuple[FilingExportConformanceVector, ...] = ()


class CanonicalTwoChannelFilingExportProofAuthority:
    """Require current public conformance and operator-custodied replay."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        registry_root: Path,
        source_root: Path,
        authority: ValidatedRegistryAuthority,
        vectors: tuple[FilingExportConformanceVector, ...],
        secure_replay_source: FilingExportSecureReplaySourceAuthority | None,
        secure_replay_custody: FilingExportSecureReplayCustody | None,
    ) -> None:
        """Bind canonical source roots and unique inputs for both channels."""
        self._workspace_root = workspace_root.resolve()
        self._registry_root = registry_root.resolve()
        self._source_root = source_root.resolve()
        self._authority = authority
        self._vectors = vectors
        self._secure_replay_source = secure_replay_source
        self._secure_replay_custody = secure_replay_custody
        _require_unique_coordinates(tuple(item.evidence.coordinate for item in vectors), channel="conformance")

    @property
    def authority_id(self) -> str:
        """Return the canonical public conformance authority identity."""
        return _CONFORMANCE_AUTHORITY_ID

    def resolve_conformance_vector(
        self,
        request: FilingExportConformanceRequest,
    ) -> FilingExportConformanceVectorEvidence | None:
        """Resolve only a canonical S85-enrolled mechanism vector."""
        vector = next((item for item in self._vectors if item.evidence.coordinate == request.coordinate), None)
        return None if vector is None else vector.evidence

    def schema_provider_for_conformance(
        self,
        evidence: FilingExportConformanceVectorEvidence,
    ):
        """Build the canonical law-selection provider for one public vector."""
        return build_runtime_schema_provider(
            self._registry_root,
            source_root=self._source_root,
            filing_year=evidence.filing_year,
            period=evidence.period,
            modelos=(str(evidence.coordinate.modelo),),
        )

    def materialize_conformance_inputs(
        self,
        evidence: FilingExportConformanceVectorEvidence,
    ) -> FilingExportConformanceRenderInputs:
        """Delegate only to the builder enrolled beside the canonical vector."""
        vector = next((item for item in self._vectors if item.evidence == evidence), None)
        if vector is None:
            raise RegistryValidationError("conformance vector builder is not canonically enrolled")
        return vector.builder.build(evidence)

    def assess_for(self, coordinate: FilingExportProofCoordinate) -> FilingExportProofAssessment:
        """Return a complete proof or exact missing/conflicting channel refusals."""
        refusals: list[FilingExportProofRefusal] = []
        conformance: FilingExportConformanceReceipt | None = None
        if self.resolve_conformance_vector(FilingExportConformanceRequest(coordinate=coordinate)) is None:
            refusals.append(self._refusal(coordinate, FilingExportProofChannel.CONFORMANCE))
        else:
            try:
                conformance = prove_export_conformance(
                    FilingExportConformanceRequest(coordinate=coordinate),
                    authority=self,
                )
            except (FilingExportError, OSError, RegistryValidationError, ValueError):
                refusals.append(
                    self._refusal(
                        coordinate,
                        FilingExportProofChannel.CONFORMANCE,
                        FilingExportProofRefusalReason.PROOF_VALIDATION_FAILED,
                    ),
                )

        replay: FilingExportSecureReplayReceipt | None = None
        if self._secure_replay_source is None or self._secure_replay_custody is None:
            refusals.append(
                self._refusal(
                    coordinate,
                    FilingExportProofChannel.SECURE_REPLAY,
                    FilingExportProofRefusalReason.AUTHORITY_UNAVAILABLE,
                ),
            )
        else:
            try:
                replay = prove_secure_export_replay(
                    FilingExportSecureReplayRequest(
                        coordinate=coordinate,
                        source_authority_id=self._secure_replay_source.authority_id,
                        custody_authority_id=self._secure_replay_custody.authority_id,
                    ),
                    source_authority=self._secure_replay_source,
                    custody=self._secure_replay_custody,
                )
            except (FilingExportError, OSError, RegistryValidationError, ValueError):
                refusals.append(
                    self._refusal(
                        coordinate,
                        FilingExportProofChannel.SECURE_REPLAY,
                        FilingExportProofRefusalReason.CUSTODY_FAILED,
                    ),
                )
        if replay is not None and not replay.attested_at <= now() < replay.valid_until:
            refusals.append(
                self._refusal(
                    coordinate,
                    FilingExportProofChannel.SECURE_REPLAY,
                    FilingExportProofRefusalReason.PROOF_VALIDATION_FAILED,
                ),
            )
        elif replay is not None and conformance is not None and replay.provenance != conformance.provenance:
            refusals.append(
                self._refusal(
                    coordinate,
                    FilingExportProofChannel.SECURE_REPLAY,
                    FilingExportProofRefusalReason.PROVENANCE_MISMATCH,
                ),
            )

        if refusals:
            return FilingExportProofAssessment(coordinate=coordinate, refusals=tuple(refusals))
        if conformance is None or replay is None:
            raise AssertionError("two-channel export proof reached an impossible incomplete state")
        return FilingExportProofAssessment(
            coordinate=coordinate,
            proof=TwoChannelFilingExportProof(
                coordinate=coordinate,
                conformance=conformance,
                secure_replay=replay,
            ),
        )

    def verify_conformance(self, *, request, evidence, export_result, payload) -> FilingExportConformanceReceipt:
        """Reopen all public authorities and check official literal byte spans."""
        coordinate = request.coordinate
        snapshot = self._authority.snapshot(
            coordinate.modelo,
            filing_year=evidence.filing_year,
            period=evidence.period.registry_token,
            grade=RegistryAuthorityGrade.FILING,
        )
        layout_ids = tuple(layout.id for layout in snapshot.revision.export_layouts)
        if snapshot.revision.id != coordinate.revision or layout_ids != coordinate.layout_ids:
            raise RegistryValidationError("conformance vector conflicts with the law-selected revision or layouts")
        if len(snapshot.revision.export_layouts) != 1:
            raise RegistryValidationError("conformance proof requires exactly one generated filing layout")
        layout = snapshot.revision.export_layouts[0]
        generation_entry = _ConformanceGenerationEntry(
            modelo=coordinate.modelo,
            revision=coordinate.revision,
            design_epoch=evidence.provenance.design_epoch,
            filing_year=evidence.filing_year,
        )
        verifier = LiveFilingExportProofAuthority(
            workspace_root=self._workspace_root,
            registry_root=self._registry_root,
            source_root=self._source_root,
            authority=self._authority,
            entries=(),
        )
        manifest, manifest_path = verifier._verify_generation(entry=generation_entry, layout=layout)
        actual_provenance = FilingExportPublicProvenance(
            official_source_ref=manifest.source_ref,
            official_source_sha256=manifest.source_sha256,
            design_epoch=manifest.design_epoch,
            generation_manifest_sha256=sha256_hex(manifest_path.read_bytes()),
            semantic_map_sha256=manifest.semantic_map_sha256,
            render_profile_sha256=manifest.render_profile_sha256,
            loader_semantic_sha256=manifest.loader_semantic_sha256,
            generated_outputs=tuple(
                {
                    "relative_path": item.relative_path,
                    "sha256": item.sha256,
                }
                for item in manifest.output_files
            ),
            probes=evidence.provenance.probes,
        )
        if actual_provenance != evidence.provenance:
            raise RegistryValidationError("conformance vector provenance is stale or conflicts with canonical sources")
        _verify_public_vector_probes(layout=layout, payload=payload, provenance=actual_provenance)
        if export_result.byte_size != len(payload):
            raise RegistryValidationError("canonical conformance writer extent conflicts with emitted bytes")
        return FilingExportConformanceReceipt(
            coordinate=coordinate,
            provenance=actual_provenance,
            authority_id=_CONFORMANCE_AUTHORITY_ID,
            emitted_bytes=len(payload),
            checked_official_offsets=len(actual_provenance.probes),
        )

    @staticmethod
    def _refusal(
        coordinate: FilingExportProofCoordinate,
        channel: FilingExportProofChannel,
        reason: FilingExportProofRefusalReason = FilingExportProofRefusalReason.EVIDENCE_MISSING,
    ) -> FilingExportProofRefusal:
        return FilingExportProofRefusal(
            coordinate=coordinate,
            channel=channel,
            reason=reason,
            authority_id=_CONFORMANCE_AUTHORITY_ID if channel is FilingExportProofChannel.CONFORMANCE else None,
        )


@dataclass(frozen=True, slots=True)
class _ConformanceGenerationEntry:
    modelo: ModeloId
    revision: RevisionId
    design_epoch: str
    filing_year: int


def _require_unique_coordinates(coordinates: tuple[FilingExportProofCoordinate, ...], *, channel: str) -> None:
    if len(coordinates) != len(set(coordinates)):
        raise ValueError(f"filing export {channel} proof coordinates must be unique")


class LiveFilingExportProofAuthority:
    """Recompute generator and production-writer evidence on every lookup."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        registry_root: Path,
        source_root: Path,
        authority: ValidatedRegistryAuthority,
        entries: tuple[FilingExportLiveProofEntry, ...],
    ) -> None:
        """Bind canonical roots, validated authority, and unique proof entries."""
        coordinates = tuple((entry.modelo, entry.revision) for entry in entries)
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("filing export live proof coordinates must be unique")
        self._workspace_root = workspace_root.resolve()
        self._registry_root = registry_root.resolve()
        self._source_root = source_root.resolve()
        self._authority = authority
        self._entries = entries

    def proof_for(
        self,
        *,
        modelo: ModeloId,
        revision: RevisionId,
        layout_ids: tuple[str, ...],
    ) -> FilingExportProof | None:
        """Return proof only after live canonical generation and export checks."""
        entry = next(
            (candidate for candidate in self._entries if candidate.modelo == modelo and candidate.revision == revision),
            None,
        )
        if entry is None:
            return None
        raise FilingExportProofConflictError(
            "legacy single-channel filing proof is disabled; two-channel source and custody authorities are required",
        )

    def _verify_generation(
        self,
        *,
        entry: FilingExportLiveProofEntry,
        layout: ExportLayoutDefinition,
    ):
        export_root = (
            self._workspace_root
            / "src/cadrumo/_data/registry/aeat/modelos"
            / str(entry.modelo)
            / "revisions"
            / str(entry.revision)
            / "export"
        )
        manifest_path = export_root / "_generation.provenance.json"
        manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
        if (
            manifest.modelo != entry.modelo
            or manifest.revision_id != entry.revision
            or manifest.design_epoch != entry.design_epoch
        ):
            raise RegistryValidationError("canonical export manifest identity conflicts with the live proof entry")
        semantic_map = load_semantic_map(
            self._workspace_root / "dev/registry/mappings" / f"modelo_{entry.modelo}" / entry.design_epoch,
        )
        render_profile = load_render_profile(
            self._workspace_root / "dev/registry/render_profiles" / f"modelo_{entry.modelo}" / entry.design_epoch,
        )
        modelo = self._authority.modelo(entry.modelo)
        inspection = RegistryRevisionInspection.from_revision(
            modelo=modelo,
            revision=modelo.revisions[entry.revision],
            source_root=self._source_root,
            sources=self._authority.catalogues.sources,
            legal_ref_ids=frozenset(self._authority.catalogues.legal),
        )
        intermediate = load_record_design_intermediate(
            self._source_root,
            self._authority.catalogues.sources,
            source_ref=manifest.source_ref,
            filing_year=entry.filing_year,
            design_epoch=entry.design_epoch,
        )
        joined = join_record_design_semantics(semantic_map, intermediate, inspection)
        claims_official = any(
            rule.evidence.authority_kind != "reviewed_policy"
            for rule in (*render_profile.singleton_rules, *render_profile.width_17_rules)
        )
        source_evidence = (
            load_render_profile_source_evidence(
                self._source_root / self._authority.catalogues.sources[manifest.source_ref].corpus_path,
                render_profile,
            )
            if claims_official
            else RenderProfileSourceEvidence(design_identity=render_profile.design_identity, entries=())
        )
        verified = verify_export_fragment_provenance_manifest(
            export_root=export_root,
            joined=joined,
            semantic_map=semantic_map,
            target=ExportFragmentTarget(
                modelo=entry.modelo,
                revision_id=entry.revision,
                design_epoch=entry.design_epoch,
            ),
            loaded_layout=layout,
            field_derivations=manifest.field_derivations,
            render_profile=render_profile,
            render_profile_source_evidence=source_evidence,
        )
        if export_fragment_provenance_manifest_json_bytes(verified) != manifest_path.read_bytes():
            raise RegistryValidationError("canonical export manifest bytes changed during live verification")
        return verified, manifest_path

def canonical_live_filing_export_proof_authority(
    *,
    workspace_root: Path,
    registry_root: Path,
    source_root: Path,
    authority: ValidatedRegistryAuthority,
) -> LiveFilingExportProofAuthority:
    """Bind the canonical live verifier to the currently enrolled proof entries."""
    return LiveFilingExportProofAuthority(
        workspace_root=workspace_root,
        registry_root=registry_root,
        source_root=source_root,
        authority=authority,
        entries=CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES,
    )


def canonical_two_channel_filing_export_proof_authority(
    *,
    workspace_root: Path,
    registry_root: Path,
    source_root: Path,
    authority: ValidatedRegistryAuthority,
    secure_replay_source: FilingExportSecureReplaySourceAuthority | None,
    secure_replay_custody: FilingExportSecureReplayCustody | None,
) -> CanonicalTwoChannelFilingExportProofAuthority:
    """Bind canonical public vectors and operator-supplied secure attestations."""
    return CanonicalTwoChannelFilingExportProofAuthority(
        workspace_root=workspace_root,
        registry_root=registry_root,
        source_root=source_root,
        authority=authority,
        vectors=CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS,
        secure_replay_source=secure_replay_source,
        secure_replay_custody=secure_replay_custody,
    )


def _verify_public_vector_probes(
    *,
    layout: ExportLayoutDefinition,
    payload: bytes,
    provenance: FilingExportPublicProvenance,
) -> None:
    ordered = tuple(sorted(layout.records, key=lambda record: record.order))
    first = ordered[0]
    prefix_extent = layout.filing_envelope.prefix_extent if layout.filing_envelope is not None else 0
    for probe in provenance.probes:
        if probe.record_id != str(first.id) or not first.required or first.repeat is not None:
            raise RegistryValidationError(
                "official conformance probe must target the first required non-repeating record",
            )
        field = next((item for item in first.fields if str(item.id) == probe.field_id), None)
        if field is None or field.offset is None or field.length is None or field.literal is None:
            raise RegistryValidationError("official conformance probe must target a positioned literal field")
        expected_offset = prefix_extent + field.offset - 1
        if probe.emitted_offset != expected_offset or probe.length != field.length:
            raise RegistryValidationError("official conformance probe span conflicts with the selected layout")
        expected = _literal_bytes(field, encoding=first.encoding)
        if payload[probe.emitted_offset : probe.emitted_offset + probe.length] != expected:
            raise RegistryValidationError(
                f"conformance payload disagrees at official field {probe.record_id!r}/{probe.field_id!r}",
            )


def verify_filing_export_payload_acceptance(
    *,
    entry: FilingExportLiveProofEntry,
    layout: ExportLayoutDefinition,
    payload: bytes,
) -> None:
    """Re-hash emitted bytes and check generator-grounded official positions."""
    if sha256_hex(payload) != entry.expected_payload_sha256:
        raise RegistryValidationError("live export payload digest does not match acceptance evidence")
    if len(payload) != entry.expected_emitted_bytes:
        raise RegistryValidationError("live export payload extent does not match acceptance evidence")
    ordered = tuple(sorted(layout.records, key=lambda record: record.order))
    first = ordered[0]
    prefix_extent = layout.filing_envelope.prefix_extent if layout.filing_envelope is not None else 0
    checked_positions: set[int] = set()
    for probe in entry.official_offset_probes:
        if probe.record_id != str(first.id) or not first.required or first.repeat is not None:
            raise RegistryValidationError(
                "official-offset probe must target the first required non-repeating record",
            )
        field = next((item for item in first.fields if str(item.id) == probe.field_id), None)
        if field is None or field.offset is None or field.length is None or field.literal is None:
            raise RegistryValidationError("official-offset probe must target a positioned literal field")
        expected = _literal_bytes(field, encoding=first.encoding)
        start = prefix_extent + field.offset - 1
        field_positions = set(range(start, start + field.length))
        if checked_positions.intersection(field_positions):
            raise RegistryValidationError("official-offset probes must target distinct emitted byte positions")
        checked_positions.update(field_positions)
        if payload[start : start + field.length] != expected:
            raise RegistryValidationError(
                f"production export payload disagrees at official field {probe.record_id!r}/{probe.field_id!r}",
            )


def _literal_bytes(field: ExportFieldDefinition, *, encoding: str) -> bytes:
    rendered = render_fixed_width_export_field(field, field.literal)
    return rendered.encode(encoding)
