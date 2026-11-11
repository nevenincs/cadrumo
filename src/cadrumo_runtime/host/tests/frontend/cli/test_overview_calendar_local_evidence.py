"""Local filing evidence resolver tests for overview calendar output."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from cadrumo.adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.observed_header_fact import ObservedHeaderFact
from cadrumo.core.period import Period
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.filing_repository import upsert_filing_record
from cadrumo.entrypoints.overview_evidence_composition import local_calendar_filing_evidence
from cadrumo.tests.inventory import FIXTURES_DIR

from .overview_calendar_support import (
    PRIMARY_PROFILE_ID,
    SOURCE_URL,
    isolated_backend,
    justificante_metadata,
    modelo_record_with_external_justificante,
)

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SECOND_PROFILE_ID = "22222222-2222-4222-8222-222222222222"
_YEAR = filing_year_envelope().horizon
_MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
#: The ejercicio the receipt fixture prints, read off its own name so the observations seeded for it
#: address the exercise the document declares.
_FIXTURE_YEAR = int(_MODELO_130_FIXTURE.stem.rpartition("_")[2][:4])


def _registry_snapshot_ref(*, modelo: str, filing_year: int, period: Period) -> RegistrySnapshotRef:
    return published_snapshot(
        modelo,
        filing_year=filing_year,
        period=period.registry_token,
    ).snapshot_ref


def test_local_calendar_filing_evidence_is_scoped_to_profile_storage_session() -> None:
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=_YEAR,
        period="1T",
        filing_period=Period.from_year_and_code(_YEAR, "1T"),
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=_YEAR,
            period="1T",
            casilla_values={validated_casilla_id("iva.resultado"): Decimal("10.00")},
        ),
    )
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        CalculationObservationRepository().save(
            CalculationObservationRepository().prepare_observation_envelope(
                observation,
                source_kind="aeat_sede_justificante",
                captured_at=datetime(_YEAR, 4, 16, 12, 0, tzinfo=UTC),
                stamped_revision_id=str(published_snapshot("303", filing_year=_YEAR, period="1T").revision.id),
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "12345678901234567890",
                    "authenticated_identity": "X0001500M",
                },
                source_headers=(
                    ObservedHeaderFact(
                        header_key="filing.result_disposition",
                        value="I",
                        source_artefact_kind="submitted_file",
                        source_locator="overview-calendar-local-evidence:declaration-type",
                    ),
                ),
            )
        )
        artefact_body = f"modelo-303-{_YEAR}-1T-justificante".encode()
        store = FiledDeclaracionObservationStore(storage_path(StorageCategory.FILED_DECLARATIONS))
        artefact = store.persist_artefact(
            ("303", _YEAR, Period.from_year_and_code(_YEAR, "1T"), "12345678901234567890"),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=SOURCE_URL,
                content_type="application/pdf",
                byte_count=len(artefact_body),
                sha256=hashlib.sha256(artefact_body).hexdigest(),
                captured_at=datetime(_YEAR, 4, 16, 12, 1, tzinfo=UTC),
            ),
            artefact_body,
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="303",
                ejercicio=_YEAR,
                period=Period.from_year_and_code(_YEAR, "1T"),
                expediente_id="12345678901234567890",
                status="ALTA",
                presented_at=datetime(_YEAR, 4, 15, 9, 30, tzinfo=UTC),
                authenticated_identity="X0001500M",
                artefacts=(artefact,),
                registry_snapshot_ref=_registry_snapshot_ref(
                    modelo="303", filing_year=_YEAR, period=Period.from_year_and_code(_YEAR, "1T")
                ),
            ),
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="303",
                ejercicio=_YEAR,
                period=Period.from_year_and_code(_YEAR, "2T"),
                expediente_id="12345678901234567891",
                status="ALTA",
                presented_at=datetime(_YEAR, 7, 15, 9, 30, tzinfo=UTC),
                authenticated_identity="X0001500M",
                artefacts=(
                    FiledDeclaracionArtefact(
                        kind="justificante_pdf",
                        source_url=SOURCE_URL,
                        content_type="application/pdf",
                        byte_count=32,
                        sha256="f" * 64,
                        captured_at=datetime(_YEAR, 7, 16, 12, 1, tzinfo=UTC),
                        storage_ref="secure-object:financial:" + "f" * 64,
                    ),
                ),
                registry_snapshot_ref=_registry_snapshot_ref(
                    modelo="303", filing_year=_YEAR, period=Period.from_year_and_code(_YEAR, "2T")
                ),
            ),
        )
        wrong_identity_body = f"modelo-303-{_YEAR}-3T-justificante".encode()
        wrong_identity_artefact = store.persist_artefact(
            ("303", _YEAR, Period.from_year_and_code(_YEAR, "3T"), "12345678901234567892"),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=SOURCE_URL,
                content_type="application/pdf",
                byte_count=len(wrong_identity_body),
                sha256=hashlib.sha256(wrong_identity_body).hexdigest(),
                captured_at=datetime(_YEAR, 10, 16, 12, 1, tzinfo=UTC),
            ),
            wrong_identity_body,
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="303",
                ejercicio=_YEAR,
                period=Period.from_year_and_code(_YEAR, "3T"),
                expediente_id="12345678901234567892",
                status="ALTA",
                presented_at=datetime(_YEAR, 10, 15, 9, 30, tzinfo=UTC),
                authenticated_identity="Y0001503E",
                artefacts=(wrong_identity_artefact,),
                registry_snapshot_ref=_registry_snapshot_ref(
                    modelo="303", filing_year=_YEAR, period=Period.from_year_and_code(_YEAR, "3T")
                ),
            ),
        )
        non_active_body = f"modelo-303-{_YEAR}-4T-non-active-justificante".encode()
        non_active_artefact = store.persist_artefact(
            ("303", _YEAR, Period.from_year_and_code(_YEAR, "4T"), "12345678901234567893"),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=SOURCE_URL,
                content_type="application/pdf",
                byte_count=len(non_active_body),
                sha256=hashlib.sha256(non_active_body).hexdigest(),
                captured_at=datetime(_YEAR + 1, 1, 16, 12, 1, tzinfo=UTC),
            ),
            non_active_body,
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="303",
                ejercicio=_YEAR,
                period=Period.from_year_and_code(_YEAR, "4T"),
                expediente_id="12345678901234567893",
                status="BAJA",
                presented_at=datetime(_YEAR + 1, 1, 15, 9, 30, tzinfo=UTC),
                authenticated_identity="X0001500M",
                artefacts=(non_active_artefact,),
                registry_snapshot_ref=_registry_snapshot_ref(
                    modelo="303", filing_year=_YEAR, period=Period.from_year_and_code(_YEAR, "4T")
                ),
            ),
        )

    with open_test_profile_session(_SECOND_PROFILE_ID):
        register_minimal_profile(profile_id=_SECOND_PROFILE_ID, display_name="Second Operator")

    with open_test_profile_session(_SECOND_PROFILE_ID), bundled_indexed_authority().operation() as operation:
        second_evidence, _second_notice = local_calendar_filing_evidence(
            _SECOND_PROFILE_ID,
            (),
            operation=operation,
        )
    with open_test_profile_session(PRIMARY_PROFILE_ID), bundled_indexed_authority().operation() as operation:
        operator_evidence, _operator_notice = local_calendar_filing_evidence(
            PRIMARY_PROFILE_ID,
            (),
            operation=operation,
            expected_tax_id="X0001500M",
        )

    assert second_evidence == ()
    by_period = {row.period: row for row in operator_evidence}
    assert sorted(
        (row.modelo, row.filing_year, row.period.registry_token) for row in operator_evidence if row.period is not None
    ) == [
        ("303", _YEAR, "1T"),
        ("303", _YEAR, "2T"),
        ("303", _YEAR, "4T"),
    ], operator_evidence
    period_1t = Period.from_year_and_code(_YEAR, "1T")
    period_2t = Period.from_year_and_code(_YEAR, "2T")
    period_3t = Period.from_year_and_code(_YEAR, "3T")
    period_4t = Period.from_year_and_code(_YEAR, "4T")
    assert by_period[period_1t].aeat_submission_state.value == "submitted_observed"
    assert by_period[period_1t].justificante_verified is False
    assert by_period[period_2t].aeat_submission_state.value == "submitted_observed"
    assert by_period[period_2t].justificante_verified is False
    assert period_3t not in by_period
    # An inactive register entry remains visible as a concern, without being
    # treated as an observed submission or a verified justificante.
    assert by_period[period_4t].aeat_submission_state.value == "not_observed"
    assert by_period[period_4t].justificante_verified is False
    assert [concern.value for concern in by_period[period_4t].aeat_evidence_concerns] == ["inactive_register"]


def test_local_calendar_filing_evidence_requires_parseable_matching_filed_justificante() -> None:
    pdf_bytes = (_MODELO_130_FIXTURE).read_bytes()
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        store = FiledDeclaracionObservationStore(storage_path(StorageCategory.FILED_DECLARATIONS))
        artefact = store.persist_artefact(
            ("130", _FIXTURE_YEAR, Period.from_year_and_code(_FIXTURE_YEAR, "1T"), f"{_FIXTURE_YEAR}13000010001A"),
            FiledDeclaracionArtefact(
                kind="justificante_pdf",
                source_url=SOURCE_URL,
                content_type="application/pdf",
                byte_count=len(pdf_bytes),
                sha256=hashlib.sha256(pdf_bytes).hexdigest(),
                captured_at=datetime(_FIXTURE_YEAR, 4, 18, 12, 1, tzinfo=UTC),
            ),
            pdf_bytes,
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="130",
                ejercicio=_FIXTURE_YEAR,
                period=Period.from_year_and_code(_FIXTURE_YEAR, "1T"),
                expediente_id=f"{_FIXTURE_YEAR}13000010001A",
                status="ALTA",
                presented_at=datetime(_FIXTURE_YEAR, 4, 18, 9, 30, tzinfo=UTC),
                authenticated_identity="00000000T",
                artefacts=(artefact,),
                registry_snapshot_ref=_registry_snapshot_ref(
                    modelo="130", filing_year=_FIXTURE_YEAR, period=Period.from_year_and_code(_FIXTURE_YEAR, "1T")
                ),
            ),
        )
        store.persist_observation(
            FiledDeclaracionObservation(
                modelo="130",
                ejercicio=_FIXTURE_YEAR,
                period=Period.from_year_and_code(_FIXTURE_YEAR, "2T"),
                expediente_id=f"{_FIXTURE_YEAR}13000010002A",
                status="ALTA",
                presented_at=datetime(_FIXTURE_YEAR, 7, 18, 9, 30, tzinfo=UTC),
                authenticated_identity="00000000T",
                artefacts=(artefact,),
                registry_snapshot_ref=_registry_snapshot_ref(
                    modelo="130", filing_year=_FIXTURE_YEAR, period=Period.from_year_and_code(_FIXTURE_YEAR, "2T")
                ),
            ),
        )

        with bundled_indexed_authority().operation() as operation:
            evidence, _notice = local_calendar_filing_evidence(
                PRIMARY_PROFILE_ID,
                (),
                operation=operation,
                expected_tax_id="00000000T",
            )

    matching = [
        row
        for row in evidence
        if row.modelo == "130"
        and row.filing_year == _FIXTURE_YEAR
        and row.period == Period.from_year_and_code(_FIXTURE_YEAR, "1T")
    ]
    assert len(matching) == 1
    assert matching[0].aeat_submission_state.value == "justificante_verified"
    assert matching[0].justificante_verified is True
    mismatched = [
        row
        for row in evidence
        if row.modelo == "130"
        and row.filing_year == _FIXTURE_YEAR
        and row.period == Period.from_year_and_code(_FIXTURE_YEAR, "2T")
    ]
    assert len(mismatched) == 1
    assert mismatched[0].aeat_submission_state.value == "submitted_observed"
    assert mismatched[0].justificante_verified is False


def test_local_calendar_filing_evidence_resolves_persisted_justificante_metadata() -> None:
    csv = "JUST3032025X1T7"
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        repo = ModeloRecordCatalogueRepository(bucket_id=PRIMARY_PROFILE_ID)
        repo.save(upsert_filing_record(repo.load(), modelo_record_with_external_justificante(csv=csv)))
        JustificanteRepository().save(justificante_metadata(csv=csv))

        with bundled_indexed_authority().operation() as operation:
            evidence, _notice = local_calendar_filing_evidence(
                PRIMARY_PROFILE_ID,
                (),
                operation=operation,
                expected_tax_id="X0001500M",
            )

    matching = [
        row
        for row in evidence
        if row.modelo == "303" and row.filing_year == _YEAR and row.period == Period.from_year_and_code(_YEAR, "1T")
    ]
    assert len(matching) == 1
    row = matching[0]
    assert row.local_filing_state.value == "external_baseline_imported"
    assert row.aeat_submission_state.value == "justificante_verified"
    assert row.aeat_evidence_kind == "aeat_justificante_pdf"
    assert row.justificante_verified is True
