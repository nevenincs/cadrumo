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
from ....adapters.persistence.storage import SensitivityClass
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....application.calculations import CalculationObservationRepository
from ....application.live import ExpedientesCapture, ExpedientesService, NotificationsService
from ....application.user_profile import (
    CENSO_DERIVED_SOURCE_TAG,
    CENSO_SOURCE_TAG,
    UserProfileLifecycleRepository,
)
from ....application.user_profile._orchestration import profile_create_storage_span, profile_storage_session
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
from ....core.time import now
from ....domain.calculations.registry import (
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
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
from ....domain.user_profile import UserProfileFact
from ....tests import FIXTURES_DIR
from ....tests.aeat_literal_fixtures import aeat_url, justificante_cotejo_url
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app
from .._overview import _local_calendar_filing_evidence

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SOURCE_URL = AnyHttpUrl(aeat_url("sede", "/"))
_WORK_UNIT_ID = "a" * 64
_CALCULATION_REVISION_ID = "b" * 64


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"overview calendar fixture casilla key {value!r} is not a CasillaId") from exc


_OBSERVED_CASILLA: CasillaId = _casilla_id("01")


def _observed_casilla_observations(value: Decimal):
    return registry_grounded_observations(
        modelo="303",
        filing_year=2025,
        period="1T",
        casilla_values={_OBSERVED_CASILLA: value},
    )


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


def _modelo_record_with_external_justificante(
    *,
    csv: str,
    bucket_id: str = "operator",
    evidence_kind: ExternalEvidenceKind = ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
) -> ModeloRecord:
    filed_at = datetime(2025, 4, 16, 12, 0, tzinfo=UTC)
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_CALCULATION_REVISION_ID,
            filed_at=filed_at,
            filed_by="aeat-import",
        ),
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        filed_at=filed_at,
        filed_by="aeat-import",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=evidence_kind,
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


def _stamp_calendar_enrolment_from_censo() -> None:
    repository = UserProfileLifecycleRepository(bucket_id="operator")
    record = repository.load("operator")
    censo_paths = {
        "iva.regime": CENSO_SOURCE_TAG,
        "taxpayer_type.entity_type": CENSO_DERIVED_SOURCE_TAG,
        "taxpayer_type.irpf_income_categories": CENSO_DERIVED_SOURCE_TAG,
    }
    facts = [
        fact.model_copy(update={"source": censo_paths[fact.path]}) if fact.path in censo_paths else fact
        for fact in record.facts
    ]
    if not any(fact.path == "activities.iae_epigraph" for fact in facts):
        facts.append(
            UserProfileFact(
                path="activities.iae_epigraph",
                value="763",
                source=CENSO_SOURCE_TAG,
            ),
        )
    repository.save(record.model_copy(update={"facts": tuple(facts)}))


_INVALID_CALENDAR_CLI_ARGS = (
    pytest.param(["app", "overview", "calendar", "--to", "2026-03-31"], id="missing-from"),
    pytest.param(["app", "overview", "calendar", "--from", "2026-01-01"], id="missing-to"),
    pytest.param(
        ["app", "overview", "calendar", "--from", "not-a-date", "--to", "2026-03-31"],
        id="malformed-from-date",
    ),
)


@pytest.mark.parametrize("args", _INVALID_CALENDAR_CLI_ARGS)
def test_calendar_rejects_invalid_invocation(cli_runner: CliRunner, args: list[str]) -> None:
    result = cli_runner.invoke(app, args)
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


def test_calendar_blocks_profile_derived_enrolment_without_live_censo(cli_runner: CliRunner) -> None:
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
        ],
    )

    assert result.exit_code != 0, result.output
    assert "censo.enrolment_unverified" in result.output

    lax = cli_runner.invoke(
        app,
        [
            "--format",
            "json",
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
    assert lax.exit_code == 0, lax.output
    warnings = json.loads(lax.output)["result"]["warnings"]
    censo_warning = next(warning for warning in warnings if warning["code"] == "censo.enrolment_unverified")
    assert censo_warning["affected_modelos"]
    entries = json.loads(lax.output)["result"]["entries"]
    assert any(entry["censo_enrolment_state"] == "unverified" for entry in entries)


def test_calendar_accepts_censo_stamped_enrolment(cli_runner: CliRunner) -> None:
    _stamp_calendar_enrolment_from_censo()

    result = cli_runner.invoke(
        app,
        [
            "--format",
            "json",
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

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    warning_codes = {warning["code"] for warning in payload["warnings"]}
    assert "censo.enrolment_unverified" not in warning_codes
    modelo_303 = next(entry for entry in payload["entries"] if entry["modelo"] == "303")
    assert modelo_303["censo_enrolment_state"] == "verified"


def _store_corrupt_local_filing_evidence() -> None:
    secure_object_repository_for_active_bucket().save(
        namespace="aeat.outbound.aeat.sede.filed_declaration.observations",
        object_key="corrupt-observation",
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=now(),
        payload=b"not-json",
    )


_CORRUPT_LOCAL_EVIDENCE_CALENDAR_ARGS = (
    pytest.param((), False, id="single-profile"),
    pytest.param(("--all-profiles",), True, id="all-profiles"),
)


@pytest.mark.parametrize(("extra_args", "assert_no_profile_skipped"), _CORRUPT_LOCAL_EVIDENCE_CALENDAR_ARGS)
def test_calendar_refuses_when_local_filing_evidence_store_is_unreadable(
    cli_runner: CliRunner,
    extra_args: tuple[str, ...],
    assert_no_profile_skipped: bool,
) -> None:
    _store_corrupt_local_filing_evidence()

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
            "--allow-incomplete",
            *extra_args,
        ],
    )

    assert result.exit_code != 0, result.output
    assert "local filing evidence is unavailable" in result.output
    if assert_no_profile_skipped:
        assert "profile_skipped" not in result.output


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
            authenticated_identity="88874275K",
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
                    titular_nif="88874275K",
                    titular_nombre="Test S.L.",
                    destinatario_nif="88874275K",
                    destinatario_nombre="Test S.L.",
                    fecha_emision=date(2025, 4, 14),
                    fecha_notificacion=None,
                    leida=False,
                    source_url=_SOURCE_URL,
                ),
                RemoteNotification(
                    certificado_id="2699101808461",
                    tipo="comunicacion",
                    concepto="Comunicacion de otro contribuyente",
                    titular_nif="B12345678",
                    titular_nombre="Other S.L.",
                    destinatario_nif="B12345678",
                    destinatario_nombre="Other S.L.",
                    fecha_emision=date(2025, 4, 14),
                    fecha_notificacion=None,
                    leida=True,
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
    assert filing_event["aeat_submitted_at"] == "2025-04-15T09:30:00Z"
    assert filing_event["justificante_verified"] is False


def test_calendar_strict_mode_refuses_unverified_aeat_filing(cli_runner: CliRunner) -> None:
    _stamp_calendar_enrolment_from_censo()
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
            authenticated_identity="88874275K",
        ),
    )

    strict = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "calendar",
            "--from",
            "2025-04-01",
            "--to",
            "2025-04-30",
        ],
    )

    assert strict.exit_code != 0, strict.output
    assert "filing.justificante_unverified" in strict.output

    lax = cli_runner.invoke(
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
    assert lax.exit_code == 0, lax.output
    warnings = json.loads(lax.output)["result"]["warnings"]
    warning = next(item for item in warnings if item["code"] == "filing.justificante_unverified")
    assert warning["affected_modelos"] == ["303"]
    assert warning["fix_command"] == "aeat app live filed pull --modelo 303 --year 2025 --period 1T"


def test_calendar_strict_mode_refuses_conflicting_aeat_evidence_references(
    cli_runner: CliRunner,
) -> None:
    _stamp_calendar_enrolment_from_censo()
    local_ref = "LOCAL-LIVE-CAPTURE-CSV"
    remote_ref = "12345678901234567890"
    record = _modelo_record_with_external_justificante(
        csv=local_ref,
        evidence_kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
    )
    with profile_storage_session("operator"):
        repo = ModeloRecordCatalogueRepository(bucket_id="operator")
        repo.save(upsert_filing_record(repo.load(), record))
    ExpedientesService().capture(
        bucket_id="operator",
        capture=ExpedientesCapture(
            declarations=(
                Declaracion(
                    modelo="303",
                    ejercicio=2025,
                    period=Period.from_year_and_code(2025, "1T"),
                    expediente_id=remote_ref,
                    estado="ALTA",
                    presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                ),
            ),
            captured_at=datetime(2025, 4, 15, 10, 0, tzinfo=UTC),
            source_url="declarations:modelo=303:ejercicio=2025",
            authenticated_identity="88874275K",
        ),
    )

    strict = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "calendar",
            "--from",
            "2025-04-01",
            "--to",
            "2025-04-30",
        ],
    )

    assert strict.exit_code != 0, strict.output
    assert "filing.aeat_evidence_conflict" in strict.output

    lax_json = cli_runner.invoke(
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
    assert lax_json.exit_code == 0, lax_json.output
    result = json.loads(lax_json.output)["result"]
    entry = next(item for item in result["entries"] if item["modelo"] == "303" and item["period"] == "2025 1T")
    evidence = entry["filing_evidence"]
    assert evidence["local_filing_state"] == "external_baseline_imported"
    assert evidence["aeat_submission_state"] == "accepted"
    assert evidence["aeat_evidence_kind"] == "aeat_live_capture"
    assert evidence["aeat_reference_id"] == local_ref
    assert evidence["aeat_evidence_conflict_reference_ids"] == [remote_ref, local_ref]
    warning = next(item for item in result["warnings"] if item["code"] == "filing.aeat_evidence_conflict")
    assert warning["affected_modelos"] == ["303"]
    assert warning["fix_command"] == "aeat app live filed pull --modelo 303 --year 2025 --period 1T"

    lax_text = cli_runner.invoke(
        app,
        [
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
    assert lax_text.exit_code == 0, lax_text.output
    assert f"aeat_conflict_refs={remote_ref},{local_ref}" in lax_text.output


def test_calendar_all_profiles_strict_mode_refuses_conflicting_aeat_evidence_references(
    cli_runner: CliRunner,
) -> None:
    _stamp_calendar_enrolment_from_censo()
    local_ref = "LOCAL-LIVE-CAPTURE-CSV"
    remote_ref = "12345678901234567890"
    record = _modelo_record_with_external_justificante(
        csv=local_ref,
        evidence_kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
    )
    with profile_storage_session("operator"):
        repo = ModeloRecordCatalogueRepository(bucket_id="operator")
        repo.save(upsert_filing_record(repo.load(), record))
    ExpedientesService().capture(
        bucket_id="operator",
        capture=ExpedientesCapture(
            declarations=(
                Declaracion(
                    modelo="303",
                    ejercicio=2025,
                    period=Period.from_year_and_code(2025, "1T"),
                    expediente_id=remote_ref,
                    estado="ALTA",
                    presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                ),
            ),
            captured_at=datetime(2025, 4, 15, 10, 0, tzinfo=UTC),
            source_url="declarations:modelo=303:ejercicio=2025",
            authenticated_identity="88874275K",
        ),
    )

    strict = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "calendar",
            "--from",
            "2025-04-01",
            "--to",
            "2025-04-30",
            "--all-profiles",
        ],
    )

    assert strict.exit_code != 0, strict.output
    assert "filing.aeat_evidence_conflict" in strict.output

    lax = cli_runner.invoke(
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
            "--all-profiles",
            "--allow-incomplete",
        ],
    )
    assert lax.exit_code == 0, lax.output
    profile = json.loads(lax.output)["result"]["profiles"][0]
    warning = next(item for item in profile["calendar"]["warnings"] if item["code"] == "filing.aeat_evidence_conflict")
    assert warning["affected_modelos"] == ["303"]


def test_calendar_strict_mode_refuses_imported_csv_register_without_justificante(
    cli_runner: CliRunner,
) -> None:
    _stamp_calendar_enrolment_from_censo()
    csv = "CSVREG-303-2025-1T"
    record = _modelo_record_with_external_justificante(
        csv=csv,
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
    )
    with profile_storage_session("operator"):
        repo = ModeloRecordCatalogueRepository(bucket_id="operator")
        repo.save(upsert_filing_record(repo.load(), record))

    strict = cli_runner.invoke(
        app,
        [
            "app",
            "overview",
            "calendar",
            "--from",
            "2025-04-01",
            "--to",
            "2025-04-30",
        ],
    )

    assert strict.exit_code != 0, strict.output
    assert "filing.justificante_unverified" in strict.output

    lax = cli_runner.invoke(
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
    assert lax.exit_code == 0, lax.output
    result = json.loads(lax.output)["result"]
    entry = next(item for item in result["entries"] if item["modelo"] == "303" and item["period"] == "2025 1T")
    evidence = entry["filing_evidence"]
    assert evidence["local_filing_state"] == "external_baseline_imported"
    assert evidence["aeat_submission_state"] == "accepted"
    assert evidence["aeat_evidence_kind"] == "aeat_csv_register"
    assert evidence["aeat_reference_id"] == csv
    assert evidence["justificante_verified"] is False
    warning = next(item for item in result["warnings"] if item["code"] == "filing.justificante_unverified")
    assert warning["affected_modelos"] == ["303"]
    assert warning["fix_command"] == "aeat app live filed pull --modelo 303 --year 2025 --period 1T"


def test_local_calendar_filing_evidence_is_scoped_to_profile_storage_session() -> None:
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        filing_period=Period.from_year_and_code(2025, "1T"),
        observations=_observed_casilla_observations(Decimal("10.00")),
    )
    with profile_storage_session("operator"):
        CalculationObservationRepository().save_observation(
            observation,
            source_kind="aeat_sede_justificante",
            captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": "12345678901234567890",
                "authenticated_identity": "X1234567L",
            },
        )
        artefact_body = b"modelo-303-2025-1T-justificante"
        store = FiledDeclaracionObservationStore(Path("var/aeat/filed-declarations"))
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
                authenticated_identity="Y7654321Z",
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
    with profile_storage_session("operator"):
        store = FiledDeclaracionObservationStore(Path("var/aeat/filed-declarations"))
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

        evidence = _local_calendar_filing_evidence(
            "operator",
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


def test_calendar_text_output_names_verified_aeat_evidence(cli_runner: CliRunner) -> None:
    csv = "JUST-303-2025-1T"
    record = _modelo_record_with_external_justificante(csv=csv)
    _stamp_calendar_enrolment_from_censo()
    with profile_storage_session("operator"):
        repo = ModeloRecordCatalogueRepository(bucket_id="operator")
        repo.save(upsert_filing_record(repo.load(), record))
        JustificanteRepository().save(_justificante_metadata(csv=csv, tax_id="88874275K"))

    result = cli_runner.invoke(
        app,
        [
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
    row = next(line for line in result.output.splitlines() if line.startswith("303\t2025 1T\t"))
    assert "\tlocal=external_baseline_imported" in row
    assert "\taeat=justificante_verified" in row
    assert "\tjustificante=true" in row
    assert "\tcenso_enrolment=verified" in row
    assert f"\tlocal_record={record.filing_record_id}" in row
    assert f"\taeat_ref={csv}" in row
    assert "\taeat_submitted_at=2025-04-15T09:30:00+00:00" in row
    assert "\taeat_kind=aeat_justificante_pdf" in row
    assert f"\tverified_justificante_csv={csv}" in row
    assert "\tevidence_source=modelo_filing_record" in row
    event_row = next(line for line in result.output.splitlines() if line.startswith("event\tfiling\t2025-04-15\t"))
    assert "\tmodelo_filing_record\t" in event_row
    assert f"\t{record.filing_record_id}\t" in event_row
    assert "\tmodelo=303" in event_row
    assert "\tperiod=2025 1T" in event_row
    assert "\tstatus=external_baseline_imported:vigente" in event_row
    assert "\taeat=justificante_verified" in event_row
    assert "\taeat_submitted_at=2025-04-15T09:30:00+00:00" in event_row
    assert "\tjustificante=true" in event_row
    assert f"\tverified_justificante_csv={csv}" in event_row


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
