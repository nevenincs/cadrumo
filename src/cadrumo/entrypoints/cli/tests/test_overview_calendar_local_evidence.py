"""Local filing evidence resolver tests for overview calendar output."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ....adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....application.calculations.observations_repository import CalculationObservationRepository
from ....core.config import load_settings
from ....core.period import Period
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.modelos.filing_repository import upsert_filing_record
from ....tests import FIXTURES_DIR
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_minimal_profile
from .._overview import _local_calendar_filing_evidence
from ._overview_calendar_support import (
    _SOURCE_URL,
    PRIMARY_PROFILE_ID,
    _isolated_backend,
    _justificante_metadata,
    _modelo_record_with_external_justificante,
    _observed_casilla_observations,
)

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SECOND_PROFILE_ID = "22222222-2222-4222-8222-222222222222"


def test_local_calendar_filing_evidence_is_scoped_to_profile_storage_session() -> None:
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        filing_period=Period.from_year_and_code(2025, "1T"),
        observations=_observed_casilla_observations(Decimal("10.00")),
    )
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        CalculationObservationRepository().save(
            CalculationObservationRepository().prepare_observation_envelope(
                observation,
                source_kind="aeat_sede_justificante",
                captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "12345678901234567890",
                    "authenticated_identity": "X1234567L",
                },
            )
        )
        artefact_body = b"modelo-303-2025-1T-justificante"
        store = FiledDeclaracionObservationStore(load_settings().cadrumo_filed_declarations_dir)
        artefact = store.persist_artefact(
            ("303", 2025, Period.from_year_and_code(2025, "1T"), "12345678901234567890"),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=_SOURCE_URL,
                content_type="application/pdf",
                byte_count=len(artefact_body),
                sha256=hashlib.sha256(artefact_body).hexdigest(),
                captured_at=datetime(2025, 4, 16, 12, 1, tzinfo=UTC),
            ),
            artefact_body,
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="303",
                ejercicio=2025,
                period=Period.from_year_and_code(2025, "1T"),
                expediente_id="12345678901234567890",
                status="ALTA",
                presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                authenticated_identity="X1234567L",
                artefacts=(artefact,),
            ),
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="303",
                ejercicio=2025,
                period=Period.from_year_and_code(2025, "2T"),
                expediente_id="12345678901234567891",
                status="ALTA",
                presented_at=datetime(2025, 7, 15, 9, 30, tzinfo=UTC),
                authenticated_identity="X1234567L",
                artefacts=(
                    FiledDeclaracionArtefact(
                        kind="justificante_pdf",
                        source_url=_SOURCE_URL,
                        content_type="application/pdf",
                        byte_count=32,
                        sha256="f" * 64,
                        captured_at=datetime(2025, 7, 16, 12, 1, tzinfo=UTC),
                        storage_ref="secure-object:financial:" + "f" * 64,
                    ),
                ),
            ),
        )
        wrong_identity_body = b"modelo-303-2025-3T-justificante"
        wrong_identity_artefact = store.persist_artefact(
            ("303", 2025, Period.from_year_and_code(2025, "3T"), "12345678901234567892"),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=_SOURCE_URL,
                content_type="application/pdf",
                byte_count=len(wrong_identity_body),
                sha256=hashlib.sha256(wrong_identity_body).hexdigest(),
                captured_at=datetime(2025, 10, 16, 12, 1, tzinfo=UTC),
            ),
            wrong_identity_body,
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="303",
                ejercicio=2025,
                period=Period.from_year_and_code(2025, "3T"),
                expediente_id="12345678901234567892",
                status="ALTA",
                presented_at=datetime(2025, 10, 15, 9, 30, tzinfo=UTC),
                authenticated_identity="Y7654321G",
                artefacts=(wrong_identity_artefact,),
            ),
        )
        non_active_body = b"modelo-303-2025-4T-non-active-justificante"
        non_active_artefact = store.persist_artefact(
            ("303", 2025, Period.from_year_and_code(2025, "4T"), "12345678901234567893"),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=_SOURCE_URL,
                content_type="application/pdf",
                byte_count=len(non_active_body),
                sha256=hashlib.sha256(non_active_body).hexdigest(),
                captured_at=datetime(2026, 1, 16, 12, 1, tzinfo=UTC),
            ),
            non_active_body,
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="303",
                ejercicio=2025,
                period=Period.from_year_and_code(2025, "4T"),
                expediente_id="12345678901234567893",
                status="BAJA",
                presented_at=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
                authenticated_identity="X1234567L",
                artefacts=(non_active_artefact,),
            ),
        )

    with open_test_profile_session(_SECOND_PROFILE_ID):
        register_minimal_profile(profile_id=_SECOND_PROFILE_ID, display_name="Second Operator")

    with open_test_profile_session(_SECOND_PROFILE_ID):
        second_evidence, _second_notice = _local_calendar_filing_evidence(_SECOND_PROFILE_ID, ())
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        operator_evidence, _operator_notice = _local_calendar_filing_evidence(
            PRIMARY_PROFILE_ID,
            (),
            expected_tax_id="X1234567L",
        )

    assert second_evidence == ()
    by_period = {row.period: row for row in operator_evidence}
    assert sorted(
        (row.modelo, row.filing_year, row.period.registry_token) for row in operator_evidence if row.period is not None
    ) == [
        ("303", 2025, "1T"),
        ("303", 2025, "2T"),
    ]
    period_1t = Period.from_year_and_code(2025, "1T")
    period_2t = Period.from_year_and_code(2025, "2T")
    period_3t = Period.from_year_and_code(2025, "3T")
    period_4t = Period.from_year_and_code(2025, "4T")
    assert by_period[period_1t].aeat_submission_state.value == "submitted_observed"
    assert by_period[period_1t].justificante_verified is False
    assert by_period[period_2t].aeat_submission_state.value == "submitted_observed"
    assert by_period[period_2t].justificante_verified is False
    assert period_3t not in by_period
    assert period_4t not in by_period


def test_local_calendar_filing_evidence_requires_parseable_matching_filed_justificante() -> None:
    pdf_bytes = (FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf").read_bytes()
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        store = FiledDeclaracionObservationStore(load_settings().cadrumo_filed_declarations_dir)
        artefact = store.persist_artefact(
            ("130", 2026, Period.from_year_and_code(2026, "1T"), "202613000010001A"),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=_SOURCE_URL,
                content_type="application/pdf",
                byte_count=len(pdf_bytes),
                sha256=hashlib.sha256(pdf_bytes).hexdigest(),
                captured_at=datetime(2026, 4, 18, 12, 1, tzinfo=UTC),
            ),
            pdf_bytes,
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="130",
                ejercicio=2026,
                period=Period.from_year_and_code(2026, "1T"),
                expediente_id="202613000010001A",
                status="ALTA",
                presented_at=datetime(2026, 4, 18, 9, 30, tzinfo=UTC),
                authenticated_identity="00000000T",
                artefacts=(artefact,),
            ),
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="130",
                ejercicio=2026,
                period=Period.from_year_and_code(2026, "2T"),
                expediente_id="202613000010002A",
                status="ALTA",
                presented_at=datetime(2026, 7, 18, 9, 30, tzinfo=UTC),
                authenticated_identity="00000000T",
                artefacts=(artefact,),
            ),
        )

        evidence, _notice = _local_calendar_filing_evidence(
            PRIMARY_PROFILE_ID,
            (),
            expected_tax_id="00000000T",
        )

    matching = [
        row
        for row in evidence
        if row.modelo == "130" and row.filing_year == 2026 and row.period == Period.from_year_and_code(2026, "1T")
    ]
    assert len(matching) == 1
    assert matching[0].aeat_submission_state.value == "justificante_verified"
    assert matching[0].justificante_verified is True
    mismatched = [
        row
        for row in evidence
        if row.modelo == "130" and row.filing_year == 2026 and row.period == Period.from_year_and_code(2026, "2T")
    ]
    assert len(mismatched) == 1
    assert mismatched[0].aeat_submission_state.value == "submitted_observed"
    assert mismatched[0].justificante_verified is False


def test_local_calendar_filing_evidence_resolves_persisted_justificante_metadata() -> None:
    csv = "JUST3032025X1T7"
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        repo = ModeloRecordCatalogueRepository(bucket_id=PRIMARY_PROFILE_ID)
        repo.save(upsert_filing_record(repo.load(), _modelo_record_with_external_justificante(csv=csv)))
        JustificanteRepository().save(_justificante_metadata(csv=csv))

        evidence, _notice = _local_calendar_filing_evidence(
            PRIMARY_PROFILE_ID,
            (),
            expected_tax_id="X1234567L",
        )

    matching = [
        row
        for row in evidence
        if row.modelo == "303" and row.filing_year == 2025 and row.period == Period.from_year_and_code(2025, "1T")
    ]
    assert len(matching) == 1
    row = matching[0]
    assert row.local_filing_state.value == "external_baseline_imported"
    assert row.aeat_submission_state.value == "justificante_verified"
    assert row.aeat_evidence_kind == "aeat_justificante_pdf"
    assert row.justificante_verified is True
