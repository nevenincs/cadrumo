"""Live filing-export proof refuses invented, stale, and non-executable evidence."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.application.filing.tests._export_support import (
    _approved_modelo_111_registry_draft,
    _approved_modelo_200_registry_draft,
    _typed_producer_snapshot,
)
from cadrumo.application.registry.filing_export_authority import FilingExportProofConflictError
from cadrumo.application.registry.filing_export_coverage import compose_filing_export_coverage
from cadrumo.core import PaymentElection, PriorDomiciliationElection, RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.product_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..filing_export_proof import (
    FilingExportLiveProofEntry,
    FilingExportOfficialOffsetProbe,
    LiveFilingExportProofAuthority,
    verify_filing_export_payload_acceptance,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).parents[3]


def _m111_entry() -> FilingExportLiveProofEntry:
    return FilingExportLiveProofEntry(
        modelo=Modelo.M111,
        revision="2019-y-siguientes",
        design_epoch="2019",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        draft=_approved_modelo_111_registry_draft(),
        producer_snapshot=_typed_producer_snapshot(),
        expected_payload_sha256="0" * 64,
        expected_emitted_bytes=1,
        official_offset_probes=(FilingExportOfficialOffsetProbe(record_id="invented", field_id="invented"),),
    )


def _m200_producer_snapshot():
    from cadrumo.application.filing import (
        FilingElectionFacts,
        GeneralFilingProfileFacts,
        PresenterIdentity,
        TaxpayerIdentityFacts,
        build_filing_producer_snapshot,
    )

    return build_filing_producer_snapshot(
        modelo=Modelo.M200,
        taxpayer_tax_id="B12345674",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name="Emilio Export Test SL",
            given_name=None,
            surnames=None,
            full_name="Emilio Export Test SL",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


def _m200_entry() -> FilingExportLiveProofEntry:
    return FilingExportLiveProofEntry(
        modelo=Modelo.M200,
        revision="2024",
        design_epoch="2025",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        draft=_approved_modelo_200_registry_draft(),
        producer_snapshot=_m200_producer_snapshot(),
        expected_payload_sha256="0" * 64,
        expected_emitted_bytes=1,
        official_offset_probes=(
            FilingExportOfficialOffsetProbe(record_id="m200-page-001", field_id="m200-2025.dp200001.f0001"),
        ),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=AeatProductSoftwareIdentity(
            program_identifier="C200",
            developer_tax_id="Y0000001S",
            evidence=(AeatProductSoftwareEvidence(reference="test-live-proof", digest="a" * 64),),
        ),
    )


def _authority(registry_authority, *, workspace_root: Path, entries):
    return LiveFilingExportProofAuthority(
        workspace_root=workspace_root,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=registry_authority,
        entries=entries,
    )


def test_modelo_111_invented_catalogue_values_cannot_replace_missing_canonical_generation(
    registry_authority,
) -> None:
    """Well-shaped zero hashes never reach a satisfied proof for Modelo 111."""
    entry = _m111_entry()
    authority = _authority(registry_authority, workspace_root=_REPO_ROOT, entries=(entry,))
    snapshot = registry_authority.snapshot("111", filing_year=2026, period="1T")

    with pytest.raises(FileNotFoundError):
        authority.proof_for(
            modelo=entry.modelo,
            revision=entry.revision,
            layout_ids=tuple(layout.id for layout in snapshot.revision.export_layouts),
        )


def test_modelo_111_fabricated_entry_remains_a_visible_stale_evidence_refusal(registry_authority) -> None:
    entry = _m111_entry()
    modelo = registry_authority.modelo("111")
    revision = modelo.revisions[entry.revision]
    narrowed_modelo = modelo.model_copy(update={"revisions": {revision.id: revision}})
    narrowed = replace(
        registry_authority,
        modelos=(narrowed_modelo,),
        _modelos_by_id={narrowed_modelo.id: narrowed_modelo},
        _snapshots={},
    )
    authority = _authority(narrowed, workspace_root=_REPO_ROOT, entries=(entry,))

    limb = compose_filing_export_coverage(authority=narrowed, proof_authority=authority).limbs[0]

    assert limb.outcome == "refused"
    assert limb.refusal is not None
    assert limb.refusal.reason == "stale_evidence"
    assert "_generation.provenance.json" in limb.refusal.detail


def test_live_authority_reports_layout_identity_conflict_before_reading_catalogue_bytes(registry_authority) -> None:
    entry = _m111_entry()
    authority = _authority(registry_authority, workspace_root=_REPO_ROOT, entries=(entry,))

    with pytest.raises(FilingExportProofConflictError, match="conflicts with the law-selected loaded layouts"):
        authority.proof_for(modelo=entry.modelo, revision=entry.revision, layout_ids=("fabricated-layout",))


def test_live_authority_rejects_a_stale_generated_output_digest(registry_authority, tmp_path: Path) -> None:
    """The canonical verifier re-hashes generated TOML instead of trusting its catalogue row."""
    entry = _m200_entry()
    _copy_m200_authored_proof_surface(tmp_path)
    output = next(
        path
        for path in (tmp_path / "src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/export").glob(
            "*.toml",
        )
    )
    output.write_bytes(output.read_bytes() + b"\n")
    authority = _authority(registry_authority, workspace_root=tmp_path, entries=(entry,))
    snapshot = registry_authority.snapshot("200", filing_year=2025, period="0A")

    with pytest.raises(RegistryValidationError, match="output-file digests do not match"):
        authority.proof_for(
            modelo=entry.modelo,
            revision=entry.revision,
            layout_ids=tuple(layout.id for layout in snapshot.revision.export_layouts),
        )


@pytest.mark.parametrize(
    "digest_field",
    ("semantic_map_sha256", "render_profile_sha256", "loader_semantic_sha256"),
)
def test_live_authority_rehashes_each_canonical_generation_semantic(
    registry_authority,
    tmp_path: Path,
    digest_field: str,
) -> None:
    entry = _m200_entry()
    _copy_m200_authored_proof_surface(tmp_path)
    manifest = (
        tmp_path / "src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/export" / "_generation.provenance.json"
    )
    raw = manifest.read_bytes()
    marker = f'"{digest_field}":"'.encode()
    start = raw.index(marker) + len(marker)
    manifest.write_bytes(raw[:start] + b"0" * 64 + raw[start + 64 :])
    authority = _authority(registry_authority, workspace_root=tmp_path, entries=(entry,))
    snapshot = registry_authority.snapshot("200", filing_year=2025, period="0A")

    with pytest.raises(RegistryValidationError, match=r"does not match current generation authorities|loader-semantic"):
        authority.proof_for(
            modelo=entry.modelo,
            revision=entry.revision,
            layout_ids=tuple(layout.id for layout in snapshot.revision.export_layouts),
        )


def test_current_generation_proof_does_not_hide_a_non_executable_production_export(registry_authority) -> None:
    """Current M200 generation reaches export_draft, whose live refusal remains a refusal."""
    entry = _m200_entry()
    authority = _authority(registry_authority, workspace_root=_REPO_ROOT, entries=(entry,))
    snapshot = registry_authority.snapshot("200", filing_year=2025, period="0A")

    with pytest.raises(ValueError, match="cannot render its fixed-width value"):
        authority.proof_for(
            modelo=entry.modelo,
            revision=entry.revision,
            layout_ids=tuple(layout.id for layout in snapshot.revision.export_layouts),
        )


def test_live_proof_entry_refuses_duplicate_official_probe_identities() -> None:
    probe = FilingExportOfficialOffsetProbe(record_id="m200-page-001", field_id="m200-2025.dp200001.f0001")

    with pytest.raises(ValueError, match="probes must identify distinct fields"):
        replace(_m200_entry(), official_offset_probes=(probe, probe))


def test_payload_acceptance_rehashes_bytes_extent_and_official_offset(registry_authority) -> None:
    base = _m200_entry()
    layout = registry_authority.snapshot("200", filing_year=2025, period="0A").revision.export_layouts[0]
    prefix_extent = layout.filing_envelope.prefix_extent
    payload = b" " * prefix_extent + b"<T" + b" " * 8
    entry = replace(
        base,
        expected_payload_sha256=sha256_hex(payload),
        expected_emitted_bytes=len(payload),
    )

    verify_filing_export_payload_acceptance(entry=entry, layout=layout, payload=payload)
    with pytest.raises(RegistryValidationError, match="digest does not match"):
        verify_filing_export_payload_acceptance(entry=entry, layout=layout, payload=payload + b"x")
    wrong_extent = replace(entry, expected_emitted_bytes=len(payload) + 1)
    with pytest.raises(RegistryValidationError, match="extent does not match"):
        verify_filing_export_payload_acceptance(entry=wrong_extent, layout=layout, payload=payload)
    moved = b" " * prefix_extent + b"X<T" + b" " * 7
    moved_entry = replace(entry, expected_payload_sha256=sha256_hex(moved))
    with pytest.raises(RegistryValidationError, match="disagrees at official field"):
        verify_filing_export_payload_acceptance(entry=moved_entry, layout=layout, payload=moved)


def test_payload_acceptance_refuses_distinct_probe_ids_at_overlapping_emitted_bytes(registry_authority) -> None:
    base = _m200_entry()
    layout = registry_authority.snapshot("200", filing_year=2025, period="0A").revision.export_layouts[0]
    first = min(layout.records, key=lambda record: record.order)
    first_field = next(field for field in first.fields if str(field.id) == "m200-2025.dp200001.f0001")
    overlapping_field = next(field for field in first.fields if str(field.id) == "m200-2025.dp200001.f0002")
    overlapping_record = first.model_copy(
        update={
            "fields": tuple(
                field.model_copy(update={"offset": 2}) if field == overlapping_field else field
                for field in first.fields
            ),
        },
    )
    overlapping_layout = layout.model_copy(
        update={
            "records": tuple(record if record != first else overlapping_record for record in layout.records),
        },
    )
    prefix_extent = layout.filing_envelope.prefix_extent
    payload = b" " * prefix_extent + b"<T" + b" " * 8
    entry = replace(
        base,
        expected_payload_sha256=sha256_hex(payload),
        expected_emitted_bytes=len(payload),
        official_offset_probes=(
            FilingExportOfficialOffsetProbe(record_id=str(first.id), field_id=str(first_field.id)),
            FilingExportOfficialOffsetProbe(record_id=str(first.id), field_id=str(overlapping_field.id)),
        ),
    )

    with pytest.raises(RegistryValidationError, match="distinct emitted byte positions"):
        verify_filing_export_payload_acceptance(entry=entry, layout=overlapping_layout, payload=payload)


def _copy_m200_authored_proof_surface(root: Path) -> None:
    for relative in (
        Path("dev/registry/mappings/modelo_200/2025"),
        Path("dev/registry/render_profiles/modelo_200/2025"),
        Path("src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/export"),
    ):
        shutil.copytree(_REPO_ROOT / relative, root / relative)
