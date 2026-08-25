"""Dynamic refusal coverage for the two-channel filing-export proof port."""

from __future__ import annotations

from inspect import signature
from pathlib import Path
from typing import Any, cast

import pytest

from cadrumo.application.filing import FilingExportProofChannel, FilingExportProofCoordinate
from cadrumo.core import RegistryAuthorityGrade
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    RegistryValidationError,
    ValidatedRegistryAuthority,
    bundled_authority,
)

from ..filing_export_proof import (
    CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS,
    canonical_two_channel_filing_export_proof_authority,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_canonical_authority_cannot_accept_a_preconstructed_replay_receipt() -> None:
    """Replay success must execute source and custody ports, not trust a model."""
    parameters = signature(canonical_two_channel_filing_export_proof_authority).parameters

    assert "secure_replay_receipts" not in parameters
    assert {"secure_replay_source", "secure_replay_custody"} <= set(parameters)

    with pytest.raises(TypeError, match="secure_replay_receipts"):
        cast(Any, canonical_two_channel_filing_export_proof_authority)(
            workspace_root=_REPOSITORY_ROOT,
            registry_root=bundled_path("registry", "aeat"),
            source_root=bundled_path(),
            authority=cast(ValidatedRegistryAuthority, object()),
            secure_replay_source=None,
            secure_replay_custody=None,
            secure_replay_receipts=(object(),),
        )


def test_diagnostic_authority_refuses_classification_without_its_strict_failure() -> None:
    """A diagnostic authority is never an implicit alternative filing authority."""
    registry = ValidatedRegistryAuthority.load_for_diagnostic_classification(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )

    assert not registry.is_registry_validated
    with pytest.raises(ValueError, match="requires its strict registry validation error"):
        canonical_two_channel_filing_export_proof_authority(
            workspace_root=_REPOSITORY_ROOT,
            registry_root=bundled_path("registry", "aeat"),
            source_root=bundled_path(),
            authority=registry,
            secure_replay_source=None,
            secure_replay_custody=None,
        )


def test_every_selected_filing_revision_refuses_each_unenrolled_proof_channel() -> None:
    """S85 derives every public candidate and retains its exact refusal residue."""
    try:
        registry = bundled_authority()
    except RegistryValidationError as strict_error:
        registry = ValidatedRegistryAuthority.load_for_diagnostic_classification(
            bundled_path("registry", "aeat"),
            source_root=bundled_path(),
        )
        full_registry_validation_error = str(strict_error)
    else:
        full_registry_validation_error = None
    proof = canonical_two_channel_filing_export_proof_authority(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=registry,
        secure_replay_source=None,
        secure_replay_custody=None,
        full_registry_validation_error=full_registry_validation_error,
    )
    assessed = 0
    selected_coordinates = set()
    for modelo in registry.modelos:
        for revision in modelo.revisions.values():
            if revision.authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            coordinate = FilingExportProofCoordinate(
                modelo=modelo.id,
                revision=revision.id,
                layout_ids=tuple(layout.id for layout in revision.export_layouts),
            )
            selected_coordinates.add((str(coordinate.modelo), str(coordinate.revision)))
            assessment = proof.assess_for(coordinate)
            assert assessment.proof is None
            assert {item.channel for item in assessment.refusals} == {
                FilingExportProofChannel.CONFORMANCE,
                FilingExportProofChannel.SECURE_REPLAY,
            }
            assessed += 1
    assert assessed > 0

    enrollment = proof.conformance_enrollment
    assert enrollment.full_registry_validation_error == full_registry_validation_error
    candidate_coordinates = {
        (str(candidate.evidence.coordinate.modelo), str(candidate.evidence.coordinate.revision))
        for candidate in enrollment.provenance_candidates
    }
    materialized_coordinates = {
        (str(vector.evidence.coordinate.modelo), str(vector.evidence.coordinate.revision))
        for vector in enrollment.materializable_vectors
    }
    residue_coordinates = {(str(residue.modelo), str(residue.revision)) for residue in enrollment.residues}
    canonical_vector_coordinates = {
        (str(vector.evidence.coordinate.modelo), str(vector.evidence.coordinate.revision))
        for vector in CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS
    }

    assert selected_coordinates == materialized_coordinates | residue_coordinates
    assert candidate_coordinates <= selected_coordinates
    assert materialized_coordinates <= canonical_vector_coordinates
    assert candidate_coordinates - materialized_coordinates <= residue_coordinates
    assert canonical_vector_coordinates - materialized_coordinates <= residue_coordinates
    assert all(
        residue.owner and residue.reconsideration_condition and residue.detail for residue in enrollment.residues
    )
    assert all(
        not {
            "draft",
            "producer_snapshot",
            "dictionary_values",
            "prior_domiciliation_election",
            "product_software_identity",
            "payload",
            "payload_sha256",
            "accepted_payload_hash",
        }.intersection(type(candidate.evidence).model_fields)
        for candidate in enrollment.provenance_candidates
    )
    if full_registry_validation_error is not None:
        assert not registry.is_registry_validated
        assert not materialized_coordinates
        assert any(residue.reason == "generated_provenance_invalid" for residue in enrollment.residues)
