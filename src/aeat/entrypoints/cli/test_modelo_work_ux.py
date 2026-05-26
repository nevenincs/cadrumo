"""End-to-end CLI verification for the modelo-work UX cluster.

Drives the real ``aeat`` CLI against an isolated encrypted backend to
pin the modelo-work findings reported by the persona fleet:

* ``work history`` records the work-unit creation event, so the audit
  trail is complete from the moment the unit is provisioned.
* the first ``work calculate`` binding failure guides the operator
  toward ``--binding KEY=VALUE`` and ``bindings list --missing``
  instead of leaving them with a bare refusal.
* ``overview status`` next-step guidance reflects real workspace
  state: once ledger transactions exist it no longer tells the
  operator to import a bank statement.
* ``work revisions`` accepts the work-unit id positionally, matching
  its sibling ``work status``.
* ``work calculate`` confirms the draft was persisted.
* ``work revision`` shows a stored revision's persisted casilla values
  without recomputing.
* an idempotent ``work create`` reports the reuse plainly and applies
  a supplied ``--name`` as a rename rather than silently dropping it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    try:
        yield tmp_path
    finally:
        dispose_engine()


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_work_unit() -> str:
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["work_unit_id"]


def _create_calculable_work_unit() -> str:
    """Create a modelo 303 work unit whose `work calculate` succeeds with
    no operator-supplied inputs - 303 has no unsatisfied binding gate."""

    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "303", "--year", "2025", "--period", "1T",
            "--revision", "2009-y-siguientes",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["work_unit_id"]


def test_work_history_records_creation_event(_isolated_cli_backend: Path) -> None:
    """M17: a freshly-created work unit's history starts with a
    ``modelo.work_unit.created`` event - not an empty stream."""

    _create_profile()
    work_unit_id = _create_work_unit()

    history = _invoke(["--format", "json", "app", "modelo", "work", "history", work_unit_id])
    assert history.exit_code == 0, history.output
    payload = json.loads(history.output)

    assert payload["event_count"] == 1
    event = payload["events"][0]
    assert event["event_type"] == "modelo.work_unit.created"
    assert event["object_type"] == "work_unit"
    assert event["object_id"] == work_unit_id
    # The creation event names who provisioned the unit.
    assert event["actor"]
    assert event["payload"]["modelo"] == "130"
    assert event["payload"]["revision_id"] == "2019-y-siguientes"


def test_first_work_calculate_binding_error_guides_the_operator(_isolated_cli_backend: Path) -> None:
    """M18: the first ``work calculate`` that hits an unsatisfied binding
    fails with guidance toward ``--binding KEY=VALUE`` and the
    bindings-list discovery command - not a bare refusal."""

    _create_profile()
    work_unit_id = _create_work_unit()

    result = _invoke(
        ["app", "modelo", "work", "calculate", work_unit_id, "--casilla", "01=10000"],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # The bare missing-binding line is still present...
    assert "irpf.previous_year_economic_activity_net_income" in result.output
    # ...now followed by actionable guidance.
    assert "--binding" in result.output
    assert "bindings list" in result.output and "--missing" in result.output


def test_work_revisions_accepts_a_positional_work_unit_id(_isolated_cli_backend: Path) -> None:
    """`work revisions <id>` must accept the work-unit id positionally,
    matching its sibling `work status <id>` - the inconsistency where
    `revisions` demanded `--work-unit-id` is gone."""

    _create_profile()
    work_unit_id = _create_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "revisions", work_unit_id])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["work_unit_id_filter"] == work_unit_id


def test_work_calculate_confirms_the_draft_was_saved(_isolated_cli_backend: Path) -> None:
    """After `work calculate` the operator is told the result was
    persisted as a draft revision and how to resume / re-inspect it -
    the bare casilla table left no save signal."""

    _create_profile()
    work_unit_id = _create_calculable_work_unit()

    result = _invoke(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["saved"] is True
    confirmation = payload["saved_confirmation"]
    assert payload["calculation_revision_id"] in confirmation
    assert "work revision" in confirmation


def test_modelo_export_unverified_work_unit_points_to_work_verify(_isolated_cli_backend: Path) -> None:
    """Export recovery must name the real verification command.

    The export verb lives at ``app modelo export`` but verification is
    under ``app modelo work verify``. The old hint named a non-existent
    ``app modelo verify`` command and sent operators into a dead end.
    """

    _create_profile()
    work_unit_id = _create_calculable_work_unit()

    result = _invoke(["app", "modelo", "export", work_unit_id, "--output", "modelo-303.txt"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "aeat app modelo work verify" in result.output
    assert "aeat app modelo verify" not in result.output


def test_work_revision_shows_persisted_casilla_values(_isolated_cli_backend: Path) -> None:
    """`work revision <id>` shows a stored revision's persisted casilla
    values without recomputing - the operator can re-inspect a saved
    calculation instead of re-running it."""

    _create_profile()
    work_unit_id = _create_calculable_work_unit()

    calculated = _invoke(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert calculated.exit_code == 0, calculated.output
    revision_id = json.loads(calculated.output)["calculation_revision_id"]
    saved_values = json.loads(calculated.output)["casilla_values"]

    shown = _invoke(["--format", "json", "app", "modelo", "work", "revision", revision_id])
    assert shown.exit_code == 0, shown.output
    payload = json.loads(shown.output)
    assert payload["operation"] == "modelo.work.revision"
    assert payload["calculation_revision_id"] == revision_id
    # The shown casilla values are exactly the persisted ones.
    assert payload["casilla_values"] == saved_values


def test_work_revision_rejects_an_unknown_revision_id(_isolated_cli_backend: Path) -> None:
    """An absent revision id is refused cleanly, not surfaced as an
    opaque internal error."""

    _create_profile()
    unknown = "0" * 64
    result = _invoke(["app", "modelo", "work", "revision", unknown])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert unknown in result.output


def test_idempotent_work_create_reports_reuse(_isolated_cli_backend: Path) -> None:
    """Re-creating an existing (modelo, year, period, revision) work unit
    must report the reuse plainly - status `reused`, not a silent
    `modelo.work.create` that reads as a fresh creation."""

    _create_profile()
    first = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "First",
        ]
    )  # fmt: skip
    assert first.exit_code == 0, first.output
    first_payload = json.loads(first.output)
    assert first_payload["status"] == "created"
    assert first_payload["operation"] == "modelo.work.create"

    second = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "First",
        ]
    )  # fmt: skip
    assert second.exit_code == 0, second.output
    second_payload = json.loads(second.output)
    assert second_payload["status"] == "reused"
    assert second_payload["operation"] == "modelo.work.reuse"
    assert second_payload["work_unit_id"] == first_payload["work_unit_id"]


def test_idempotent_work_create_applies_a_new_name_as_a_rename(_isolated_cli_backend: Path) -> None:
    """A different --name supplied on an idempotent re-create is not
    silently dropped: it is applied as a rename and the result says so."""

    _create_profile()
    first = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "Original",
        ]
    )  # fmt: skip
    assert first.exit_code == 0, first.output

    renamed = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes", "--name", "Renamed Unit",
        ]
    )  # fmt: skip
    assert renamed.exit_code == 0, renamed.output
    payload = json.loads(renamed.output)
    assert payload["status"] == "reused"
    assert payload["name_applied"] == "Renamed Unit"
    assert payload["name"] == "Renamed Unit"

    # The rename is durable: a fresh status read sees the new name.
    status = _invoke(
        ["--format", "json", "app", "modelo", "work", "status", payload["work_unit_id"]]
    )
    assert status.exit_code == 0, status.output
    assert json.loads(status.output)["name"] == "Renamed Unit"


def test_overview_next_step_not_import_after_manual_ledger_entry(_isolated_cli_backend: Path) -> None:
    """M19: after ``ledger add`` records a transaction, ``overview
    status`` next-step guidance must not suggest importing a bank
    statement - the operator already has ledger data."""

    _create_profile()
    added = _invoke(
        [
            "app", "ledger", "add",
            "--date", "2025-01-15", "--amount", "1000.00",
            "--direction", "INCOMING", "--description", "Factura cliente A",
        ]
    )  # fmt: skip
    assert added.exit_code == 0, added.output

    status = _invoke(["app", "overview", "status"])
    assert status.exit_code == 0, status.output
    # The transaction is visible...
    assert "1" in status.output
    # ...and the next-step guidance points forward, never back at import.
    next_section = status.output.split("\n\n")[-1]
    assert "ledger import" not in next_section
    assert "ledger review" in next_section
    assert "modelo work create" in next_section
