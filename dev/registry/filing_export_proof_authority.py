"""Coordinate the public conformance and secure replay proof channels."""

from __future__ import annotations

from pathlib import Path

from cadrumo.adapters.persistence.storage.errors import PersistenceError
from cadrumo.application.filing.runtime import (
    schema_provider_from_authority,
)
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection
from cadrumo.domain.filing.errors import FilingExportError

from .export_proof import (
    FilingExportProofAssessment,
    FilingExportProofChannel,
    FilingExportProofRefusal,
    FilingExportProofRefusalReason,
)
from .filing_export_conformance import (
    _CONFORMANCE_AUTHORITY_ID,
    FilingExportConformanceRequest,
    prove_export_conformance,
)
from .filing_export_conformance_enrollment import (
    FilingExportConformanceEnrollmentReport,
    derive_filing_export_conformance_enrollment,
)
from .filing_export_conformance_vectors import (
    FilingExportConformanceVector,
    canonical_filing_export_conformance_vectors,
)
from .filing_export_generated_verification import _ConformanceGenerationEntry, _verify_generated_revision
from .filing_export_payload_acceptance import _literal_bytes
from .filing_export_proof_contracts import (
    FilingExportConformanceReceipt,
    FilingExportConformanceRenderInputs,
    FilingExportConformanceVectorEvidence,
    FilingExportOfficialProbe,
    FilingExportProof,
    FilingExportProofCoordinate,
    FilingExportPublicProvenance,
    FilingExportSecureReplayReceipt,
)
from .filing_export_secure_replay import (
    FilingExportSecureReplayCustody,
    FilingExportSecureReplayRequest,
    FilingExportSecureReplaySourceAuthority,
    prove_secure_export_replay,
)


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
        conformance_enrollment: FilingExportConformanceEnrollmentReport,
        secure_replay_source: FilingExportSecureReplaySourceAuthority | None,
        secure_replay_custody: FilingExportSecureReplayCustody | None,
    ) -> None:
        """Bind canonical source roots and unique inputs for both channels."""
        self._workspace_root = workspace_root.resolve()
        self._registry_root = registry_root.resolve()
        self._source_root = source_root.resolve()
        self._authority = authority
        self._vectors = vectors
        self._conformance_enrollment = conformance_enrollment
        self._secure_replay_source = secure_replay_source
        self._secure_replay_custody = secure_replay_custody
        _require_unique_coordinates(tuple(item.evidence.coordinate for item in vectors), channel="conformance")

    @property
    def authority_id(self) -> str:
        """Return the canonical public conformance authority identity."""
        return _CONFORMANCE_AUTHORITY_ID

    @property
    def conformance_enrollment(self) -> FilingExportConformanceEnrollmentReport:
        """Expose the current success candidates and explicit non-success residue."""
        return self._conformance_enrollment

    def resolve_conformance_vector(
        self,
        request: FilingExportConformanceRequest,
    ) -> FilingExportConformanceVectorEvidence | None:
        """Resolve only a canonically enrolled mechanism vector."""
        vector = next((item for item in self._vectors if item.evidence.coordinate == request.coordinate), None)
        return None if vector is None else vector.evidence

    def schema_provider_for_conformance(
        self,
        evidence: FilingExportConformanceVectorEvidence,
    ):
        """Build the canonical law-selection provider for one public vector."""
        return schema_provider_from_authority(
            self._authority,
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

    def prove_conformance(self, request: FilingExportConformanceRequest) -> FilingExportConformanceReceipt:
        """Keep candidate facts explicit throughout materialization and canonical rendering."""
        with validating_governed_facts(self._authority):
            return prove_export_conformance(request, authority=self)

    def assess_for(self, coordinate: FilingExportProofCoordinate) -> FilingExportProofAssessment:
        """Return a complete proof or exact missing/conflicting channel refusals."""
        refusals: list[FilingExportProofRefusal] = []
        conformance = _assess_conformance_channel(self, coordinate, refusals)
        replay = _assess_secure_replay_channel(self, coordinate, refusals)
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
            proof=FilingExportProof(
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
        modelo = self._authority.modelo(generation_entry.modelo)
        inspection = RegistryRevisionInspection.from_revision(
            modelo=modelo,
            revision=modelo.revisions[generation_entry.revision],
            source_root=self._source_root,
            sources=self._authority.catalogues.sources,
            legal_ref_ids=frozenset(self._authority.catalogues.legal),
        )
        manifest, manifest_path = _verify_generated_revision(
            workspace_root=self._workspace_root,
            registry_root=self._registry_root,
            source_root=self._source_root,
            authority=self._authority,
            inspection=inspection,
            entry=generation_entry,
            layout=layout,
        )
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


def _assess_conformance_channel(
    authority: CanonicalTwoChannelFilingExportProofAuthority,
    coordinate: FilingExportProofCoordinate,
    refusals: list[FilingExportProofRefusal],
) -> FilingExportConformanceReceipt | None:
    request = FilingExportConformanceRequest(coordinate=coordinate)
    if authority.resolve_conformance_vector(request) is None:
        refusals.append(authority._refusal(coordinate, FilingExportProofChannel.CONFORMANCE))
        return None
    try:
        return authority.prove_conformance(request)
    except (FilingExportError, OSError, RegistryValidationError, ValueError):
        refusals.append(
            authority._refusal(
                coordinate,
                FilingExportProofChannel.CONFORMANCE,
                FilingExportProofRefusalReason.PROOF_VALIDATION_FAILED,
            ),
        )
        return None


def _assess_secure_replay_channel(
    authority: CanonicalTwoChannelFilingExportProofAuthority,
    coordinate: FilingExportProofCoordinate,
    refusals: list[FilingExportProofRefusal],
) -> FilingExportSecureReplayReceipt | None:
    source = authority._secure_replay_source
    custody = authority._secure_replay_custody
    if source is None or custody is None:
        refusals.append(
            authority._refusal(
                coordinate,
                FilingExportProofChannel.SECURE_REPLAY,
                FilingExportProofRefusalReason.AUTHORITY_UNAVAILABLE,
            ),
        )
        return None
    request = FilingExportSecureReplayRequest(
        coordinate=coordinate,
        source_authority_id=source.authority_id,
        custody_authority_id=custody.authority_id,
    )
    try:
        return prove_secure_export_replay(request, source_authority=source, custody=custody)
    except (FilingExportError, OSError, PersistenceError, RegistryValidationError, ValueError):
        refusals.append(
            authority._refusal(
                coordinate,
                FilingExportProofChannel.SECURE_REPLAY,
                FilingExportProofRefusalReason.CUSTODY_FAILED,
            ),
        )
        return None


def _require_unique_coordinates(coordinates: tuple[FilingExportProofCoordinate, ...], *, channel: str) -> None:
    if len(coordinates) != len(set(coordinates)):
        raise ValueError(f"filing export {channel} proof coordinates must be unique")


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
    if not isinstance(authority, ValidatedRegistryAuthority):
        raise TypeError("canonical filing proof requires a validated registry authority")
    enrollment = derive_filing_export_conformance_enrollment(
        workspace_root=workspace_root,
        registry_root=registry_root,
        source_root=source_root,
        authority=authority,
        vectors=canonical_filing_export_conformance_vectors(
            registry_root=registry_root,
            source_root=source_root,
        ),
    )
    return CanonicalTwoChannelFilingExportProofAuthority(
        workspace_root=workspace_root,
        registry_root=registry_root,
        source_root=source_root,
        authority=authority,
        vectors=enrollment.materializable_vectors,
        conformance_enrollment=enrollment,
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
        _verify_public_vector_probe(
            probe=probe,
            first_record=first,
            prefix_extent=prefix_extent,
            payload=payload,
        )


def _verify_public_vector_probe(
    *,
    probe: FilingExportOfficialProbe,
    first_record: ExportRecordDefinition,
    prefix_extent: int,
    payload: bytes,
) -> None:
    if probe.record_id != str(first_record.id) or not first_record.required or first_record.repeat is not None:
        raise RegistryValidationError(
            "official conformance probe must target the first required non-repeating record",
        )
    field, field_offset, field_length, literal = _public_vector_probe_field(probe, first_record)
    expected_offset = prefix_extent + field_offset - 1
    if probe.emitted_offset != expected_offset or probe.length != field_length:
        raise RegistryValidationError("official conformance probe span conflicts with the selected layout")
    expected = _literal_bytes(field, literal=literal, encoding=first_record.encoding)
    if payload[probe.emitted_offset : probe.emitted_offset + probe.length] != expected:
        raise RegistryValidationError(
            f"conformance payload disagrees at official field {probe.record_id!r}/{probe.field_id!r}",
        )


def _public_vector_probe_field(
    probe: FilingExportOfficialProbe,
    first_record: ExportRecordDefinition,
) -> tuple[ExportFieldDefinition, int, int, str]:
    field = next((item for item in first_record.fields if str(item.id) == probe.field_id), None)
    if field is None or field.offset is None or field.length is None or field.literal is None:
        raise RegistryValidationError("official conformance probe must target a positioned literal field")
    return field, field.offset, field.length, field.literal
