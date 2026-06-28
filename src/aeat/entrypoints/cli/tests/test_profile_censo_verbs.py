"""CLI surface tests for ``aeat config profile censo {refresh,show,compare,apply}``.

Exercises the Typer surface end-to-end against a real seeded
WorkflowState + the encrypted backend. Refresh is asserted to refuse
cleanly with the "sede driver not wired" message; show/compare/apply
are exercised against a snapshot captured via the application service
directly (the production refresh path lands when the sede G313
adapter is wired through the live driver).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from typing import cast

import click
import pytest
from click.testing import CliRunner, Result
from typer.main import get_command

from ....application.live._censo import CensoSnapshotService
from ....application.user_profile._orchestration import profile_create_storage_span
from ....core.config import Settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .._config import profile_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_AEAT = Settings.external_constants().aeat
_G313 = f"{_AEAT.domains.sede}{_AEAT.sede_paths.censo_g313_launcher}"
_PROFILE_RUNNER = CliRunner()


@cache
def _profile_command() -> click.Command:
    return cast(click.Command, get_command(profile_app))


def _invoke_profile(args: Sequence[str]) -> Result:
    return _PROFILE_RUNNER.invoke(_profile_command(), list(args))


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        yield


def _seed_active_profile(*, without_taxpayer_axes: bool = False) -> None:
    from ....application.user_profile._testing import register_minimal_profile
    from ....application.workflow._persistence import workflow_state_repository

    repo = workflow_state_repository()
    overrides = {"identity.tax_id": "12345678Z", "activities.description": "software"}
    if without_taxpayer_axes:
        overrides.update(
            {
                "taxpayer_type.entity_type": "",
                "taxpayer_type.irpf_income_categories": "",
                "irpf.estimation_regime": "",
            },
        )
    repo.update(
        lambda state: register_minimal_profile(
            state,
            profile_id="default",
            overrides=overrides,
        ),
    )


def _capture_snapshot(*, include_iae: bool = False) -> str:
    from ....core import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    assert active is not None, "active profile must be seeded before capture"
    service = CensoSnapshotService(bucket_id=active)
    censo_facts = {
        "censo.establecimiento_type": "propio",
        "censo.elected_withholding_pct": "15",
        "vivienda_office.total_m2": "120.00",
        "vivienda_office.office_m2": "24.00",
    }
    if include_iae:
        censo_facts["activities.iae_epigraph"] = "763"
        censo_facts["iva.regime"] = "GENERAL"
    snapshot = service.capture(
        profile_id=active,
        captured_at=datetime.now(UTC),
        source_url=_G313,
        censo_facts=censo_facts,
    )
    return snapshot.snapshot_id


def test_censo_help_lists_four_verbs() -> None:
    result = _invoke_profile(("censo", "--help"))

    assert result.exit_code == 0
    for verb in ("pull", "show", "compare", "apply"):
        assert verb in result.output


def test_censo_refresh_command_is_not_registered() -> None:
    result = _invoke_profile(("censo", "refresh", "--help"))

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_refresh_refuses_without_live_gate() -> None:
    """Live refresh requires AEAT_LIVE_TESTS_ENABLED=1 to pass the
    access-gate. With the gate off (default), the CLI surfaces the
    refusal without ever touching a browser session.

    ``override_settings(aeat_live_tests_enabled=False)`` pins the
    gate-off state; the ContextVar-backed override shadows any ambient
    env value.
    """

    from ....core.config import override_settings

    _seed_active_profile()

    with override_settings(aeat_live_tests_enabled=""):
        result = _invoke_profile(("censo", "pull"))

    assert result.exit_code != 0
    haystack = (result.output + " " + str(result.exception or "")).lower()
    assert "auth_preflight=redacted" in haystack
    assert "auth_provider" in haystack
    assert "live aeat reads require aeat_live_tests_enabled" in haystack


def test_show_refuses_when_no_snapshot_exists() -> None:
    _seed_active_profile()

    result = _invoke_profile(("censo", "show"))

    assert result.exit_code != 0
    # The CLI error boundary decoration is process-global memoised by
    # callback identity (see ``command_error_boundary`` in ``_errors``).
    # When the root ``aeat`` app has been imported by an earlier test,
    # ``profile_app`` callbacks are wrapped and the refusal renders to
    # stderr (mixed into ``result.output``).  When this test runs alone
    # the verb raises ``CliRefusedBoundaryError`` directly and the
    # message is on ``result.exception``.  Accept both surfaces so the
    # assertion is order-independent.
    haystack = (result.output + " " + str(result.exception or "")).lower()
    assert "no censo snapshot" in haystack


def test_show_emits_active_snapshot() -> None:
    _seed_active_profile()
    snapshot_id = _capture_snapshot()

    result = _invoke_profile(("censo", "show"))

    assert result.exit_code == 0
    assert snapshot_id in result.output
    assert "vivienda_office.total_m2\t120.00" in result.output
    assert "state\tactive" in result.output


def test_compare_reports_per_field_status() -> None:
    _seed_active_profile()
    _capture_snapshot()

    result = _invoke_profile(("censo", "compare"))

    assert result.exit_code == 0
    assert "censo_only\tcenso.establecimiento_type" in result.output
    assert "censo_only\tvivienda_office.total_m2" in result.output


def test_apply_writes_censo_facts_onto_profile() -> None:
    _seed_active_profile(without_taxpayer_axes=True)
    _capture_snapshot(include_iae=True)

    result = _invoke_profile(("censo", "apply"))

    assert result.exit_code == 0
    assert "written\tcenso.establecimiento_type" in result.output
    assert "written\tvivienda_office.office_m2" in result.output
    assert "derived\ttaxpayer_type.entity_type" in result.output
    assert "derived\ttaxpayer_type.irpf_income_categories" in result.output
    assert "taxpayer_model_declared\ttrue" in result.output
    assert "calendar_obligations\t" in result.output
    assert (
        "calendar_enrolment_sources\t"
        "activities.iae_epigraph=aeat_censo_read,"
        "iva.regime=aeat_censo_read,"
        "taxpayer_type.entity_type=aeat_censo_derived,"
        "taxpayer_type.irpf_income_categories=aeat_censo_derived"
    ) in result.output
    obligation_rows = [
        line.split("\t") for line in result.output.splitlines() if line.startswith("calendar_obligation\t303\t")
    ]
    assert obligation_rows
    current_year_row = next(row for row in obligation_rows if row[2] == str(date.today().year))
    fields = dict(cell.split("=", maxsplit=1) for cell in current_year_row[4:])
    assert current_year_row[3] in {"1T", "2T", "3T", "4T"}
    assert date.fromisoformat(fields["opens_on"]) <= date.fromisoformat(fields["closes_on"])
    assert date.fromisoformat(fields["closes_on"]) <= date.fromisoformat(fields["adjusted_closes_on"])
    assert "payment_cutoff_on" in fields
    assert fields["status"]
    assert fields["user_state"]
    assert fields["enrolment_sources"] == (
        "activities.iae_epigraph=aeat_censo_read,"
        "iva.regime=aeat_censo_read,"
        "taxpayer_type.entity_type=aeat_censo_derived,"
        "taxpayer_type.irpf_income_categories=aeat_censo_derived"
    )
    modelo_100_row = next(
        line.split("\t") for line in result.output.splitlines() if line.startswith("calendar_obligation\t100\t")
    )
    modelo_100_fields = dict(cell.split("=", maxsplit=1) for cell in modelo_100_row[4:])
    assert modelo_100_fields["enrolment_sources"] == "taxpayer_type.entity_type=aeat_censo_derived"


def test_compare_matches_after_apply() -> None:
    _seed_active_profile()
    _capture_snapshot()
    applied = _invoke_profile(("censo", "apply"))
    assert applied.exit_code == 0, applied.output

    result = _invoke_profile(("censo", "compare"))

    assert result.exit_code == 0
    assert "matches\tcenso.establecimiento_type" in result.output
    assert "matches\tvivienda_office.total_m2" in result.output


def test_apply_emits_censo_applied_bucket_event() -> None:
    """Apply MUST emit CENSO_APPLIED so the stale-cascade walker
    has a typed event to react to. The CLI test never reached the
    catalogue before this assertion landed — the emission was
    implemented but not witnessed end-to-end."""

    from ....application.workflow._persistence import workflow_state_repository
    from ....core import resolve_active_bucket_id
    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    _seed_active_profile()
    snapshot_id = _capture_snapshot()

    result = _invoke_profile(("censo", "apply"))
    assert result.exit_code == 0, result.output

    catalogue = BucketEventHistoryRepository().load()
    workflow_state_repository().load()
    active = resolve_active_bucket_id()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.CENSO_APPLIED and event.object_id == active
    ]
    assert matching, (
        f"CENSO_APPLIED must fire after apply; saw {[e.event_type.value for e in catalogue.events.values()]}"
    )
    payload = matching[-1].payload
    assert payload["snapshot_id"] == snapshot_id
    assert payload["profile_id"] == active


def test_rejected_subverb_returns_nonzero() -> None:
    """Typer must refuse an undeclared subverb (e.g. 'diff' is not in
    {refresh, show, compare, apply}). Without this regression a typo
    would silently invoke nothing instead of erroring."""

    _seed_active_profile()

    result = _invoke_profile(("censo", "diff"))

    assert result.exit_code != 0


def test_compare_emits_json_payload_with_typed_rows() -> None:
    """The --format json branch on the root aeat CLI must render
    CensoProfileComparison through model_dump(mode='json') cleanly."""

    import json

    _seed_active_profile(without_taxpayer_axes=True)
    _capture_snapshot()

    result = invoke_cached_cli(["--format", "json", "config", "profile", "censo", "compare"])
    assert result.exit_code == 0, result.output

    raw = json.loads(result.output)
    # Every CLI verb now emits the centralised {schema_version, command,
    # result, warnings} envelope; the operator-visible payload lives
    # under ``result``.
    payload = raw["result"] if isinstance(raw, dict) and "schema_version" in raw else raw
    assert payload["snapshot_id"]
    statuses = {row["path"]: row["status"] for row in payload["rows"]}
    assert statuses["censo.establecimiento_type"] == "censo_only"
    assert statuses["vivienda_office.total_m2"] == "censo_only"
    censo_only_statuses = {row["path"]: row["status"] for row in payload["censo_only"]}
    assert censo_only_statuses["censo.establecimiento_type"] == "censo_only"
    assert censo_only_statuses["vivienda_office.total_m2"] == "censo_only"


def test_apply_emits_json_payload_with_written_paths() -> None:
    """The --format json branch on apply must serialize CensoApplyPayload
    (projected from the application CensoApplyResult via from_result) through
    model_dump(mode='json'); written_paths is a tuple that JSON renders as a list."""

    import json

    _seed_active_profile(without_taxpayer_axes=True)
    _capture_snapshot(include_iae=True)

    result = invoke_cached_cli(["--format", "json", "config", "profile", "censo", "apply"])
    assert result.exit_code == 0, result.output

    raw = json.loads(result.output)
    payload = raw["result"] if isinstance(raw, dict) and "schema_version" in raw else raw
    assert payload["snapshot_id"]
    assert "censo.establecimiento_type" in payload["written_paths"]
    assert "vivienda_office.office_m2" in payload["written_paths"]
    assert payload["derived_paths"] == ["taxpayer_type.entity_type", "taxpayer_type.irpf_income_categories"]
    assert payload["taxpayer_model_declared"] is True
    assert payload["calendar_range_from"]
    assert payload["calendar_range_to"]
    assert isinstance(payload["calendar_obligation_modelos"], list)
    assert payload["calendar_enrolment_source_paths"] == [
        "activities.iae_epigraph=aeat_censo_read",
        "iva.regime=aeat_censo_read",
        "taxpayer_type.entity_type=aeat_censo_derived",
        "taxpayer_type.irpf_income_categories=aeat_censo_derived",
    ]
    rows = payload["calendar_obligation_rows"]
    assert rows, payload
    modelo_303_rows = [row for row in rows if row["modelo"] == "303"]
    assert modelo_303_rows
    current_year_303 = next(row for row in modelo_303_rows if row["filing_year"] == date.today().year)
    assert current_year_303["period"] in {"1T", "2T", "3T", "4T"}
    assert date.fromisoformat(current_year_303["opens_on"]) <= date.fromisoformat(current_year_303["closes_on"])
    assert date.fromisoformat(current_year_303["closes_on"]) <= date.fromisoformat(
        current_year_303["adjusted_closes_on"],
    )
    assert "payment_cutoff_on" in current_year_303
    assert current_year_303["status"]
    assert current_year_303["user_state"]
    assert current_year_303["enrolment_source_paths"] == payload["calendar_enrolment_source_paths"]
    modelo_100_row = next(row for row in rows if row["modelo"] == "100")
    assert modelo_100_row["enrolment_source_paths"] == ["taxpayer_type.entity_type=aeat_censo_derived"]
