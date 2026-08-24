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
from tempfile import TemporaryDirectory

from cadrumo.application.filing import (
    FilingProducerSnapshot,
    build_runtime_schema_provider,
    export_draft,
)
from cadrumo.application.registry import (
    FilingExportEmissionProof,
    FilingExportGenerationProof,
    FilingExportProof,
    FilingExportProofConflictError,
    GeneratedExportFileDigest,
)
from cadrumo.core import (
    AeatProductSoftwareIdentity,
    Period,
    PriorDomiciliationElection,
    RegistryAuthorityGrade,
    sha256_hex,
)
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
from cadrumo.domain.filing import ModeloDraft

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
    "CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES",
    "FilingExportLiveProofEntry",
    "FilingExportOfficialOffsetProbe",
    "LiveFilingExportProofAuthority",
    "canonical_live_filing_export_proof_authority",
    "verify_filing_export_payload_acceptance",
]


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
        snapshot = self._authority.snapshot(
            modelo,
            filing_year=entry.filing_year,
            period=entry.period.registry_token,
            grade=RegistryAuthorityGrade.FILING,
        )
        actual_layout_ids = tuple(layout.id for layout in snapshot.revision.export_layouts)
        if snapshot.revision.id != revision or actual_layout_ids != layout_ids:
            raise FilingExportProofConflictError(
                "filing export live proof coordinate conflicts with the law-selected loaded layouts",
            )
        if len(snapshot.revision.export_layouts) != 1:
            raise RegistryValidationError("live export proof requires exactly one generated filing layout")
        layout = snapshot.revision.export_layouts[0]
        manifest, manifest_path = self._verify_generation(entry=entry, layout=layout)
        payload = self._execute_export(entry=entry)
        verify_filing_export_payload_acceptance(entry=entry, layout=layout, payload=payload)
        return FilingExportProof(
            modelo=modelo,
            revision=revision,
            layout_ids=actual_layout_ids,
            generation=FilingExportGenerationProof(
                authority="dev.registry.pipeline.verify_export_fragment_provenance_manifest",
                manifest_locator=manifest_path.relative_to(self._workspace_root).as_posix(),
                manifest_sha256=sha256_hex(manifest_path.read_bytes()),
                semantic_map_sha256=manifest.semantic_map_sha256,
                render_profile_sha256=manifest.render_profile_sha256,
                loader_semantic_sha256=manifest.loader_semantic_sha256,
                output_files=tuple(
                    GeneratedExportFileDigest(relative_path=item.relative_path, sha256=item.sha256)
                    for item in manifest.output_files
                ),
            ),
            emission=FilingExportEmissionProof(
                authority="cadrumo.application.filing.export_draft",
                evidence_locator=f"live-export/{modelo}/{revision}",
                payload_sha256=sha256_hex(payload),
                emitted_bytes=len(payload),
                checked_official_offsets=len(entry.official_offset_probes),
            ),
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

    def _execute_export(self, *, entry: FilingExportLiveProofEntry) -> bytes:
        provider = build_runtime_schema_provider(
            self._registry_root,
            source_root=self._source_root,
            filing_year=entry.filing_year,
            period=entry.period,
            modelos=(str(entry.modelo),),
        )
        with TemporaryDirectory(prefix="cadrumo-live-export-proof-") as temporary:
            output_path = Path(temporary) / f"modelo-{entry.modelo}.txt"
            receipt = export_draft(
                entry.draft,
                output_path=output_path,
                producer_snapshot=entry.producer_snapshot,
                dictionary_values=entry.dictionary_values,
                prior_domiciliation_election=entry.prior_domiciliation_election,
                product_software_identity=entry.product_software_identity,
                schema_provider=provider,
            )
            payload = output_path.read_bytes()
        if receipt.file_sha256 != sha256_hex(payload) or receipt.byte_size != len(payload):
            raise RegistryValidationError("production export receipt disagrees with the re-read emitted payload")
        return payload


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
