"""CLI surface tests for ``aeat app overview calendar``."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter
from typer.testing import CliRunner

from ....adapters.outbound.aeat.sede import Declaracion
from ....adapters.outbound.aeat.sede._notifications import NotificationsSnapshot, RemoteNotification
from ....adapters.outbound.aeat.sede._observation_store import FiledDeclaracionObservationStore
from ....adapters.outbound.aeat.sede._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from ....application.calculations import CalculationObservationRepository
from ....application.live import ExpedientesCapture, ExpedientesService, NotificationsService
from ....application.user_profile._orchestration import profile_create_storage_span, profile_storage_session
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....domain.justificante import Justificante, JustificanteRepository
from ....domain.modelos import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloCode,
    ModeloRecord,
    ModeloRecordCatalogueRepository,
    ModeloRecordStatus,
    derive_filing_record_id,
    upsert_filing_record,
)
from ....tests.aeat_literal_fixtures import aeat_url, justificante_cotejo_url
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app
from .._overview import _local_calendar_filing_evidence

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SOURCE_URL = AnyHttpUrl(aeat_url("sede", "/"))
_WORK_UNIT_ID = "a" * 64
_CALCULATION_REVISION_ID = "b" * 64


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def _modelo_record_with_external_justificante(*, csv: str, bucket_id: str = "operator") -> ModeloRecord:
    filed_at = datetime(2025, 4, 16, 12, 0, tzinfo=UTC)
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_CALCULATION_REVISION_ID,
            filed_at=filed_at,
            filed_by="operator",
        ),
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        filed_at=filed_at,
        filed_by="operator",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id=csv,
            imported_at=filed_at,
        ),
    )


def _justificante_metadata(*, csv: str, tax_id: str = "X1234567L") -> Justificante:
    body = f"{csv}-pdf".encode()
    return Justificante(
        csv=csv,
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        ejercicio="2025",
        presentation_id=None,
        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        tax_id=tax_id,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
        source_pdf_sha256=hashlib.sha256(body).hexdigest(),
        parsed_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
    )


def test_calendar_requires_from_flag(cli_runner: CliRunner) -> None:
    """`--from` is required; missing it surfaces as Typer usage error."""

    result = cli_runner.invoke(app, ["app", "overview", "calendar", "--to", "2026-03-31"])
    assert result.exit_code != 0, result.output


def test_calendar_requires_to_flag(cli_runner: CliRunner) -> None:
    """`--to` is required; missing it surfaces as Typer usage error."""

    result = cli_runner.invoke(app, ["app", "overview", "calendar", "--from", "2026-01-01"])
    assert result.exit_code != 0, result.output


def test_calendar_rejects_malformed_date(cli_runner: CliRunner) -> None:
    """A non-ISO date in --from or --to is rejected before the service runs."""

    result = cli_runner.invoke(
        app,
        ["app", "overview", "calendar", "--from", "not-a-date", "--to", "2026-03-31"],
    )
    assert result.exit_code != 0, result.output


def test_calendar_renders_entries_for_q1_window(cli_runner: CliRunner) -> None:
    """A valid Q1 window over the minimal profile yields the entries
    header lines plus zero-or-more entry rows. With profile incomplete
    warnings present the verb still refuses without --allow-incomplete."""

    result_strict = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
        ],
    )
    # Minimal profile triggers completeness warnings; strict mode refuses.
    if result_strict.exit_code != 0:
        result_lax = cli_runner.invoke(
            app,
            [
                "app",
                "overview",
                "calendar",
                "--from",
                "2026-01-01",
                "--to",
                "2026-03-31",
                "--allow-incomplete",
            ],
        )
        assert result_lax.exit_code == 0, result_lax.output
        assert "from\t2026-01-01" in result_lax.output
        assert "to\t2026-03-31" in result_lax.output
        assert "entries\t" in result_lax.output
    else:
        # Profile was complete (unusual for minimal profile) — strict
        # mode rendered the calendar; assert the same anchors.
        assert "from\t2026-01-01" in result_strict.output
        assert "to\t2026-03-31" in result_strict.output


def test_calendar_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only` so the operator cannot
    mistake the verb for an AEAT-contacting probe."""

    result = cli_runner.invoke(app, ["app", "overview", "calendar", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_calendar_json_includes_local_live_snapshot_events(cli_runner: CliRunner) -> None:
    ExpedientesService().capture(
        bucket_id="operator",
        capture=ExpedientesCapture(
            declarations=(
                Declaracion(
                    modelo="303",
                    ejercicio=2025,
                    period=Period.from_year_and_code(2025, "1T"),
                    expediente_id="12345678901234567890",
                    estado="ALTA",
                    presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                ),
            ),
            captured_at=datetime(2025, 4, 15, 10, 0, tzinfo=UTC),
            source_url="declarations:modelo=303:ejercicio=2025",
        ),
    )
    NotificationsService().capture(
        bucket_id="operator",
        snapshot=NotificationsSnapshot(
            rows=(
                RemoteNotification(
                    certificado_id="2596230606502",
                    tipo="notificacion",
                    concepto="Requerimiento censal",
                    titular_nif="B12345678",
                    titular_nombre="Test S.L.",
                    destinatario_nif="B12345678",
                    destinatario_nombre="Test S.L.",
                    fecha_emision=date(2025, 4, 14),
                    fecha_notificacion=None,
                    leida=False,
                    source_url=_SOURCE_URL,
                ),
            ),
            captured_at=datetime(2025, 4, 14, 10, 0, tzinfo=UTC),
            source_url=_SOURCE_URL,
        ),
    )

    result = cli_runner.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "overview",
            "calendar",
            "--from",
            "2025-04-01",
            "--to",
            "2025-04-30",
            "--allow-incomplete",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    events = payload["result"]["events"]
    assert {(event["event_type"], event["reference_id"]) for event in events} == {
        ("filing", "12345678901234567890"),
        ("message", "2596230606502"),
    }
    filing_event = next(event for event in events if event["reference_id"] == "12345678901234567890")
    assert filing_event["aeat_submission_state"] == "submitted_observed"
    assert filing_event["justificante_verified"] is False


def test_local_calendar_filing_evidence_is_scoped_to_profile_storage_session() -> None:
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        filing_period=Period.from_year_and_code(2025, "1T"),
        observations=(CasillaObservation(casilla_id="01", value=Decimal("10.00")),),
    )
    with profile_storage_session("operator"):
        CalculationObservationRepository().save_observation(
            observation,
            source_kind="aeat_sede_justificante",
            captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
        )
        artefact_body = b"modelo-303-2025-1T-justificante"
        store = FiledDeclaracionObservationStore(Path("var/aeat/filed-declarations"))
        artefact = store.persist_artefact(
            ("303", 2025, "1T", "12345678901234567890"),
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
            ("303", 2025, "3T", "12345678901234567892"),
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
                authenticated_identity="Y7654321Z",
                artefacts=(wrong_identity_artefact,),
            ),
        )
        non_active_body = b"modelo-303-2025-4T-non-active-justificante"
        non_active_artefact = store.persist_artefact(
            ("303", 2025, "4T", "12345678901234567893"),
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

    with profile_create_storage_span("second"):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="second",
                display_name="Second Operator",
                enforce_unique_tax_id=False,
            ),
        )

    with profile_storage_session("second"):
        second_evidence = _local_calendar_filing_evidence("second", ())
    with profile_storage_session("operator"):
        operator_evidence = _local_calendar_filing_evidence("operator", (), expected_tax_id="X1234567L")

    assert second_evidence == ()
    by_period = {row.period: row for row in operator_evidence}
    assert sorted(
        (row.modelo, row.filing_year, row.period.registry_token) for row in operator_evidence
    ) == [
        ("303", 2025, "1T"),
        ("303", 2025, "2T"),
    ]
    period_1t = Period.from_year_and_code(2025, "1T")
    period_2t = Period.from_year_and_code(2025, "2T")
    period_3t = Period.from_year_and_code(2025, "3T")
    period_4t = Period.from_year_and_code(2025, "4T")
    assert by_period[period_1t].aeat_submission_state.value == "justificante_verified"
    assert by_period[period_1t].justificante_verified is True
    assert by_period[period_2t].aeat_submission_state.value == "submitted_observed"
    assert by_period[period_2t].justificante_verified is False
    assert period_3t not in by_period
    assert period_4t not in by_period


def test_local_calendar_filing_evidence_resolves_persisted_justificante_metadata() -> None:
    csv = "JUST-303-2025-1T"
    with profile_storage_session("operator"):
        repo = ModeloRecordCatalogueRepository(bucket_id="operator")
        repo.save(upsert_filing_record(repo.load(), _modelo_record_with_external_justificante(csv=csv)))
        JustificanteRepository().save(_justificante_metadata(csv=csv))

        evidence = _local_calendar_filing_evidence(
            "operator",
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


def test_all_profiles_flag_iterates_every_registered_profile(cli_runner: CliRunner) -> None:
    """--all-profiles iterates every registered profile.

    Two profiles are registered; the flag must emit a `profile` header
    line for each one. The test does not assert specific obligation rows
    because the minimal fixture leaves the taxpayer model undeclared;
    --allow-incomplete is required to get any output at all.
    """

    with profile_create_storage_span("second"):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="second",
                display_name="Second Operator",
                enforce_unique_tax_id=False,
            ),
        )

    result = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--all-profiles",
            "--allow-incomplete",
        ],
    )
    assert result.exit_code == 0, result.output
    # Both profile labels must appear in the output.
    assert "operator" in result.output
    assert "Second Operator" in result.output
    # Output is structured with per-profile header lines.
    profile_lines = [line for line in result.output.splitlines() if line.startswith("profile\t")]
    assert len(profile_lines) == 2, f"expected 2 profile header lines, got: {result.output}"
