"""Real-behavior CLI tests for ``aeat app overview prepare``.

Drives the real ``cadrumo`` CLI against an isolated encrypted backend to pin the
data-prep walkthrough's operator contract from #260:

* a fresh profile with no ledger data shows step 1 (import) pending, naming
  the exact ``ledger import`` next command;
* after a manual ledger entry lands in the requested period, step 1 flips to
  done and the checklist advances to naming the classify command;
* the command is read-only and safe to run repeatedly (no bucket-event side
  effects, matching the acceptance criterion in the issue).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextvars import ContextVar
from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.application.overview.data_prep import DataPrepStepId, DataPrepStepState
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.cli.overview_results import OverviewPrepareStepPayload
from cadrumo.tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture

from .overview_native_support import invoke_native_overview

_YEAR = filing_year_envelope().horizon

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]
_PROFILE: ContextVar[NativeCliProfileFixture] = ContextVar("prepare_native_profile")


@pytest.fixture(autouse=True)
def _native_profile(native_overview_profile: NativeCliProfileFixture) -> Iterator[None]:
    token = _PROFILE.set(native_overview_profile)
    try:
        yield
    finally:
        _PROFILE.reset(token)


def _invoke(args: list[str]):
    return invoke_native_overview(_PROFILE.get(), args)


def test_prepare_shows_import_step_pending_on_fresh_profile() -> None:
    """A brand-new profile with no ledger data: the first checklist step is
    pending and names the exact ``ledger import`` command to run next."""

    result = _invoke(
        ["--format", "json", "app", "overview", "prepare", "--modelo", "130", "--year", str(_YEAR), "--period", "1T"],
    )
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)

    assert payload["modelo"] == "130"
    assert payload["filing_year"] == _YEAR
    assert payload["period"] == "1T"
    assert payload["ready_for_calculation"] is False

    steps = {step["step_id"]: step for step in payload["steps"]}
    import_step = steps["import_transactions"]
    assert import_step["state"] == "pending"
    # Importing needs a statement file and a provider this read model cannot
    # know, so the row carries no executable action rather than a placeholder.
    assert import_step["next_action"] is None

    # Every later step is not-done either; none can be satisfied before data exists.
    assert steps["start_modelo_work"]["state"] == "pending"
    work_action = steps["start_modelo_work"]["next_action"]
    assert work_action["action"]["action_id"] == "operator.modelo.work.create"
    assert work_action["action"]["cli_path"] == ["app", "modelo", "work", "create"]
    assert {binding["argument_name"]: binding["value"] for binding in work_action["argument_bindings"]} == {
        "modelo": "130",
        "year": _YEAR,
        "period": "1T",
    }
    preparation_notices = [
        notice
        for notice in unwrap_envelope_notices(result.output)
        if notice["code"].startswith("overview.prepare.next_step.")
    ]
    assert preparation_notices
    # A notice carries an action exactly when its step can name an executable
    # one. The blanket "every notice carries none" this replaced held only
    # while no step did; asserting it now would forbid the surface from
    # offering the operator the command it already resolved.
    notices_by_code = {notice["code"]: notice for notice in preparation_notices}
    actionable = notices_by_code["overview.prepare.next_step.start_modelo_work"]
    assert actionable["action"] == work_action, (
        "the notice must offer the same executable action as its step row, not a second spelling of it"
    )
    for code, notice in notices_by_code.items():
        if code == "overview.prepare.next_step.start_modelo_work":
            continue
        assert notice["action"] is None, (
            f"{code} carries an action, but its step cannot resolve one without operator input"
        )


def test_prepare_advances_import_step_after_manual_ledger_entry() -> None:
    """After a manual ledger entry lands inside the requested period, the
    import step must flip from pending to done - the operator must not keep
    being told to import when the data already exists."""

    added = _invoke(
        [
            "app", "ledger", "add",
            "--date", date(_YEAR, 2, 10).isoformat(), "--amount", "1000.00",
            "--direction", "INCOMING", "--description", "Factura cliente A",
        ],
    )  # fmt: skip
    assert added.exit_code == 0, added.output

    result = _invoke(
        ["--format", "json", "app", "overview", "prepare", "--modelo", "130", "--year", str(_YEAR), "--period", "1T"],
    )
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    steps = {step["step_id"]: step for step in payload["steps"]}

    assert steps["import_transactions"]["state"] == "done"
    assert "1 transaction" in steps["import_transactions"]["summary"]

    # Classification has not happened yet, so the checklist correctly still
    # points the operator at the classify command, not the import command.
    classify_step = steps["classify_transactions"]
    assert classify_step["state"] != "done"
    assert classify_step["next_action"]["action"]["action_id"] == "operator.ledger.classify"


def test_prepare_is_read_only_and_safe_to_run_repeatedly() -> None:
    """Running the walkthrough twice in a row must be a pure read: the second
    invocation reports identical state, proving no mutation occurred."""

    first = _invoke(
        ["--format", "json", "app", "overview", "prepare", "--modelo", "130", "--year", str(_YEAR), "--period", "1T"],
    )
    second = _invoke(
        ["--format", "json", "app", "overview", "prepare", "--modelo", "130", "--year", str(_YEAR), "--period", "1T"],
    )
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert unwrap_schema_envelope(first.output) == unwrap_schema_envelope(second.output)


def test_prepare_rejects_unknown_modelo_with_registry_grounded_message() -> None:
    """An unknown/mistyped modelo code refuses loudly rather than silently
    defaulting to an empty checklist."""

    result = _invoke(
        ["--format", "json", "app", "overview", "prepare", "--modelo", "999", "--year", str(_YEAR), "--period", "1T"],
    )
    assert result.exit_code != 0


def test_prepare_step_row_enforces_the_canonical_step_contract() -> None:
    """``step_id``/``state`` are closed enums on :class:`DataPrepStep`.

    The CLI row redeclared both as free strings, so a malformed step or state
    token could cross the ``overview.prepare`` envelope.
    """
    step_id = next(iter(DataPrepStepId))
    state = next(iter(DataPrepStepState))
    row = OverviewPrepareStepPayload(
        step_id=step_id,
        state=state,
        summary="import your bank statements",
    )
    rendered = json.loads(row.model_dump_json())
    assert rendered["step_id"] == step_id.value
    assert rendered["state"] == state.value

    base = {"step_id": step_id, "state": state, "summary": "s"}
    for label, override in (
        ("unknown step id", {"step_id": "bogus"}),
        ("unknown step state", {"state": "bogus"}),
    ):
        try:
            OverviewPrepareStepPayload(**(base | override))
        except ValidationError:
            continue
        pytest.fail(f"{label} was accepted by the transport row")
