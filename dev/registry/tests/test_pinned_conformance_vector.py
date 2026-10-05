"""Detector teeth for the pinned public conformance-vector contract.

The pinning design exists to make a regenerated export tree fail closed rather
than be silently absorbed: the vector's evidence is committed data, so a tree
whose generation manifest no longer matches the pin must be refused. These
tests prove that refusal actually fires, and that a corrupt pin surfaces as a
typed registry refusal rather than an unhandled crash with no owner.
"""

from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path as _bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import governed_facts_in_scope

from ..compiler.authority import compile_validated_authority
from ..filing_export_conformance import FilingExportConformanceRequest
from ..filing_export_conformance_enrollment import derive_filing_export_conformance_enrollment
from ..filing_export_conformance_vectors import (
    build_pinned_conformance_evidence,
    canonical_filing_export_conformance_vectors,
    load_pinned_conformance_document,
    load_pinned_conformance_inputs,
)
from ..filing_export_proof_authority import (
    CanonicalTwoChannelFilingExportProofAuthority,
    canonical_two_channel_filing_export_proof_authority,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PINNED = Path(__file__).resolve().parents[1] / "conformance_vectors" / "modelo_200_2025_y_siguientes.toml"
_REGISTRY_ROOT = _bundled_path("registry", "aeat")


def test_the_shipped_pin_materializes_against_the_current_generated_tree() -> None:
    """The committed pin admits the tree as generated today."""
    vectors = canonical_filing_export_conformance_vectors(
        registry_root=_REGISTRY_ROOT,
        source_root=_bundled_path(),
    )
    assert len(vectors) == 1
    coordinate = vectors[0].evidence.coordinate
    assert (str(coordinate.modelo), str(coordinate.revision)) == ("200", "2025-y-siguientes")

    authority = compile_validated_authority(_REGISTRY_ROOT, _bundled_path())
    enrollment = derive_filing_export_conformance_enrollment(
        workspace_root=Path.cwd(),
        registry_root=_REGISTRY_ROOT,
        source_root=_bundled_path(),
        authority=authority,
        vectors=vectors,
    )
    materialized = {
        (str(vector.evidence.coordinate.modelo), str(vector.evidence.coordinate.revision))
        for vector in enrollment.materializable_vectors
    }
    m200_residues = [
        (residue.reason, residue.owner, residue.detail)
        for residue in enrollment.residues
        if str(residue.modelo) == "200"
    ]
    assert ("200", "2025-y-siguientes") in materialized, m200_residues
    assert not m200_residues
    candidates = {
        (str(candidate.evidence.coordinate.modelo), str(candidate.evidence.coordinate.revision))
        for candidate in enrollment.provenance_candidates
    }
    assert {
        ("165", "2026-y-siguientes"),
        ("189", "2024"),
        ("189", "2025"),
        ("369", "esquema-exterior"),
        ("369", "esquema-importacion"),
        ("369", "esquema-union"),
    } <= candidates


def test_public_proof_uses_the_real_writer_and_restores_candidate_fact_scope(tmp_path: Path) -> None:
    """Required rows, typed rate inputs and official probes all reach the production writer."""
    authority = compile_validated_authority(_REGISTRY_ROOT, _bundled_path())
    proof = canonical_two_channel_filing_export_proof_authority(
        workspace_root=Path.cwd(),
        registry_root=_REGISTRY_ROOT,
        source_root=_bundled_path(),
        authority=authority,
        secure_replay_source=None,
        secure_replay_custody=None,
    )
    vector = proof.conformance_enrollment.materializable_vectors[0]
    before = governed_facts_in_scope()
    render = vector.builder.build(vector.evidence)
    assert governed_facts_in_scope() is before
    values = {value.casilla_id: value.value for value in render.draft.values}
    assert values["DP200014:00562"] == Decimal("25000")
    assert render.draft.profile_tax_id == render.producer_snapshot.taxpayer_tax_id
    assert render.product_software_identity is not None
    request = FilingExportConformanceRequest(coordinate=vector.evidence.coordinate)
    receipt = proof.prove_conformance(request)
    assert receipt.checked_official_offsets == len(vector.evidence.provenance.probes)
    assert receipt.emitted_bytes > 0
    assert receipt.taxpayer_truth_claimed is False
    assert receipt.source_owned_replay_claimed is False
    assert governed_facts_in_scope() is before

    # The healthy active tree must not mask a corrupt explicitly selected candidate.
    candidate_root = tmp_path / "registry"
    candidate_export = candidate_root / "modelos/200/revisions/2025-y-siguientes/export"
    shutil.copytree(_REGISTRY_ROOT / "modelos/200/revisions/2025-y-siguientes/export", candidate_export)
    selected_output = candidate_export / vector.evidence.provenance.generated_outputs[0].relative_path
    selected_output.write_bytes(selected_output.read_bytes() + b"\n# changed candidate\n")
    candidate_proof = CanonicalTwoChannelFilingExportProofAuthority(
        workspace_root=Path.cwd(),
        registry_root=candidate_root,
        source_root=_bundled_path(),
        authority=authority,
        vectors=(vector,),
        conformance_enrollment=proof.conformance_enrollment,
        secure_replay_source=None,
        secure_replay_custody=None,
    )
    with pytest.raises(RegistryValidationError, match="output-file digests"):
        candidate_proof.prove_conformance(request)
    assert governed_facts_in_scope() is before


def test_a_manifest_digest_that_drifts_from_the_pin_is_refused(tmp_path: Path) -> None:
    """A regenerated tree must fail closed, never be silently absorbed."""
    drifted = tmp_path / "drifted.toml"
    text = _PINNED.read_text(encoding="utf-8")
    document = load_pinned_conformance_document(_PINNED)
    drifted.write_text(
        text.replace(document.generation_manifest_sha256, "0" * 64),
        encoding="utf-8",
    )
    manifest_path = (
        _REGISTRY_ROOT
        / "modelos"
        / "200"
        / "revisions"
        / "2025-y-siguientes"
        / "export"
        / "_generation.provenance.json"
    )
    manifest_raw = manifest_path.read_bytes()

    from ..pipeline.export_fragment_provenance import load_export_fragment_provenance_manifest

    with pytest.raises(RegistryValidationError, match="does not match the pinned conformance vector"):
        build_pinned_conformance_evidence(
            load_pinned_conformance_document(drifted),
            manifest_raw=manifest_raw,
            manifest=load_export_fragment_provenance_manifest(manifest_raw),
        )


def test_a_corrupt_pin_refuses_as_a_typed_registry_error(tmp_path: Path) -> None:
    """A truncated or malformed pin must not escape as an unowned crash."""
    truncated = tmp_path / "truncated.toml"
    shutil.copy(_PINNED, truncated)
    truncated.write_text('authority_id = "only-this"\n', encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="pinned-vector contract"):
        load_pinned_conformance_document(truncated)

    unparseable = tmp_path / "unparseable.toml"
    unparseable.write_text("this is = = not toml\n", encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="unreadable"):
        load_pinned_conformance_document(unparseable)

    absent = tmp_path / "absent.toml"
    with pytest.raises(RegistryValidationError, match="unreadable"):
        load_pinned_conformance_document(absent)


def test_one_id_declared_on_both_input_channels_is_refused(tmp_path: Path) -> None:
    """An ambiguous declaration is refused rather than resolved by ordering."""
    colliding = tmp_path / "colliding.toml"
    text = _PINNED.read_text(encoding="utf-8")
    decimal_id = next(iter(load_pinned_conformance_document(_PINNED).inputs["decimal"]))
    colliding.write_text(
        text.replace(
            "[inputs.enum]",
            f'[inputs.enum]\n"{decimal_id}" = "sl"',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryValidationError, match="multiple typed channels"):
        load_pinned_conformance_inputs(load_pinned_conformance_document(colliding))


def test_public_boolean_input_is_typed_and_cannot_shadow_another_channel(tmp_path: Path) -> None:
    """Profile predicates arrive as bools, never numeric substitutes or overwritten ids."""
    document = load_pinned_conformance_document(_PINNED)
    values = load_pinned_conformance_inputs(document)
    assert values["modelo-200-profile-new-entity-flag"] is False
    colliding = tmp_path / "boolean-collision.toml"
    colliding.write_text(
        _PINNED.read_text(encoding="utf-8").replace(
            '"modelo-200-profile-new-entity-flag" = false', '"DP200012:00501" = false'
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryValidationError, match="multiple typed channels"):
        load_pinned_conformance_inputs(load_pinned_conformance_document(colliding))
    mistyped = tmp_path / "numeric-predicate.toml"
    mistyped.write_text(
        _PINNED.read_text(encoding="utf-8").replace(
            '"modelo-200-profile-new-entity-flag" = false', '"modelo-200-profile-new-entity-flag" = 0'
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryValidationError, match="pinned-vector contract"):
        load_pinned_conformance_document(mistyped)
