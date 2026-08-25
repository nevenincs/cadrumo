"""CLI surface tests for ``aeat app overview calendar``."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime

import pytest
from click.testing import Result

from ....adapters.outbound.aeat.sede import (
    Declaracion,
    NotificationsSnapshot,
    RemoteNotification,
)
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.storage import SensitivityClass
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....application.live.expedientes import (
    ExpedientesCapture,
    ExpedientesService,
)
from ....application.live.notifications import NotificationsService
from ....application.overview import OverviewCalendarRange, build_overview_calendar
from ....application.user_profile.projections import record_to_values
from ....core import Period
from ....core.config import override_settings
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n import clear_output_language_cache
from ....core.time import frozen_clock, now, today_madrid
from cadrumo.domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import (
    ExternalEvidenceKind,
    upsert_filing_record,
)
from ....domain.user_profile.values import ProfileSetupState
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_minimal_profile
from .._overview import _calendar_shift_reason_text, _live_censo_verified_profile_keys, _profile_to_taxpayer, _state
from ._overview_calendar_support import (
    _SOURCE_URL,
    PRIMARY_PROFILE_ID,
    _isolated_backend,
    _justificante_metadata,
    _modelo_record_with_external_justificante,
    _stamp_calendar_enrolment_from_censo,
)

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The pipe-joined choice set, bracket-agnostic: Typer renders a Choice
# metavar as `<es|en|ca|hu>` (older Typer used square brackets). Asserting
# the joined choices without the enclosing bracket proves the full accepted
# set is surfaced regardless of the bracket glyph.
_OUTPUT_LANGUAGE_CHOICE_LIST = "|".join(SUPPORTED_OUTPUT_LANGUAGES)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


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


def test_calendar_json_preserves_exact_modelo_303_2025_quarterly_coordinates() -> None:
    """The real CLI must expose four, and only four, M303 quarterly rows for 2025."""
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "calendar",
            "--from",
            "2025-01-01",
            "--to",
            "2026-02-28",
            "--allow-incomplete",
        ],
    )

    assert result.exit_code == 0, result.output
    entries = json.loads(result.output)["result"]["entries"]
    coordinates = tuple(
        (entry["modelo"], entry["period"])
        for entry in entries
        if entry["modelo"] == "303" and entry["period"].startswith("2025 ")
    )

    assert coordinates == (
        ("303", "2025 1T"),
        ("303", "2025 2T"),
        ("303", "2025 3T"),
        ("303", "2025 4T"),
    )


def test_calendar_json_matches_application_coordinates_for_every_supported_year() -> None:
    """Real CLI fleet parity consumes the canonical horizon and application projection."""
    with frozen_clock(now()):
        reference_today = today_madrid()
        current = _state()
        profile = _profile_to_taxpayer(current)
        record = current.active_profile_record()
        raw_values = record_to_values(record) if record is not None else None
        supported_years = bundled_authority().catalogues.supported_filing_years
        assert supported_years is not None

        for filing_year in supported_years.years:
            from_date = date(filing_year, 1, 1)
            to_date = date(filing_year + 1, 12, 31)
            result = _invoke(
                [
                    "--format",
                    "json",
                    "app",
                    "overview",
                    "calendar",
                    "--from",
                    from_date.isoformat(),
                    "--to",
                    to_date.isoformat(),
                    "--allow-incomplete",
                ],
            )
            assert result.exit_code == 0, result.output

            expected_calendar = build_overview_calendar(
                profile,
                OverviewCalendarRange(from_date=from_date, to_date=to_date),
                today=reference_today,
                raw_values=raw_values,
            )
            expected = tuple(
                (
                    entry.modelo,
                    str(entry.period),
                    entry.adjusted_closes_on.isoformat(),
                    entry.user_state.value,
                )
                for entry in expected_calendar.entries
                if entry.period.filing_year == filing_year
            )
            entries = json.loads(result.output)["result"]["entries"]
            actual = tuple(
                (
                    entry["modelo"],
                    entry["period"],
                    entry["adjusted_closes_on"],
                    entry["user_state"],
                )
                for entry in entries
                if entry["period"].startswith(f"{filing_year} ")
            )

            assert expected, filing_year
            assert actual == expected, filing_year


def test_calendar_text_localizes_shift_label_but_json_keeps_token() -> None:
    text_result = _invoke(
        [
            "app",
            "overview",
            "calendar",
            "--output-language",
            "en",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--allow-incomplete",
        ],
    )

    assert text_result.exit_code == 0, text_result.output
    row = next(line for line in text_result.output.splitlines() if line.startswith("303\t2025 4T\t"))
    assert "\tshift=Business day" in row
    assert "\tshift=business_day" not in row

    json_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "calendar",
            "--output-language",
            "en",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--allow-incomplete",
        ],
    )

    assert json_result.exit_code == 0, json_result.output
    entries = json.loads(json_result.output)["result"]["entries"]
    modelo_303 = next(entry for entry in entries if entry["modelo"] == "303" and entry["period"] == "2025 4T")
    detail = modelo_303["detail_action"]
    assert detail["action"]["action_id"] == "operator.overview.explain"
    assert detail["action"]["cli_path"] == ["app", "overview", "explain"]
    assert {binding["argument_name"]: binding["value"] for binding in detail["argument_bindings"]} == {
        "modelo": "303",
        "year": 2025,
    }


def test_calendar_shift_formatter_localizes_weekend_tokens() -> None:
    with override_settings(cadrumo_output_language="ca"):
        clear_output_language_cache()
        try:
            rendered = _calendar_shift_reason_text("sabado + Todos los Santos + domingo")
        finally:
            clear_output_language_cache()

    assert rendered == "Dissabte + Todos los Santos + Diumenge"
    assert "sabado" not in rendered
    assert "domingo" not in rendered

    with override_settings(cadrumo_output_language="es"):
        clear_output_language_cache()
        try:
            accented = _calendar_shift_reason_text("sabado + business_day")
        finally:
            clear_output_language_cache()

    assert accented == "Sábado + Día hábil"
    assert "Sabado" not in accented
    assert "Dia habil" not in accented


def _store_corrupt_local_filing_evidence() -> None:
    secure_object_repository_for_active_bucket().save(
        namespace="cadrumo.outbound.aeat.sede.filed_declaration.observations",
        object_key="corrupt-observation",
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=now(),
        payload=b"not-json",
    )


_CORRUPT_LOCAL_EVIDENCE_CALENDAR_ARGS = (
    pytest.param((), True, id="single-profile"),
    pytest.param(("--all-profiles",), False, id="all-profiles"),
)


@pytest.mark.parametrize(("extra_args", "assert_degraded_notice"), _CORRUPT_LOCAL_EVIDENCE_CALENDAR_ARGS)
def test_calendar_degrades_when_local_filing_evidence_store_is_unreadable(
    extra_args: tuple[str, ...],
    assert_degraded_notice: bool,
) -> None:
    """An unreadable local filing-evidence store degrades the calendar to a
    schedule-only view rather than refusing it (commit 4adf391107): a
    never-filed taxpayer must still be able to see what they owe.

    The single-profile view surfaces the ``overview.calendar_filing_evidence_degraded``
    WARNING notice; the ``--all-profiles`` view deliberately drops per-loader
    degradation notices (see ``_overview_calendar_all_profiles``) since it
    already degrades per profile and renders many calendars in one payload.
    Either way the profile itself is never skipped — only an unreadable
    *bucket* is skipped, not unreadable evidence within a readable one.
    """
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

    assert result.exit_code == 0, result.output
    assert "profile_skipped" not in result.output
    if assert_degraded_notice:
        assert "overview.calendar_filing_evidence_degraded" in result.output


def test_calendar_help_advertises_local_only() -> None:
    """Help text must signal `local-only` so the operator cannot
    mistake the verb for an AEAT-contacting probe."""

    result = _invoke(["app", "overview", "calendar", "--help"])
    assert result.exit_code == 0, result.output
    assert "--output-language" in result.output
    assert _OUTPUT_LANGUAGE_CHOICE_LIST in result.output
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_calendar_output_language_applies_before_refusal_rendering() -> None:
    result = _invoke(
        [
            "app",
            "overview",
            "calendar",
            "--output-language",
            "ca",
            "--from",
            "not-a-date",
            "--to",
            "2026-03-31",
        ],
    )

    assert result.exit_code != 0, result.output
    assert "No such option" not in result.output
    assert "Format de data invàlid" in result.output
    assert "Formato de fecha inválido" not in result.output


def test_calendar_json_includes_local_live_snapshot_events() -> None:
    ExpedientesService().capture(
        bucket_id=PRIMARY_PROFILE_ID,
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
            authenticated_identity="57964777Q",
        ),
    )
    NotificationsService().capture(
        bucket_id=PRIMARY_PROFILE_ID,
        snapshot=NotificationsSnapshot(
            rows=(
                RemoteNotification(
                    certificado_id="2596230606502",
                    tipo="notificacion",
                    concepto="Requerimiento censal",
                    titular_nif="57964777Q",
                    titular_nombre="Test S.L.",
                    destinatario_nif="57964777Q",
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
        bucket_id=PRIMARY_PROFILE_ID,
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
            authenticated_identity="57964777Q",
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
    fix_action = warning["fix_action"]
    assert fix_action["action"]["action"]["action_id"] == "operator.live.filed.pull"
    assert fix_action["action"]["cli_path"] == ["app", "live", "filed", "pull"]
    assert {binding["argument_name"]: binding["value"] for binding in fix_action["argument_bindings"]} == {
        "modelos": "303",
        "year": 2025,
        "period": "1T",
    }


def test_calendar_strict_mode_refuses_conflicting_aeat_evidence_references() -> None:
    _stamp_calendar_enrolment_from_censo()
    local_ref = "LOCAL-LIVE-CAPTURE-CSV"
    remote_ref = "12345678901234567890"
    record = _modelo_record_with_external_justificante(
        csv=local_ref,
        evidence_kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
    )
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        repo = ModeloRecordCatalogueRepository(bucket_id=PRIMARY_PROFILE_ID)
        repo.save(upsert_filing_record(repo.load(), record))
    ExpedientesService().capture(
        bucket_id=PRIMARY_PROFILE_ID,
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
            authenticated_identity="57964777Q",
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
    assert entry["local_filing_state"] == "external_baseline_imported"
    assert entry["aeat_submission_state"] == "accepted"
    warning = next(item for item in result["warnings"] if item["code"] == "filing.aeat_evidence_conflict")
    assert warning["affected_modelos"] == ["303"]
    fix_action = warning["fix_action"]
    assert fix_action["action"]["action"]["action_id"] == "operator.live.filed.pull"
    assert fix_action["action"]["cli_path"] == ["app", "live", "filed", "pull"]
    assert {binding["argument_name"]: binding["value"] for binding in fix_action["argument_bindings"]} == {
        "modelos": "303",
        "year": 2025,
        "period": "1T",
    }

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
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        repo = ModeloRecordCatalogueRepository(bucket_id=PRIMARY_PROFILE_ID)
        repo.save(upsert_filing_record(repo.load(), record))
    ExpedientesService().capture(
        bucket_id=PRIMARY_PROFILE_ID,
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
            authenticated_identity="57964777Q",
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
    # The all-profiles payload is a per-profile SUMMARY, so it reports that the
    # profile carries a warning; the warning's own fields are read from the
    # single-profile call below, which is where that detail now lives.
    profile = json.loads(lax.output)["result"]["profiles"][0]
    assert profile["warning_count"] >= 1, profile

    single = _invoke(
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
    assert single.exit_code == 0, single.output
    warnings = json.loads(single.output)["result"]["warnings"]
    warning = next(item for item in warnings if item["code"] == "filing.aeat_evidence_conflict")
    assert warning["affected_modelos"] == ["303"]


def test_calendar_strict_mode_refuses_imported_csv_register_without_justificante() -> None:
    _stamp_calendar_enrolment_from_censo()
    csv = "CSVREG-303-2025-1T"
    record = _modelo_record_with_external_justificante(
        csv=csv,
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
    )
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        repo = ModeloRecordCatalogueRepository(bucket_id=PRIMARY_PROFILE_ID)
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
    assert entry["local_filing_state"] == "external_baseline_imported"
    assert entry["aeat_submission_state"] == "accepted"
    assert entry["justificante_verified"] is False
    warning = next(item for item in result["warnings"] if item["code"] == "filing.justificante_unverified")
    assert warning["affected_modelos"] == ["303"]
    fix_action = warning["fix_action"]
    assert fix_action["action"]["action"]["action_id"] == "operator.live.filed.pull"
    assert fix_action["action"]["cli_path"] == ["app", "live", "filed", "pull"]
    assert {binding["argument_name"]: binding["value"] for binding in fix_action["argument_bindings"]} == {
        "modelos": "303",
        "year": 2025,
        "period": "1T",
    }


def test_calendar_text_output_names_verified_aeat_evidence() -> None:
    csv = "JUST3032025X1T7"
    record = _modelo_record_with_external_justificante(csv=csv)
    _stamp_calendar_enrolment_from_censo()
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        repo = ModeloRecordCatalogueRepository(bucket_id=PRIMARY_PROFILE_ID)
        repo.save(upsert_filing_record(repo.load(), record))
        JustificanteRepository().save(_justificante_metadata(csv=csv, tax_id="57964777Q"))

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

    with open_test_profile_session("22222222-2222-4222-8222-222222222222"):
        register_minimal_profile(profile_id="22222222-2222-4222-8222-222222222222", display_name="Second Operator")

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


def test_operator_manual_censo_facts_are_never_treated_as_aeat_verified() -> None:
    """Retirement guard: operator-entered censal facts (``config profile edit``,
    stamped ``PROVENANCE_SOURCE_MANUAL_CLI``) are a non-official evidence tier and
    must never be counted as AEAT-verified censo — the analog of
    ``app_filing not in _OFFICIAL_SOURCE_KINDS``. With the live scrape retired,
    nothing stamps the verified censo tags, so the verified-key set stays empty
    for a hand-entered profile and the calendar keeps its unverified posture.
    """
    from ....application.user_profile.censo_sync import CENSO_SOURCE_TAG
    from ....core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI
    from ....domain.user_profile.values import UserProfileFact, UserProfileRecord

    verified_sources = {CENSO_SOURCE_TAG}
    assert PROVENANCE_SOURCE_MANUAL_CLI not in verified_sources

    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(
            UserProfileFact(
                path="activities.iae_epigraph",
                value="861",
                source=PROVENANCE_SOURCE_MANUAL_CLI,
            ),
            UserProfileFact(
                path="iva.regime",
                value="general",
                source=CENSO_SOURCE_TAG,
            ),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )

    verified = _live_censo_verified_profile_keys(record)
    # The manual-cli fact is excluded; only a censo-stamped fact would count,
    # proving the filter is the source-tag gate and not a vacuous empty return.
    assert "activities.iae_epigraph" not in verified
    assert verified == ("iva.regime",)
