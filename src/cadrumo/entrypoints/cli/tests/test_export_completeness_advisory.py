"""The CLI surfaces a coverage advisory when a fichero-BOE was not verified.

A fixed-width fichero-BOE whose revision declares no calculation-completeness
manifest cannot be structural-parity-verified (the pre-write gate only runs when a
manifest is present). ``export_modelo_revision`` marks such a result
``completeness_unverified``; the CLI must then emit a non-blocking coverage
advisory on the typed Notice channel, so the operator learns the export was not
completeness-checked rather than being silently reassured.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....application.modelo._export import ModeloExportResult
from ....core import Period
from ....core.json_contract import NoticeSeverity
from .._modelo_export_cli import _export_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ADVISORY_CODE = "modelo.export.completeness_unverified"


def _result(*, completeness_unverified: bool, tmp_path: Path) -> ModeloExportResult:
    return ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        output_path=tmp_path / "modelo-130.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        completeness_unverified=completeness_unverified,
    )


def test_unverified_export_emits_coverage_advisory(tmp_path: Path) -> None:
    result = _result(completeness_unverified=True, tmp_path=tmp_path)

    notices = _export_notices(result)
    codes = {notice.code for notice in notices}

    assert _ADVISORY_CODE in codes
    advisory = next(notice for notice in notices if notice.code == _ADVISORY_CODE)
    assert advisory.severity is NoticeSeverity.WARNING
    assert "not completeness-verified" in advisory.message.lower()
    assert advisory.context is not None
    assert advisory.context["reason"] == "no_completeness_manifest"


def test_verified_export_emits_no_coverage_advisory(tmp_path: Path) -> None:
    result = _result(completeness_unverified=False, tmp_path=tmp_path)

    notices = _export_notices(result)
    codes = {notice.code for notice in notices}

    # The default (gate ran, or non-fichero-BOE transport) carries no advisory.
    assert _ADVISORY_CODE not in codes
