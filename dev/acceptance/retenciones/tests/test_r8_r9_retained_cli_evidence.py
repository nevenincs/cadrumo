"""Integrity audit of retained installed-CLI R8/R9 evidence; this does not rerun it."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_retained_installed_cli_evidence_keeps_r8_r9_states_and_provenance_distinct() -> None:
    """Audit prior public CLI receipts without relabelling them as a current run."""
    artifacts = Path(__file__).resolve().parents[4] / ".agents/session-briefs/handoffs/artifacts/retenciones-01"
    m190_manifest = _document(artifacts / "manifest-annual-m190-proven-730ab66aa9.json")
    m180_manifest = _document(artifacts / "manifest-annual-m180-proven-m190-grouping-blocked-8ee967def7.json")
    missing_detail = _document(artifacts / "modelo-190-2025-0A-required-detail-blocker-receipt.json")
    m190_receipt = _document(artifacts / "modelo-190-2025-0A-proven-receipt-730ab66aa9.json")
    m180_receipt = _document(artifacts / "modelo-180-2025-0A-proven-receipt-8ee967def7.json")

    _assert_retained_file(m190_manifest, artifacts, "modelo_190_proof", "receipt")
    _assert_retained_file(m190_manifest, artifacts, "modelo_190_proof", "validated_export")
    _assert_retained_file(m180_manifest, artifacts, "modelo_180_proof", "receipt")
    _assert_retained_file(m180_manifest, artifacts, "modelo_180_proof", "validated_export")

    installed = _mapping(m190_manifest, "installed_product")
    assert m190_manifest["outcome"] == {
        "modelo_190": "proven_selected_annual_slice",
        "campaign_scope": "selected_annual_slices",
        "live_submission_attempted": False,
    }
    assert m190_receipt["source_identity"] == installed["source_identity"]
    assert m190_receipt["package_identity"] == f"wheel_sha256:{installed['wheel_sha256']}"
    assert m190_receipt["campaign_scope"] == "selected_annual_slices"
    assert m190_receipt["status"] == "partial"

    assert missing_detail["status"] == "failed"
    assert missing_detail["stage"] == "professional-190-annual-detail:work_verify"
    assert missing_detail["diagnostic_code"] == "annual_verification_not_complete"
    assert missing_detail["retention"] == "caller_owned_failure_artifacts_only; no stdout_or_stderr_retained"
    assert any(
        command.get("notice_codes", []).count("modelo.work.verify.finding.missing_required_casilla") == 6
        for command in _commands(missing_detail)
    )

    m190_slice = _single_slice(m190_receipt, "190")
    assert m190_slice["reopened_observation_counts"] == {"1T": 0, "2T": 3, "3T": 0, "4T": 0}
    assert _source_periods(m190_slice, "no_relevant_payment") == ("1T", "3T", "4T")
    assert all(
        source["source_workflow"] == "m111_no_retenciones_attestation"
        and source["filing_record_id"] is None
        and source["live_submission"] is False
        for source in _sources(m190_slice, "no_relevant_payment")
    )
    assert [row["modelo-190-perc-subclave"] for row in _type2_rows(m190_slice)] == ["01", "02"]

    m180_slice = _single_slice(m180_receipt, "180")
    assert m180_slice["reopened_observation_counts"] == {"1T": 1, "2T": 2, "3T": 0, "4T": 0}
    assert _source_periods(m180_slice, "no_relevant_payment") == ("3T", "4T")
    assert all(
        source["source_workflow"] == "m115_no_relevant_payment_attested_local_filing_record"
        and isinstance(source["filing_record_id"], str)
        and source["live_submission"] is False
        for source in _sources(m180_slice, "no_relevant_payment")
    )
    assert any(
        "modelo.export.local_export_not_official_evidence" in command.get("notice_codes", [])
        for command in _commands(m180_receipt)
    )


def _document(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _mapping(document: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = document.get(key)
    assert isinstance(value, Mapping), key
    return cast(Mapping[str, object], value)


def _assert_retained_file(
    manifest: Mapping[str, object], artifacts: Path, proof_key: str, artifact_key: str
) -> None:
    proof = _mapping(manifest, proof_key)
    expected = _mapping(proof, artifact_key)
    path = artifacts / str(expected["path"])
    assert path.is_file(), path
    assert path.stat().st_size == expected["bytes"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"]


def _commands(document: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    commands = document.get("commands")
    assert isinstance(commands, list)
    assert all(isinstance(command, Mapping) for command in commands)
    return tuple(cast(Mapping[str, object], command) for command in commands)


def _single_slice(document: Mapping[str, object], modelo: str) -> Mapping[str, object]:
    slices = document.get("slices")
    assert isinstance(slices, list)
    matches = [slice_ for slice_ in slices if isinstance(slice_, Mapping) and slice_.get("modelo") == modelo]
    assert len(matches) == 1
    return cast(Mapping[str, object], matches[0])


def _sources(slice_: Mapping[str, object], evidence_state: str) -> tuple[Mapping[str, object], ...]:
    periods = slice_.get("source_periods")
    assert isinstance(periods, list)
    matches = [
        period
        for period in periods
        if isinstance(period, Mapping) and period.get("evidence_state") == evidence_state
    ]
    return tuple(cast(Mapping[str, object], period) for period in matches)


def _source_periods(slice_: Mapping[str, object], evidence_state: str) -> tuple[str, ...]:
    return tuple(cast(str, source["period"]) for source in _sources(slice_, evidence_state))


def _type2_rows(slice_: Mapping[str, object]) -> list[Mapping[str, object]]:
    validation = _mapping(slice_, "export_validation")
    rows = validation.get("parsed_type2_rows")
    assert isinstance(rows, list)
    assert all(isinstance(row, Mapping) for row in rows)
    return [cast(Mapping[str, object], row) for row in rows]
