"""Unit tests for the typed declaration-export / declaration-verify surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from . import (
    DeclarationExportFormat,
    DeclarationExportResult,
    DeclarationVerifyResult,
    DeclarationVerifyVerdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_HEX_DIGEST = "a" * 64
_EXPORT_PATH = Path("exports/m130-2026Q1.txt")
_OTHER_EXPORT_PATH = Path("exports/x.txt")


def _narrative() -> str:
    narrative: str = "filing.test_export.narrative"
    return narrative


def test_format_enum_carries_cli_values() -> None:
    assert DeclarationExportFormat.FICHERO_BOE.value == "fichero-boe"


def test_verdict_enum_orders_match_drift_missing() -> None:
    assert {item.value for item in DeclarationVerifyVerdict} == {"match", "drift", "missing"}


def test_export_result_round_trips_canonical_fields() -> None:
    receipt = DeclarationExportResult(
        draft_id="d-130-2026Q1",
        modelo="130",
        period="2026Q1",
        format=DeclarationExportFormat.FICHERO_BOE,
        output_path=_EXPORT_PATH,
        byte_size=512,
        file_sha256=_HEX_DIGEST,
        exported_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    assert receipt.draft_id == "d-130-2026Q1"
    assert receipt.format is DeclarationExportFormat.FICHERO_BOE
    assert receipt.output_path == _EXPORT_PATH
    assert receipt.byte_size == 512
    assert receipt.file_sha256 == _HEX_DIGEST
    assert receipt.narrative


def test_export_result_rejects_uppercase_digest() -> None:
    with pytest.raises(ValueError):
        DeclarationExportResult(
            draft_id="d",
            modelo="130",
            period="2026Q1",
            format=DeclarationExportFormat.FICHERO_BOE,
            output_path=_OTHER_EXPORT_PATH,
            byte_size=1,
            file_sha256="A" * 64,
            exported_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_export_result_rejects_non_hex_digest() -> None:
    with pytest.raises(ValueError):
        DeclarationExportResult(
            draft_id="d",
            modelo="130",
            period="2026Q1",
            format=DeclarationExportFormat.FICHERO_BOE,
            output_path=_OTHER_EXPORT_PATH,
            byte_size=1,
            file_sha256="z" * 64,
            exported_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_export_result_is_frozen() -> None:
    receipt = DeclarationExportResult(
        draft_id="d",
        modelo="130",
        period="2026Q1",
        format=DeclarationExportFormat.FICHERO_BOE,
        output_path=_OTHER_EXPORT_PATH,
        byte_size=0,
        file_sha256=_HEX_DIGEST,
        exported_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    with pytest.raises(ValidationError):
        receipt.byte_size = 1  # type: ignore[misc]


def test_verify_result_match_carries_no_mismatched_casillas() -> None:
    verdict = DeclarationVerifyResult(
        draft_id="d-130-2026Q1",
        file_path=_EXPORT_PATH,
        verdict=DeclarationVerifyVerdict.MATCH,
        mismatched_casillas=(),
        file_sha256=_HEX_DIGEST,
        verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    assert verdict.verdict is DeclarationVerifyVerdict.MATCH
    assert verdict.mismatched_casillas == ()


def test_verify_result_drift_lists_mismatched_casillas() -> None:
    verdict = DeclarationVerifyResult(
        draft_id="d",
        file_path=_OTHER_EXPORT_PATH,
        verdict=DeclarationVerifyVerdict.DRIFT,
        mismatched_casillas=("01", "07"),
        file_sha256=None,
        verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        narrative=_narrative(),
    )
    assert verdict.mismatched_casillas == ("01", "07")
    assert verdict.file_sha256 is None


def test_verify_result_rejects_blank_casilla_ids() -> None:
    with pytest.raises(ValueError):
        DeclarationVerifyResult(
            draft_id="d",
            file_path=_OTHER_EXPORT_PATH,
            verdict=DeclarationVerifyVerdict.DRIFT,
            mismatched_casillas=("", "07"),
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_verify_result_rejects_padded_casilla_ids() -> None:
    with pytest.raises(ValueError):
        DeclarationVerifyResult(
            draft_id="d",
            file_path=_OTHER_EXPORT_PATH,
            verdict=DeclarationVerifyVerdict.DRIFT,
            mismatched_casillas=(" 01 ",),
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )


def test_verify_result_rejects_short_digest() -> None:
    with pytest.raises(ValueError):
        DeclarationVerifyResult(
            draft_id="d",
            file_path=_OTHER_EXPORT_PATH,
            verdict=DeclarationVerifyVerdict.MATCH,
            file_sha256="abc",
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
            narrative=_narrative(),
        )
