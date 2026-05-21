"""End-to-end CLI verification for the modelo-work UX cluster.

Drives the real ``aeat`` CLI against an isolated encrypted backend to
pin three cluster-E findings reported by the persona fleet:

* M17 - ``work history`` records the work-unit creation event, so the
  audit trail is complete from the moment the unit is provisioned.
* M18 - the first ``work calculate`` binding failure guides the
  operator toward ``--binding KEY=VALUE`` and ``bindings list
  --missing`` instead of leaving them with a bare refusal.
* M19 - ``overview status`` next-step guidance reflects real workspace
  state: once ledger transactions exist it no longer tells the
  operator to import a bank statement.
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
