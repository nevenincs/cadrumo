"""Contract checks for the RETENCIONES-01 installed-TUI withholding journey."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from .. import installed_tui_withholding as driver

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _document(*, fresh_readback: list[str]) -> dict[str, object]:
    return {
        "schema_version": "retenciones-01-installed-tui-withholding-v4",
        "status": "proven",
        "product_origin": "site-packages",
        "product_init_sha256": "a" * 64,
        "year": 2025,
        "professional_capture": "captured",
        "urban_rent_capture": "captured",
        "cli_periodic_lifecycle": [],
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
    assert receipt.unexercised == ("tui_only_historical_work_creation", "cli_to_tui_continuation")


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


def test_parent_uses_two_stdin_credential_children_without_retaining_the_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[dict[str, object]] = []

    def fake_child(**kwargs: object) -> SimpleNamespace:
        observed.append(kwargs)
        receipt_path = kwargs["receipt_path"]
        assert isinstance(receipt_path, Path)
        mode = tuple(kwargs["child_args"])[1]
        assert mode in {"capture", "reopen"}
        receipt_path.write_text(
            json.dumps(
                _document(
                    fresh_readback=(
                        ["not_yet_reopened", "not_yet_reopened"] if mode == "capture" else ["modelo-111", "modelo-115"]
                    )
                )
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, receipt_status="proven")

    monkeypatch.setattr(driver, "run_installed_tui_child_process", fake_child)
    monkeypatch.setattr(
        driver,
        "_run_tui_to_cli_periodic_lifecycle",
        lambda **_kwargs: driver._CLI_PERIODIC_LIFECYCLE,
    )
    receipt = driver.run_installed_tui_withholding_journey(
        python_executable=Path(__file__).resolve(),
        workspace_root=tmp_path,
        authority_root=tmp_path,
        output_root=tmp_path / "run",
    )

    assert receipt.status == "proven"
    assert receipt.cli_periodic_lifecycle == driver._CLI_PERIODIC_LIFECYCLE
    assert [tuple(call["child_args"])[1] for call in observed] == ["capture", "reopen"]
    assert all(call["child_module"] == "dev.acceptance.retenciones.installed_tui_withholding" for call in observed)
    assert all(call["timeout_seconds"] == 1200 for call in observed)
    assert "passphrase" not in json.dumps(receipt.to_dict())
