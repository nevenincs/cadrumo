"""Focused receipt-shape checks for the PROFILE-01 installed TUI supervisor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.acceptance.income_tax.installed_tui_child import InstalledTuiChildProcessEvidence

from ..tui_journey import (
    ProfileInstalledAcceptanceError,
    ProfileInstalledAcceptanceEvidence,
    ProfileInstalledAcceptanceFailure,
    _parse_tui_child_evidence,
    write_profile_installed_receipt,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _outer(*, status: str = "proven", returncode: int = 0) -> InstalledTuiChildProcessEvidence:
    return InstalledTuiChildProcessEvidence(
        child_module="dev.acceptance.profile.installed_tui_child",
        returncode=returncode,
        receipt_status=status,
        receipt_sha256="a" * 64,
        receipt_size=160,
        stdout_sha256="b" * 64,
        stderr_sha256="c" * 64,
    )


def test_tui_child_receipt_keeps_only_public_operation_identity(tmp_path: Path) -> None:
    """The outer driver accepts a complete value-free installed-child receipt."""
    receipt = tmp_path / "child.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "profile-01-installed-tui-row-child-v1",
                "status": "proven",
                "operation": "assert-clear",
                "product_origin": "site-packages",
                "product_init_sha256": "d" * 64,
                "row_key": "4",
                "row_visible": True,
                "clear_visible_absent": True,
                "selector_fact_visible": True,
                "no_op_observed": False,
            }
        ),
        encoding="utf-8",
    )

    evidence = _parse_tui_child_evidence(outer=_outer(), receipt_path=receipt, operation="assert-clear")

    assert evidence.row_key == "4"
    assert evidence.clear_visible_absent is True
    assert evidence.selector_fact_visible is True
    assert evidence.no_op_observed is False


def test_tui_no_op_receipt_is_typed_and_preserved(tmp_path: Path) -> None:
    """A visible no-op has an explicit, sanitized observation in the child receipt."""
    receipt = tmp_path / "no-op.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "profile-01-installed-tui-row-child-v1",
                "status": "proven",
                "operation": "no-op",
                "product_origin": "site-packages",
                "product_init_sha256": "d" * 64,
                "row_key": "4",
                "row_visible": True,
                "clear_visible_absent": False,
                "selector_fact_visible": True,
                "no_op_observed": True,
            }
        ),
        encoding="utf-8",
    )

    evidence = _parse_tui_child_evidence(outer=_outer(), receipt_path=receipt, operation="no-op")

    assert evidence.operation == "no-op"
    assert evidence.no_op_observed is True


def test_top_level_receipt_makes_no_op_observation_auditable() -> None:
    """The durable aggregate receipt retains a typed no-op observation."""
    evidence = ProfileInstalledAcceptanceEvidence(
        schema_version="fixture-v1",
        status="proven",
        pattern_id="ACCEPTANCE-01",
        pattern_revision="1.6",
        brief_id="PROFILE-01",
        brief_revision="0.1",
        scenario="fixture",
        year=2026,
        source_identity="fixture-source",
        package_identity="fixture-package",
        cli_executable="fixture-cli",
        cli_executable_sha256="a" * 64,
        tui_python="fixture-python",
        tui_python_sha256="b" * 64,
        run_root="fixture-root",
        journeys=(),
        no_op_observed=True,
        retention="fixture",
    )

    receipt = evidence.to_dict()

    assert receipt["no_op_observed"] is True


def test_tui_child_failure_is_not_promoted_to_acceptance(tmp_path: Path) -> None:
    """A zero-looking receipt cannot hide a failed child status or nonzero exit."""
    receipt = tmp_path / "failed.json"
    receipt.write_text('{"status":"failed","failure_code":"safe"}', encoding="utf-8")

    with pytest.raises(ProfileInstalledAcceptanceError) as raised:
        _parse_tui_child_evidence(outer=_outer(status="failed", returncode=2), receipt_path=receipt, operation="remove")

    assert raised.value.diagnostic_code == "TUI_CHILD_NOT_PROVEN"


def test_receipt_writer_refuses_to_replace_a_prior_outcome(tmp_path: Path) -> None:
    """A later run cannot overwrite another run's durable acceptance receipt."""
    target = tmp_path / "receipt.json"
    target.write_text("{}", encoding="utf-8")
    failure = ProfileInstalledAcceptanceFailure(
        schema_version="fixture-v1",
        status="failed",
        pattern_id="ACCEPTANCE-01",
        pattern_revision="1.6",
        brief_id="PROFILE-01",
        brief_revision="0.1",
        scenario="fixture",
        source_identity="fixture-source",
        package_identity="fixture-package",
        stage="fixture",
        diagnostic_code="fixture",
        completed_paths=(),
        retention="fixture",
    )

    with pytest.raises(ProfileInstalledAcceptanceError) as raised:
        write_profile_installed_receipt(path=target, evidence=failure)

    assert raised.value.diagnostic_code == "RECEIPT_ALREADY_EXISTS"
    assert target.read_text(encoding="utf-8") == "{}"
