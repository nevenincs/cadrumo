"""CLI surface tests for ``aeat app overview calendar``."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.outbound.aeat.sede import Declaracion
from ....adapters.outbound.aeat.sede._notifications import NotificationsSnapshot, RemoteNotification
from ....adapters.persistence.storage import SensitivityClass
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....application.live import ExpedientesCapture, ExpedientesService, NotificationsService
from ....application.user_profile._orchestration import profile_create_storage_span, profile_storage_session
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
from ....core.time import now
from ....domain.justificante import JustificanteRepository
from ....domain.modelos import (
    ExternalEvidenceKind,
    ModeloRecordCatalogueRepository,
    upsert_filing_record,
)
from ....tests.cli_runner import invoke_cached_cli
from ._overview_calendar_support import (
    _SOURCE_URL,
    _justificante_metadata,
    _modelo_record_with_external_justificante,
    _stamp_calendar_enrolment_from_censo,
    isolated_calendar_backend,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_calendar_backend(tmp_path):
        yield


_INVALID_CALENDAR_CLI_ARGS = (
    pytest.param(["app", "overview", "calendar", "--to", "2026-03-31"], id="missing-from"),
    pytest.param(["app", "overview", "calendar", "--from", "2026-01-01"], id="missing-to"),
    pytest.param(
        ["app", "overview", "calendar", "--from", "not-a-date", "--to", "2026-03-31"],
        id="malformed-from-date",
    ),
)


@pytest.mark.parametrize("args", _INVALID_CALENDAR_CLI_ARGS)
def test_calendar_rejects_invalid_invocation(args: list[str]) -> None:
    result = _invoke(args)
    assert result.exit_code != 0, result.output


def test_calendar_renders_entries_for_q1_window() -> None:
    """A valid Q1 window over the minimal profile yields the entries
    header lines plus zero-or-more entry rows. With profile incomplete
    warnings present the verb still refuses without --allow-incomplete."""

    result_strict = _invoke(
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
        result_lax = _invoke(
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


def test_calendar_blocks_profile_derived_enrolment_without_live_censo() -> None:
    result = _invoke(
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

    lax = _invoke(
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


def test_calendar_accepts_censo_stamped_enrolment() -> None:
    _stamp_calendar_enrolment_from_censo()

    result = _invoke(
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
    extra_args: tuple[str, ...],
    assert_no_profile_skipped: bool,
) -> None:
    _store_corrupt_local_filing_evidence()

    result = _invoke(
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


def test_calendar_help_advertises_local_only() -> None:
    """Help text must signal `local-only` so the operator cannot
    mistake the verb for an AEAT-contacting probe."""

    result = _invoke(["app", "overview", "calendar", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_calendar_json_includes_local_live_snapshot_events() -> None:
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

    result = _invoke(
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


def test_calendar_strict_mode_refuses_unverified_aeat_filing() -> None:
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

    strict = _invoke(
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

    lax = _invoke(
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


def test_calendar_strict_mode_refuses_conflicting_aeat_evidence_references() -> None:
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

    strict = _invoke(
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

    lax_json = _invoke(
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

    lax_text = _invoke(
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


def test_calendar_all_profiles_strict_mode_refuses_conflicting_aeat_evidence_references() -> None:
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

    strict = _invoke(
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

    lax = _invoke(
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


def test_calendar_strict_mode_refuses_imported_csv_register_without_justificante() -> None:
    _stamp_calendar_enrolment_from_censo()
    csv = "CSVREG-303-2025-1T"
    record = _modelo_record_with_external_justificante(
        csv=csv,
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
    )
    with profile_storage_session("operator"):
        repo = ModeloRecordCatalogueRepository(bucket_id="operator")
        repo.save(upsert_filing_record(repo.load(), record))

    strict = _invoke(
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

    lax = _invoke(
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


def test_calendar_text_output_names_verified_aeat_evidence() -> None:
    csv = "JUST-303-2025-1T"
    record = _modelo_record_with_external_justificante(csv=csv)
    _stamp_calendar_enrolment_from_censo()
    with profile_storage_session("operator"):
        repo = ModeloRecordCatalogueRepository(bucket_id="operator")
        repo.save(upsert_filing_record(repo.load(), record))
        JustificanteRepository().save(_justificante_metadata(csv=csv, tax_id="88874275K"))

    result = _invoke(
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


def test_all_profiles_flag_iterates_every_registered_profile() -> None:
    """--all-profiles iterates every registered profile.

    Two profiles are registered; the flag must emit a `profile` header
    line for each one. The test does not assert specific obligation rows
    because the minimal fixture leaves the taxpayer model undeclared;
    --allow-incomplete is required to get any output at all.
    """

    with profile_create_storage_span("22222222-2222-4222-8222-222222222222"):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="22222222-2222-4222-8222-222222222222",
                display_name="Second Operator",
                enforce_unique_tax_id=False,
            ),
        )

    result = _invoke(
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
