"""A captured filing kind survives the encrypted observation boundary, and its absence reads unknown.

The projection is optional so rows written before it existed still load; such a
row must read as unknown, never as an original. Real adapters throughout: real
master-key provider, real SQLite engine and serializer through
``isolated_runtime_profile``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.storage.sql.tables import secure_objects_table
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
)
from cadrumo.application.calculations.observations_repository import ObservationEnvelopePayload, member_observation_key
from cadrumo.application.persistence_errors import PersistenceDegradationError
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.registry_observations import revision_id_for_observation
from cadrumo.domain.modelos.filing_kind_evidence import (
    UNKNOWN_FILING_KIND,
    FilingKindEvidenceBasis,
    ObservedFilingKind,
    SubmittedFileFilingKindMarker,
    observed_filing_kind_from_capture,
    register_tipo_solicitud_reading,
    submitted_file_marker_reading,
)
from cadrumo.domain.modelos.filing_record import FilingDeclarationKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 4, 21, 9, 0, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "3T")
_MEMBER = "B12345678"
_MARKER_LOCATOR = "modelo-130-fichero-boe:modelo-130-page-01:modelo-130-page-01-declaracion-complementaria:432:1"


def _stored_layer(envelope: dict[str, Any]) -> dict[str, Any]:
    layers = envelope["payload"]
    return layers["pending_local"] or layers["official"]


def _observation() -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="130",
        filing_year=2025,
        period="3T",
        observations=(
            CasillaObservation(
                casilla_id=validated_casilla_id("19", surface="filing kind roundtrip"),
                value=Decimal("40.00"),
                legal_refs=("rd-439-2007:art-110",),
                source_refs=("aeat-modelo-130-instructions",),
            ),
        ),
    )


def _complementaria() -> ObservedFilingKind:
    """A complementaria whose register reading agrees, so both readings must survive."""
    return observed_filing_kind_from_capture(
        SubmittedFileFilingKindMarker(
            declaration_marker=submitted_file_marker_reading("X", source_locator=_MARKER_LOCATOR),
        ),
        register_reading=register_tipo_solicitud_reading(
            "Complementaria", source_locator="aeat-register:202513000000001Z:tipo_solicitud"
        ),
    )


def _save(repo: CalculationObservationRepository, filing_kind: ObservedFilingKind | None) -> ObservationEnvelopePayload:
    repo.save(
        repo.prepare_observation_envelope(
            _observation(),
            source_kind="aeat_sede_justificante",
            captured_at=_CAPTURED_AT,
            member_nif=_MEMBER,
            filing_kind=filing_kind,
            stamped_revision_id=revision_id_for_observation(_observation()),
        )
    )
    loaded = repo.load(member_observation_key("130", _PERIOD, _MEMBER))
    assert loaded is not None
    return loaded


def _mutate(profile: Any, mutate: Any) -> None:
    stmt = select(secure_objects_table).where(
        secure_objects_table.c.namespace == CalculationObservationRepository.namespace,
        secure_objects_table.c.object_key == member_observation_key("130", _PERIOD, _MEMBER),
    )
    mutate_encrypted_secure_object_json(profile.repository._engine, row_statement=stmt, mutate=mutate)


def test_a_captured_filing_kind_survives_the_roundtrip_with_its_readings(tmp_path: Path) -> None:
    expected = _complementaria()
    assert expected.basis is FilingKindEvidenceBasis.SUBMITTED_FILE_MARKER
    assert len(expected.readings) == 2

    with isolated_runtime_profile(tmp_path=tmp_path):
        loaded = _save(CalculationObservationRepository(), expected)

    assert loaded.filing_kind == expected
    assert loaded.observed_filing_kind.admitted_kind is FilingDeclarationKind.COMPLEMENTARIA


def test_a_row_without_the_projection_reads_unknown_not_original(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository()
        saved = _save(repo, _complementaria())

        def drop(envelope: dict[str, Any]) -> None:
            assert _stored_layer(envelope)["filing_kind"] is not None
            del _stored_layer(envelope)["filing_kind"]

        _mutate(profile, drop)
        reloaded = repo.load(member_observation_key("130", _PERIOD, _MEMBER))

    assert reloaded is not None
    assert reloaded.filing_kind is None
    assert reloaded.observed_filing_kind == UNKNOWN_FILING_KIND
    assert reloaded != saved


def test_a_stored_kind_without_its_basis_refuses_at_load(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository()
        _save(repo, _complementaria())

        def strip_basis(envelope: dict[str, Any]) -> None:
            stored = _stored_layer(envelope)["filing_kind"]
            assert stored["kind"] == "complementaria"
            stored["basis"] = "none"

        _mutate(profile, strip_basis)
        with pytest.raises(PersistenceDegradationError) as refused:
            repo.load(member_observation_key("130", _PERIOD, _MEMBER))

    assert isinstance(refused.value.__cause__, ValidationError)
