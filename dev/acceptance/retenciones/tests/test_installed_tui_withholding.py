"""Contract checks for the RETENCIONES-01 installed-TUI withholding journey."""

from __future__ import annotations

import asyncio
import json
import secrets
from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import installed_tui_withholding as driver

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _document(*, fresh_readback: list[str]) -> dict[str, object]:
    return {
        "schema_version": "retenciones-01-installed-tui-withholding-v5",
        "status": "proven",
        "product_origin": "site-packages",
        "product_init_sha256": "a" * 64,
        "year": 2025,
        "professional_capture": "captured",
        "urban_rent_capture": "captured",
        "cli_periodic_lifecycle": [],
        "cli_seeded_scopes": ["not_yet_seeded", "not_yet_seeded"],
        "tui_mutation": "not_yet_mutated",
        "fresh_readback": fresh_readback,
        "unexercised": list(driver._UNEXERCISED),
    }


def test_proven_receipt_requires_both_income_families_and_explicit_reopen() -> None:
    receipt = driver._proven_receipt(
        _document(fresh_readback=["modelo-111", "modelo-115"]), year=2025, require_fresh_readback=True
    )

    assert receipt.professional_capture == "captured"
    assert receipt.urban_rent_capture == "captured"
    assert receipt.fresh_readback == ("modelo-111", "modelo-115")
    assert receipt.cli_periodic_lifecycle == ()
    assert receipt.unexercised == ("tui_only_historical_work_creation", "tui_only_periodic_lifecycle")


def test_proven_receipt_refuses_route_only_or_wrong_scope_claims() -> None:
    document = _document(fresh_readback=["modelo-111", "not_yet_reopened"])

    with pytest.raises(driver.RetencionesInstalledTuiError, match="fresh scope readback"):
        driver._proven_receipt(document, year=2025, require_fresh_readback=True)


def test_proven_receipt_refuses_child_claiming_cli_lifecycle_evidence() -> None:
    document = _document(fresh_readback=["modelo-111", "modelo-115"])
    document["cli_periodic_lifecycle"] = ["modelo.work.calculate"]

    with pytest.raises(driver.RetencionesInstalledTuiError, match="invalid public shape"):
        driver._proven_receipt(document, year=2025, require_fresh_readback=True)


def test_ledger_invoice_uses_percentage_for_iva_and_fraction_for_retention() -> None:
    values = driver._ledger_invoice_form_values(
        number="RET-PRO-2025-001", base="500.00", withholding="95.00", year=2025
    )

    assert values["#ledger-invoice-iva-rate"] == "21"
    assert values["#ledger-invoice-retention-rate"] == "0.19"
    assert values["#ledger-invoice-retention-amount"] == "95.00"


def test_tui_capture_supplies_territorial_deduction_as_an_explicit_payer_fact() -> None:
    values = driver._withholding_capture_form_values(invoice_number="RET-PRO-2025-001", kind="professional", year=2025)

    assert values["territorial-deduction"] == "0"
    assert values["province"] == "28"


def test_cli_seeded_replacement_uses_the_last_inspected_professional_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[tuple[str, str]] = []
    admission_events: list[str] = []
    receipt_calls: list[dict[str, object]] = []

    async def fake_open(*_args: object, **_kwargs: object) -> None:
        events.append(("open", "withholding"))

    async def fake_inspect(*_args: object, modelo: str, expected_entries: int, **_kwargs: object) -> None:
        events.append(("inspect", f"{modelo}:{expected_entries}"))

    async def fake_capture(*_args: object, kind: str, mode: str, **_kwargs: object) -> None:
        events.append((mode, kind))

    def fake_launcher(*, drive_after_home: object, **_kwargs: object) -> None:
        assert callable(drive_after_home)
        admission_events.append("launcher")
        asyncio.run(drive_after_home(SimpleNamespace(app=SimpleNamespace(exit=lambda: None))))

    monkeypatch.setattr(driver, "_open_withholding", fake_open)
    monkeypatch.setattr(driver, "_inspect_scope", fake_inspect)
    monkeypatch.setattr(driver, "_set_capture", fake_capture)
    monkeypatch.setattr(driver, "_run_launcher", fake_launcher)
    monkeypatch.setattr(
        driver, "_admit_cli_created_profile", lambda **_kwargs: admission_events.append("visible_login")
    )
    monkeypatch.setattr(driver, "_receipt", lambda **kwargs: receipt_calls.append(kwargs) or None)

    assert driver.run_mutation_child(workspace_root=tmp_path, passphrase=secrets.token_urlsafe(), year=2025) is None
    assert events == [
        ("open", "withholding"),
        ("inspect", "115:1"),
        ("inspect", "111:4"),
        ("replace", "professional"),
        ("inspect", "111:2"),
    ]
    assert admission_events == ["visible_login", "launcher"]
    assert receipt_calls == [
        {
            "workspace_root": tmp_path,
            "year": 2025,
            "cli_seeded_scopes": ("modelo-111", "modelo-115"),
            "tui_mutation": "professional_replace",
            "fresh_readback": ("not_yet_reopened", "not_yet_reopened"),
        }
    ]


def test_reopen_admits_cli_created_profile_before_fresh_launcher(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    admission_events: list[str] = []

    async def fake_open(*_args: object, **_kwargs: object) -> None:
        return None

    async def fake_inspect(*_args: object, **_kwargs: object) -> None:
        return None

    def fake_launcher(*, drive_after_home: object, **_kwargs: object) -> None:
        assert callable(drive_after_home)
        admission_events.append("launcher")
        asyncio.run(drive_after_home(SimpleNamespace(app=SimpleNamespace(exit=lambda: None))))

    monkeypatch.setattr(driver, "_open_withholding", fake_open)
    monkeypatch.setattr(driver, "_inspect_scope", fake_inspect)
    monkeypatch.setattr(driver, "_run_launcher", fake_launcher)
    monkeypatch.setattr(
        driver, "_admit_cli_created_profile", lambda **_kwargs: admission_events.append("visible_login")
    )
    monkeypatch.setattr(driver, "_receipt", lambda **_kwargs: None)

    assert driver.run_reopen_child(workspace_root=tmp_path, passphrase=secrets.token_urlsafe(), year=2025) is None
    assert admission_events == ["visible_login", "launcher"]


def test_launcher_refuses_zero_exit_without_executing_public_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.entrypoints.tui import launcher

    monkeypatch.setattr(driver, "admitted_session_autopilot", lambda **kwargs: kwargs["drive_after_home"])
    monkeypatch.setattr(launcher, "main", lambda **_kwargs: 0)

    async def drive(_pilot: object) -> None:
        return None

    with pytest.raises(driver.RetencionesInstalledTuiError, match="did not enter public callback"):
        driver._run_launcher(passphrase=secrets.token_urlsafe(), drive_after_home=drive)


def test_launcher_requires_completed_public_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.entrypoints.tui import launcher

    monkeypatch.setattr(driver, "admitted_session_autopilot", lambda **kwargs: kwargs["drive_after_home"])

    def fake_main(*, auto_pilot: object, **_kwargs: object) -> int:
        assert callable(auto_pilot)
        asyncio.run(auto_pilot(object()))
        return 0

    monkeypatch.setattr(launcher, "main", fake_main)
    completed: list[bool] = []

    async def drive(_pilot: object) -> None:
        completed.append(True)

    driver._run_launcher(passphrase=secrets.token_urlsafe(), drive_after_home=drive)
    assert completed == [True]


def test_read_window_parses_generation_audit_before_count_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from .. import cli_journey

    monkeypatch.setattr(
        cli_journey,
        "_require_result",
        lambda *_args, **_kwargs: {
            "observation_count": 2,
            "withholding_window": {
                "baseline": {"scope_token": "scope", "generation_id": "a" * 64},
                "generation": 2,
                "generation_audit": {"parent_generation_id": "b" * 64, "mode": "replace"},
            },
        },
    )

    readback = driver._read_window(cli=object(), modelo="111", year=2025, stage="test")

    assert readback.observation_count == 2
    assert readback.generation == 2
    assert readback.parent_generation_id == "b" * 64
    assert readback.mode == "replace"


def test_replacement_readback_reports_all_sanitized_semantics_before_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    before = driver._WindowReadback("111", 2, "scope", "a" * 64, 2, "b" * 64, "append")
    urban_rent = driver._WindowReadback("115", 1, "rent", "c" * 64, 1, "d" * 64, "append")
    reads = iter(
        (
            driver._WindowReadback("111", 2, "scope", "e" * 64, 3, "a" * 64, "replace"),
            urban_rent,
        )
    )
    monkeypatch.setattr(driver, "_read_window", lambda **_kwargs: next(reads))
    executable = tmp_path / "aeat.exe"
    executable.write_bytes(b"")

    readback = driver._assert_tui_replacement(
        cli_executable=executable,
        store=tmp_path,
        authority_root=tmp_path,
        passphrase=secrets.token_urlsafe(),
        year=2025,
        seeded=(before, urban_rent),
    )

    assert readback.generation_changed is True
    assert readback.parent_matches is True
    assert readback.mode_replace is True
    assert readback.urban_rent_unchanged is True
    assert readback.count_matches is False


def test_tui_annual_oracle_uses_only_the_two_visible_capture_allocations() -> None:
    rent, professional = driver._tui_captured_annual_slices(2025)

    assert (rent.modelo, professional.modelo) == ("180", "190")
    assert rent.expected_capture_allocation_count == 1
    assert professional.expected_capture_allocation_count == 1
    assert tuple(period.expected_observation_count for period in rent.source_periods) == (0, 1, 0, 0)
    assert tuple(period.expected_observation_count for period in professional.source_periods) == (0, 1, 0, 0)
    assert dict(professional.expected_type2_rows[0].values)["modelo-190-perc-subclave"] == "01"
    assert (
        dict(rent.expected_type2_rows[0].values)["modelo-180-perc-referencia-catastral"]
        == driver._TUI_PROPERTY_REFERENCE
    )


def test_tui_annual_no_activity_attestation_targets_the_active_tui_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from .. import cli_journey

    rent, _professional = driver._tui_captured_annual_slices(2025)
    calls: list[tuple[str, ...]] = []

    def fake_require(_cli: object, command: tuple[str, ...], **_kwargs: object) -> dict[str, object]:
        calls.append(command)
        return {}

    monkeypatch.setattr(cli_journey, "_require_result", fake_require)
    tokens = driver._attest_tui_captured_no_activity_periods(
        cli=object(),
        slice_=rent,
        captures_by_period={"2T": [rent.captures[0]]},
        year=2025,
    )

    assert tokens == frozenset({"2025:1T", "2025:3T", "2025:4T"})
    assert calls == [
        (
            "config",
            "profile",
            "edit",
            "retenciones-installed-tui",
            "--quiet",
            "--modelo-115-no-relevant-payment-periods",
            "2025:1T,2025:3T,2025:4T",
        )
    ]


def test_tui_to_cli_annual_runner_records_only_local_annual_lifecycle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[dict[str, object]] = []

    def fake_child(**kwargs: object) -> SimpleNamespace:
        observed.append(kwargs)
        receipt_path = kwargs["receipt_path"]
        assert isinstance(receipt_path, Path)
        mode = tuple(kwargs["child_args"])[1]
        document = _document(
            fresh_readback=(
                ["modelo-111", "modelo-115"] if mode == "reopen" else ["not_yet_reopened", "not_yet_reopened"]
            )
        )
        receipt_path.write_text(json.dumps(document), encoding="utf-8")
        return SimpleNamespace(returncode=0, receipt_status="proven")

    monkeypatch.setattr(driver, "run_installed_tui_child_process", fake_child)
    monkeypatch.setattr(driver, "_run_tui_to_cli_annual_lifecycle", lambda **_kwargs: driver._CLI_ANNUAL_LIFECYCLE)

    receipt = driver.run_installed_tui_to_cli_annual_journey(
        python_executable=Path(__file__).resolve(),
        workspace_root=tmp_path,
        authority_root=tmp_path,
        output_root=tmp_path / "annual",
    )

    assert receipt.status == "proven"
    assert receipt.annual_cli_lifecycle == driver._CLI_ANNUAL_LIFECYCLE
    assert receipt.fresh_readback == ("modelo-111", "modelo-115")
    annual = json.loads((tmp_path / "annual" / "tui-to-cli-annual.json").read_text(encoding="utf-8"))
    assert annual == {
        "annual_lifecycle": list(driver._CLI_ANNUAL_LIFECYCLE),
        "annual_models": ["180", "190"],
        "source_history": "local_only",
        "status": "proven",
    }
    assert [tuple(call["child_args"])[1] for call in observed] == ["capture", "reopen"]


def test_tui_to_cli_annual_runner_preserves_its_exact_safe_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_child(**kwargs: object) -> SimpleNamespace:
        receipt_path = kwargs["receipt_path"]
        assert isinstance(receipt_path, Path)
        receipt_path.write_text(
            json.dumps(_document(fresh_readback=["not_yet_reopened", "not_yet_reopened"])),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, receipt_status="proven")

    monkeypatch.setattr(driver, "run_installed_tui_child_process", fake_child)
    monkeypatch.setattr(
        driver,
        "_run_tui_to_cli_annual_lifecycle",
        lambda **_kwargs: (_ for _ in ()).throw(driver.RetencionesInstalledTuiError("annual_public_refusal")),
    )

    with pytest.raises(driver.RetencionesInstalledTuiError, match="annual continuation refused"):
        driver.run_installed_tui_to_cli_annual_journey(
            python_executable=Path(__file__).resolve(),
            workspace_root=tmp_path,
            authority_root=tmp_path,
            output_root=tmp_path / "annual-refusal",
        )

    refusal = json.loads((tmp_path / "annual-refusal" / "tui-to-cli-annual.json").read_text(encoding="utf-8"))
    assert refusal == {
        "code": "annual_public_refusal",
        "stage": "annual_continuation",
        "status": "failed",
        "verification": None,
    }


def test_annual_verification_refusal_retains_only_safe_public_identifiers() -> None:
    refusal = driver._annual_verification_refusal(
        modelo="190",
        verified={
            "granted_verificado_completo": False,
            "missing_required_casilla_ids": ["190.001", "190.001", 5],
            "findings": [
                {
                    "kind": "required_field_missing",
                    "casilla_id": "190.002",
                    "expectation_id": "annual_detail",
                    "message": "must never be retained",
                },
                {"kind": "cross_period_dependency"},
                "not-a-finding",
            ],
        },
    )

    assert str(refusal) == "tui-190-annual_verification_not_complete"
    assert refusal.findings == (
        "casilla_id:190.002",
        "expectation_id:annual_detail",
        "kind:cross_period_dependency",
        "kind:required_field_missing",
    )
    assert refusal.missing_casilla_ids == ("190.001",)
    assert "must never be retained" not in repr(refusal.findings)


def test_parent_uses_two_stdin_credential_children_without_retaining_the_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[dict[str, object]] = []

    def fake_child(**kwargs: object) -> SimpleNamespace:
        observed.append(kwargs)
        receipt_path = kwargs["receipt_path"]
        assert isinstance(receipt_path, Path)
        mode = tuple(kwargs["child_args"])[1]
        assert mode in {"mutate", "reopen"}
        document = _document(
            fresh_readback=(
                ["not_yet_reopened", "not_yet_reopened"] if mode == "mutate" else ["modelo-111", "modelo-115"]
            )
        )
        if mode == "mutate":
            document["cli_seeded_scopes"] = ["modelo-111", "modelo-115"]
            document["tui_mutation"] = "professional_replace"
        receipt_path.write_text(json.dumps(document), encoding="utf-8")
        return SimpleNamespace(returncode=0, receipt_status="proven")

    monkeypatch.setattr(driver, "run_installed_tui_child_process", fake_child)
    monkeypatch.setattr(
        driver,
        "_seed_cli_evidence",
        lambda **_kwargs: (
            driver._WindowReadback("111", 2, "scope-111", "a" * 64, 2, "b" * 64, "append"),
            driver._WindowReadback("115", 1, "scope-115", "c" * 64, 1, "d" * 64, "append"),
        ),
    )
    monkeypatch.setattr(
        driver,
        "_assert_tui_replacement",
        lambda **_kwargs: driver._ReplacementReadback(True, True, True, True, True),
    )
    receipt = driver.run_installed_tui_withholding_journey(
        python_executable=Path(__file__).resolve(),
        workspace_root=tmp_path,
        authority_root=tmp_path,
        output_root=tmp_path / "run",
    )

    assert receipt.status == "proven"
    assert receipt.cli_periodic_lifecycle == ()
    assert receipt.cli_seeded_scopes == ("modelo-111", "modelo-115")
    assert receipt.tui_mutation == "professional_replace"
    assert [tuple(call["child_args"])[1] for call in observed] == ["mutate", "reopen"]
    assert all(call["child_module"] == "dev.acceptance.retenciones.installed_tui_withholding" for call in observed)
    assert all(call["timeout_seconds"] == 1200 for call in observed)
    assert "passphrase" not in json.dumps(receipt.to_dict())
