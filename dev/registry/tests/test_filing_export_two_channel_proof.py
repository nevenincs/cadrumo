"""Dynamic refusal coverage for the two-channel filing-export proof port."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import fields, is_dataclass
from datetime import date
from enum import Enum
from inspect import signature
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import BaseModel

from cadrumo.application.filing import FilingExportProofChannel, FilingExportProofCoordinate
from cadrumo.core import RegistryAuthorityGrade
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry.authority import (
    RegistryDiagnosticFilingRevision,
    ValidatedRegistryAuthority,
    bundled_authority,
    load_registry_diagnostic_classification,
)
from cadrumo.domain.calculations.registry.static_inspection import (
    RegistryRevisionInspection,
    StaticGeneratedArtifactInspection,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..filing_export_proof import (
    CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS,
    FilingExportConformanceEnrollmentReport,
    FilingExportConformanceVector,
    _derive_static_filing_export_conformance_enrollment,
    canonical_two_channel_filing_export_proof_authority,
    derive_diagnostic_filing_export_conformance_enrollment,
    derive_filing_export_conformance_enrollment,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _static_data_graph(value: object) -> Iterator[object]:
    """Walk only values stored in the static diagnostic projection."""
    yield value
    if isinstance(value, (str, int, float, bool, date, Enum, type(None))):
        return
    if isinstance(value, (tuple, frozenset)):
        for item in value:
            yield from _static_data_graph(item)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _static_data_graph(key)
            yield from _static_data_graph(item)
        return
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            yield from _static_data_graph(getattr(value, field.name))
        return
    if isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            yield from _static_data_graph(getattr(value, field_name))
        return
    raise AssertionError(f"diagnostic projection retained a non-static value: {type(value).__name__}")


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


def test_diagnostic_classification_has_no_runtime_authority_or_success_path() -> None:
    """Diagnostic classification remains static residue, never filing authority."""
    classification = load_registry_diagnostic_classification(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        strict_validation_error=RegistryValidationError("strict registry validation failed"),
    )

    assert not isinstance(classification, ValidatedRegistryAuthority)
    assert not {"_authority", "snapshot", "modelo", "catalogues", "validate_modelo"}.intersection(dir(classification))
    with pytest.raises(AttributeError):
        object.__getattribute__(classification, "_authority")
    projection_values = tuple(_static_data_graph(classification))
    assert not any(isinstance(value, ValidatedRegistryAuthority) for value in projection_values)
    assert not any(callable(value) for value in projection_values)
    with pytest.raises(TypeError, match="requires a validated registry authority"):
        canonical_two_channel_filing_export_proof_authority(
            workspace_root=_REPOSITORY_ROOT,
            registry_root=bundled_path("registry", "aeat"),
            source_root=bundled_path(),
            authority=cast(Any, classification),
            secure_replay_source=None,
            secure_replay_custody=None,
        )
    enrollment = derive_diagnostic_filing_export_conformance_enrollment(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        classification=classification,
        vectors=CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS,
    )
    assert enrollment.full_registry_validation_error == "strict registry validation failed"
    assert not enrollment.materializable_vectors
    assert enrollment.residues


def test_static_projection_has_one_residue_classifier_and_strict_failure_cannot_materialize() -> None:
    """Identical static facts preserve residue while strict failure closes success."""
    selected = RegistryDiagnosticFilingRevision(
        modelo="100",
        revision="static-refusal",
        selection_coordinates=(),
        layout_ids=(),
        layout_json=None,
        inspection=None,
        refusal_reason="law_selection_failed",
        refusal_detail="synthetic static selection failure",
    )
    strict_report = _derive_static_filing_export_conformance_enrollment(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        revisions=(selected,),
        vectors=(),
        strict_validation_error=None,
        validated_authority=None,
    )
    diagnostic_report = _derive_static_filing_export_conformance_enrollment(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        revisions=(selected,),
        vectors=(),
        strict_validation_error="whole-registry validation failed",
        validated_authority=None,
    )

    assert diagnostic_report.residues == strict_report.residues
    assert not diagnostic_report.materializable_vectors
    blocked_vector = cast(
        FilingExportConformanceVector,
        SimpleNamespace(evidence=SimpleNamespace(coordinate=SimpleNamespace(modelo="100", revision="static-refusal"))),
    )
    with pytest.raises(ValueError, match="cannot materialize"):
        FilingExportConformanceEnrollmentReport(
            full_registry_validation_error="whole-registry validation failed",
            provenance_candidates=(),
            materializable_vectors=(blocked_vector,),
            residues=(),
        )


def _candidate_signature(report: FilingExportConformanceEnrollmentReport) -> tuple[object, ...]:
    return tuple(
        sorted(
            (
                str(candidate.evidence.coordinate.modelo),
                str(candidate.evidence.coordinate.revision),
                candidate.evidence.coordinate.layout_ids,
                candidate.evidence.filing_year,
                str(candidate.evidence.period),
                candidate.evidence.mechanism_source_ref,
                candidate.evidence.mechanism_source_sha256,
                candidate.evidence.provenance,
            )
            for candidate in report.provenance_candidates
        )
    )


def _residue_signature(report: FilingExportConformanceEnrollmentReport) -> tuple[object, ...]:
    return tuple(
        sorted(
            (
                str(residue.modelo),
                str(residue.revision),
                residue.layout_ids,
                residue.reason,
                residue.owner,
                residue.reconsideration_condition,
                residue.detail,
            )
            for residue in report.residues
        )
    )


@pytest.mark.timeout(600)
def test_static_projection_matches_validated_classification_for_every_selected_revision() -> None:
    """The immutable diagnostic projection preserves every strict disposition."""
    registry = bundled_authority()
    classification = load_registry_diagnostic_classification(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        strict_validation_error=RegistryValidationError("forced strict validation failure"),
    )

    strict_report = derive_filing_export_conformance_enrollment(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=registry,
        vectors=CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS,
    )
    diagnostic_report = derive_diagnostic_filing_export_conformance_enrollment(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        classification=classification,
        vectors=CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS,
    )

    static_inspections = tuple(
        selected.inspection for selected in classification.filing_revisions if selected.inspection is not None
    )
    assert static_inspections
    assert all(isinstance(inspection, StaticGeneratedArtifactInspection) for inspection in static_inspections)
    assert not any(isinstance(value, RegistryRevisionInspection) for value in _static_data_graph(classification))
    assert _candidate_signature(diagnostic_report) == _candidate_signature(strict_report)
    assert _residue_signature(diagnostic_report) == _residue_signature(strict_report)
    assert not diagnostic_report.materializable_vectors


def test_every_selected_filing_revision_refuses_each_unenrolled_proof_channel() -> None:
    """Every public candidate retains its exact refusal residue."""
    try:
        registry = bundled_authority()
    except RegistryValidationError as strict_error:
        classification = load_registry_diagnostic_classification(
            bundled_path("registry", "aeat"),
            source_root=bundled_path(),
            strict_validation_error=strict_error,
        )
        enrollment = derive_diagnostic_filing_export_conformance_enrollment(
            workspace_root=_REPOSITORY_ROOT,
            registry_root=bundled_path("registry", "aeat"),
            source_root=bundled_path(),
            classification=classification,
            vectors=CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS,
        )
        selected_coordinates = {
            (str(selected.modelo), str(selected.revision)) for selected in classification.filing_revisions
        }
        materialized_coordinates = {
            (str(vector.evidence.coordinate.modelo), str(vector.evidence.coordinate.revision))
            for vector in enrollment.materializable_vectors
        }
        residue_coordinates = {(str(residue.modelo), str(residue.revision)) for residue in enrollment.residues}
        assert enrollment.full_registry_validation_error == str(strict_error)
        assert selected_coordinates == residue_coordinates
        assert not materialized_coordinates
        return
    else:
        full_registry_validation_error = None
    proof = canonical_two_channel_filing_export_proof_authority(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=registry,
        secure_replay_source=None,
        secure_replay_custody=None,
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
    assert full_registry_validation_error is None
