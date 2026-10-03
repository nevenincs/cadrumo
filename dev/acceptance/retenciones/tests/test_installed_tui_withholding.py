"""Refuse partial or misleading installed withholding continuation receipts."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dev.acceptance.income_tax import tui_navigation
from dev.acceptance.income_tax.installed_tui_child import InstalledTuiChildError
from dev.acceptance.income_tax.tui_contracts import TuiJourneyError
from dev.acceptance.installed_cli import CommandEvidence, InstalledCliError

from .. import installed_tui_seed, installed_tui_withholding
from ..cli_contracts import RetencionesInstalledCliError
from ..installed_tui_seed import WithholdingWork
from ..installed_tui_withholding import main, validate_child_receipt

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("fault", "message"),
    (
        ("checkout_product", "requested admitted continuation"),
        ("live_submission_claim", "requested admitted continuation"),
        ("wrong_manifest", "requested admitted continuation"),
        ("empty_palette_claim", "requested admitted continuation"),
        ("missing_work", "skipped a required work unit"),
        ("wrong_coordinate", "another work coordinate"),
        ("empty_artifact", "durable artifact identity"),
        ("skipped_export", "required lifecycle terminal"),
        ("file_before_export", "required lifecycle terminal"),
        ("unobserved_reopen", "reopen a recorded declaration"),
    ),
)
def test_child_success_requires_the_whole_requested_public_continuation(fault: str, message: str) -> None:
    """A child's nominal proven status cannot cover an omitted runtime boundary."""
    target = WithholdingWork("public-work-key", "111", 2025, "2T", "2025", "professional-190")
    work: dict[str, Any] = {
        "target": asdict(target),
        "independent_export_matches": True,
        "artifact": {"name": "modelo-111-2025-2T.boe", "size": 350, "sha256": "b" * 64},
        "operations": ["modelo.work.calculate", "modelo.work.verify", "modelo.export", "modelo.work.file"],
        "recorded_reopen": True,
    }
    document: dict[str, Any] = {
        "schema_version": "retenciones-installed-runtime-tui-continuation-v1",
        "status": "proven",
        "phase": "lifecycle",
        "manifest_sha256": "a" * 64,
        "authority_generation": "published-generation",
        "product_origin": "site-packages",
        "product_init_sha256": "c" * 64,
        "withholding_capture": "unavailable_and_withheld_from_populated_palette",
        "works": [work],
        "live_submission": False,
        "aeat_acceptance_claimed": False,
    }
    phase = "lifecycle"
    if fault == "checkout_product":
        document["product_origin"] = "checkout"
    elif fault == "live_submission_claim":
        document["live_submission"] = True
    elif fault == "wrong_manifest":
        document["manifest_sha256"] = "d" * 64
    elif fault == "empty_palette_claim":
        document["withholding_capture"] = "empty_palette"
    elif fault == "missing_work":
        document["works"] = []
    elif fault == "wrong_coordinate":
        work["target"] = {**asdict(target), "period": "3T"}
    elif fault == "empty_artifact":
        work["artifact"]["size"] = 0
    elif fault == "skipped_export":
        work["operations"].remove("modelo.export")
    elif fault == "file_before_export":
        work["operations"][-2:] = ["modelo.work.file", "modelo.export"]
    else:
        phase = "reopen"
        document["phase"] = phase
        work["recorded_reopen"] = False
    with pytest.raises(InstalledTuiChildError, match=message):
        validate_child_receipt(
            document,
            phase=phase,
            targets=(target,),
            manifest_sha256="a" * 64,
            authority_generation="published-generation",
        )


def test_existing_caller_receipt_is_preserved_on_refusal(tmp_path: Path) -> None:
    """A fresh-run requirement never replaces a caller's previous evidence."""
    receipt = tmp_path / "retained-receipt.json"
    previous = b'{"status":"caller-retained"}\n'
    receipt.write_bytes(previous)
    with pytest.raises(SystemExit) as refused:
        main(("--output-dir", str(tmp_path / "outputs"), "--receipt", str(receipt)))
    assert refused.value.code == 2
    assert receipt.read_bytes() == previous


def test_complete_setup_failure_receipt_retains_actual_stage_and_safe_commands(tmp_path: Path, monkeypatch) -> None:
    """The create wrapper cannot hide the second public command's typed failure."""
    secret = f"{tmp_path.name}-synthetic-credential"
    commands = (
        CommandEvidence("config profile create", 0, "warning", ("PROFILE_LOGIN_REQUIRED",)),
        CommandEvidence(
            "config profile complete-setup",
            2,
            "error",
            (),
            "REFUSED/runtime_endpoint_untrusted",
            "REFUSED_LOCAL_RUNTIME",
        ),
    )
    original = InstalledCliError(secret, diagnostic_code="REFUSED_LOCAL_RUNTIME", commands=commands)

    def refuse_profile(cli, *, year):
        raise RetencionesInstalledCliError(stage="profile_create", diagnostic_code="wrapper") from original

    monkeypatch.setattr(installed_tui_seed, "_create_withholding_profile", refuse_profile)

    def run_parent(args):
        return installed_tui_seed.seed_withholding_work(type("Cli", (), {"commands": list(commands)})(), year=2025)

    monkeypatch.setattr(installed_tui_withholding, "_run_parent", run_parent)
    receipt = tmp_path / "failed.json"
    assert main(("--output-dir", str(tmp_path / "outputs"), "--receipt", str(receipt))) == 2
    contents = receipt.read_text(encoding="utf-8")
    document = json.loads(contents)
    assert document["status"] == "failed"
    assert document["stage"] == "profile_complete_setup"
    assert document["diagnostic_code"] == "REFUSED_LOCAL_RUNTIME"
    assert document["cli_commands"][-1]["refusal"] == "REFUSED/runtime_endpoint_untrusted"
    assert secret not in contents


def test_pilot_failure_receipt_keeps_public_surface_without_private_notice(tmp_path: Path, monkeypatch) -> None:
    """A failed native control retains its reason and mounted IDs, never its notice."""
    secret = f"{tmp_path.name}-private-notice-and-credential"
    screen = SimpleNamespace(id="modelo-workbench", query=lambda _: [SimpleNamespace(id="wb-next")])
    pilot: Any = SimpleNamespace(
        app=SimpleNamespace(screen=screen, query=lambda _: [SimpleNamespace(id="home-agenda")])
    )
    monkeypatch.setattr(tui_navigation, "_stack_text", lambda *_args: secret)

    def run_child(args):
        try:
            tui_navigation._require_fresh_notice(pilot, label="modelo.export")
        except TuiJourneyError as error:
            raise installed_tui_withholding._pilot_failure(error, pilot=pilot, stage="lifecycle") from error

    monkeypatch.setattr(installed_tui_withholding, "_run_child", run_child)
    receipt = tmp_path / "failed.json"
    assert (
        main(
            (
                "--child-phase",
                "lifecycle",
                "--manifest",
                str(tmp_path / "manifest.json"),
                "--output-dir",
                str(tmp_path / "outputs"),
                "--receipt",
                str(receipt),
            )
        )
        == 2
    )
    contents = receipt.read_text(encoding="utf-8")
    document = json.loads(contents)
    assert document["phase"] == "lifecycle"
    assert document["stage"] == "lifecycle._require_fresh_notice"
    assert document["error"] == (
        "installed withholding lifecycle._require_fresh_notice failed: modelo.export would start under an earlier "
        "workbench notice; open the declaration afresh first"
    )
    assert document["diagnostic"] == {
        "current_screen_class": "SimpleNamespace",
        "current_screen_id": "modelo-workbench",
        "mounted_widget_ids": ["home-agenda", "wb-next"],
    }
    assert document["live_submission"] is False
    assert document["aeat_acceptance_claimed"] is False
    assert secret not in contents


@pytest.mark.parametrize("private_suffix", (" (notice private-facts)", ": private-facts", " private-facts"))
def test_operation_failure_reason_discards_dynamic_detail(private_suffix: str) -> None:
    """Known operation identities survive while modal values stay out of receipts."""
    error = TuiJourneyError(f"modelo.work.verify did not expose a terminal operation status{private_suffix}")
    assert installed_tui_withholding._safe_tui_failure_reason(error) == (
        "modelo.work.verify did not expose a terminal operation status"
    )
    assert installed_tui_withholding._safe_tui_failure_reason(TuiJourneyError("private-facts")) == (
        "installed withholding public control failed"
    )


def test_parent_receipt_retains_child_phase_and_reportable_reason(tmp_path: Path, monkeypatch) -> None:
    """The parent names the failed child phase instead of flattening it to a class."""
    child = tmp_path / "lifecycle.json"
    child.write_text(
        json.dumps(
            {
                "status": "failed",
                "error": "installed withholding lifecycle failed: the workbench did not open its export dialog",
            }
        ),
        encoding="utf-8",
    )

    def run_parent(args):
        raise installed_tui_withholding._child_process_failure(phase="lifecycle", receipt=child)

    monkeypatch.setattr(installed_tui_withholding, "_run_parent", run_parent)
    receipt = tmp_path / "parent.json"
    assert main(("--output-dir", str(tmp_path / "outputs"), "--receipt", str(receipt))) == 2
    document = json.loads(receipt.read_text(encoding="utf-8"))
    assert document["phase"] == "parent"
    assert document["stage"] == "lifecycle.child"
    assert "lifecycle child failed" in document["error"]
    assert "the workbench did not open its export dialog" in document["error"]
