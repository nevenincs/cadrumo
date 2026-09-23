"""Contracts for the installed CLI/TUI continuation driver."""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from .. import installed_tui_continuations as continuation_module
from ..installed_tui_continuations import (
    ContinuationPathReceipt,
    InstalledContinuationError,
    _cli_public_readback,
    _parse_child_state,
    _state,
)
from ..tui_journey import create_continuation_checkpoint, prove_continuation

if TYPE_CHECKING:
    from dev.acceptance.installed_cli import InstalledCli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_GENERATION = "a" * 64


def test_partial_handoff_has_four_work_units_but_only_q1_is_locally_filed() -> None:
    handoff = _state(
        generation=_GENERATION,
        year=2025,
        periods=("1T", "2T", "3T", "4T"),
        filed=("1T",),
        annual_exported=False,
    )
    checkpoint = create_continuation_checkpoint(frontend_path="cli_to_tui", state=handoff)
    completion = _state(
        generation=_GENERATION,
        year=2025,
        periods=("1T", "2T", "3T", "4T", "0A"),
        filed=("1T", "2T", "3T", "4T"),
        annual_exported=True,
    )

    evidence = prove_continuation(
        checkpoint=checkpoint,
        frontend="tui",
        resumed_state=handoff,
        completion_state=completion,
    )

    assert checkpoint.state.work_periods == ("1T", "2T", "3T", "4T")
    assert checkpoint.state.locally_filed_periods == ("1T",)
    assert evidence.completion_state.exported_modelos == ("100",)


def test_cli_readback_uses_public_ledger_and_work_list_collections() -> None:
    class Cli:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        def run(self, args: tuple[str, ...]) -> dict[str, object]:
            self.calls.append(args)
            if args == ("app", "ledger", "list"):
                return {"result": {"rows": [{"transaction_id": str(index)} for index in range(8)]}}
            if args == ("app", "ledger", "invoice", "list"):
                return {
                    "result": {
                        "count": 8,
                        "rows": [{"linked_transaction_ids": [str(index)]} for index in range(8)],
                    }
                }
            return {
                "result": {
                    "work_units": [
                        {
                            "modelo": "130",
                            "filing_year": 2025,
                            "period": {"filing_year": 2025, "code": "1T"},
                            "work_unit_id": "q1",
                            "filed_calculation_revision_id": "revision-q1",
                            "current_filing_record_id": "filing-q1",
                        },
                        {
                            "modelo": "130",
                            "filing_year": 2025,
                            "period": {"filing_year": 2025, "code": "2T"},
                            "work_unit_id": "q2",
                        },
                        {
                            "modelo": "130",
                            "filing_year": 2025,
                            "period": {"filing_year": 2025, "code": "3T"},
                            "work_unit_id": "q3",
                        },
                        {
                            "modelo": "130",
                            "filing_year": 2025,
                            "period": {"filing_year": 2025, "code": "4T"},
                            "work_unit_id": "q4",
                        },
                    ]
                }
            }

    cli = Cli()
    state = _cli_public_readback(cast("InstalledCli", cli), generation=_GENERATION, year=2025)

    assert cli.calls == [
        ("app", "ledger", "list"),
        ("app", "ledger", "invoice", "list"),
        ("app", "modelo", "work", "list"),
    ]
    assert state.transactions == state.invoices == state.links == 8
    assert state.work_periods == ("1T", "2T", "3T", "4T")


def test_cli_readback_refuses_a_partial_public_work_list() -> None:
    class Cli:
        def run(self, args: tuple[str, ...]) -> dict[str, object]:
            if args == ("app", "ledger", "list"):
                return {"result": {"rows": [{"transaction_id": str(index)} for index in range(8)]}}
            if args == ("app", "ledger", "invoice", "list"):
                return {
                    "result": {
                        "count": 8,
                        "rows": [{"linked_transaction_ids": [str(index)]} for index in range(8)],
                    }
                }
            return {
                "result": {
                    "work_units": [
                        {
                            "modelo": "130",
                            "filing_year": 2025,
                            "period": {"filing_year": 2025, "code": "1T"},
                            "work_unit_id": "q1",
                        }
                    ]
                }
            }

    with pytest.raises(InstalledContinuationError, match="four-unit handoff"):
        _cli_public_readback(cast("InstalledCli", Cli()), generation=_GENERATION, year=2025)


def test_cli_readback_refuses_when_q1_has_no_public_filing_pointers() -> None:
    class Cli:
        def run(self, args: tuple[str, ...]) -> dict[str, object]:
            if args == ("app", "ledger", "list"):
                return {"result": {"rows": [{"transaction_id": str(index)} for index in range(8)]}}
            if args == ("app", "ledger", "invoice", "list"):
                return {
                    "result": {
                        "count": 8,
                        "rows": [{"linked_transaction_ids": [str(index)]} for index in range(8)],
                    }
                }
            return {
                "result": {
                    "work_units": [
                        {
                            "modelo": "130",
                            "filing_year": 2025,
                            "period": {"filing_year": 2025, "code": period},
                            "work_unit_id": period,
                        }
                        for period in ("1T", "2T", "3T", "4T")
                    ]
                }
            }

    with pytest.raises(InstalledContinuationError, match="Q1 local filing"):
        _cli_public_readback(cast("InstalledCli", Cli()), generation=_GENERATION, year=2025)


def test_cli_completion_reuses_public_handoff_work_ids(monkeypatch, tmp_path: Path) -> None:
    observed: list[str] = []

    monkeypatch.setattr(
        continuation_module,
        "_public_work_units",
        lambda _cli, *, year: {
            "1T": {"work_unit_id": "q1"},
            "2T": {"work_unit_id": "q2"},
            "3T": {"work_unit_id": "q3"},
            "4T": {"work_unit_id": "q4"},
        },
    )
    monkeypatch.setattr(
        continuation_module,
        "create_m130_work",
        lambda *_args, **_kwargs: pytest.fail("completion must not create an existing handoff work unit"),
    )
    monkeypatch.setattr(
        continuation_module,
        "calculate_m130_work",
        lambda _cli, *, work_id, oracle: (observed.append(work_id) or {}, f"revision-{oracle.period}"),
    )
    monkeypatch.setattr(continuation_module, "verify_and_file_m130", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        continuation_module,
        "calculate_m100",
        lambda *_args, **_kwargs: {"export_execution": "proven"},
    )
    monkeypatch.setattr(
        continuation_module,
        "_validate_annual_artifact",
        lambda **_kwargs: ({}, {"xsd_valid": True, "error_identities": ()}),
    )
    monkeypatch.setattr(continuation_module, "_annual_schema", lambda *_args: tmp_path / "official.xsd")

    state, validation = continuation_module._cli_complete(
        cli=cast("InstalledCli", SimpleNamespace()),
        workspace_root=tmp_path,
        output_dir=tmp_path,
        generation=_GENERATION,
        year=2025,
    )

    assert observed == ["q2", "q3", "q4"]
    assert state.locally_filed_periods == ("1T", "2T", "3T", "4T")
    assert validation["xsd_valid"] is True


def test_child_runner_has_a_bounded_2400_second_tui_window(monkeypatch, tmp_path: Path) -> None:
    receipt = tmp_path / "cli_to_tui.json"
    observed: dict[str, object] = {}

    def fake_child(**kwargs):
        observed.update(kwargs)
        receipt.write_text('{"status":"proven"}', encoding="utf-8")
        return SimpleNamespace(returncode=0, receipt_status="proven")

    monkeypatch.setattr(continuation_module, "run_installed_tui_child_process", fake_child)
    result = continuation_module._run_child(
        direction="cli_to_tui",
        python_executable=tmp_path / "python.exe",
        workspace_root=tmp_path,
        authority_root=tmp_path,
        storage_root=tmp_path,
        scratch=tmp_path,
        passphrase=secrets.token_urlsafe(32),
        year=2025,
    )

    assert result == {"status": "proven"}
    assert observed["timeout_seconds"] == 2400


def test_child_state_receipt_retains_only_value_free_continuation_state() -> None:
    state = _state(
        generation=_GENERATION,
        year=2025,
        periods=("1T", "2T", "3T", "4T"),
        filed=("1T",),
        annual_exported=False,
    )
    recovered = _parse_child_state({"handoff_state": asdict(state)}, "handoff_state")
    json_recovered = _parse_child_state(json.loads(json.dumps({"handoff_state": asdict(state)})), "handoff_state")
    receipt = ContinuationPathReceipt(
        direction="cli_to_tui",
        status="proven",
        year=2025,
        product_origin="site-packages",
        product_init_sha256="b" * 64,
        handoff_state_sha256=state.state_sha256(),
        resumed_state_sha256=state.state_sha256(),
        completion_state_sha256="c" * 64,
        transactions=8,
        invoices=8,
        links=8,
        locally_filed_periods=("1T", "2T", "3T", "4T"),
        annual_xsd_valid=True,
        annual_xsd_error_count=0,
        oracle_value_fingerprint="d" * 64,
    )

    assert recovered == state
    assert json_recovered == state
    serialized = str(receipt.to_dict())
    assert "passphrase" not in serialized
    assert "12000" not in serialized
    assert "submission" not in serialized
