"""The CLI serves the work-income limitation on an export of a return resting on a payer record.

The deductions only the filer can evidence (union dues, professional-body fees, legal-defence costs
and the geographic-mobility increase) are not computed, and leaving them out can only raise the tax.
``export_modelo_revision`` marks such a result ``trabajo_deductions_not_computed``; the CLI then emits
a non-blocking warning on the typed Notice channel, in the words verification serves, and a result
without the mark emits none.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....application.modelo.export_contracts import ModeloExportResult
from ....application.modelo.export_projection import ModeloFicheroBoePublicReceipt
from ....core.config import override_settings
from ....core.i18n.render import tr
from ....core.json_contract import NoticeSeverity
from ....core.period import Period
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ..modelo_export_commands import export_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SUPPORT = published_supported_filing_years()
assert _SUPPORT is not None
_YEAR = max(_SUPPORT.years)
_LIMITATION_CODE = "modelo.export.trabajo_deduction_not_computed"


def _result(*, trabajo_deductions_not_computed: bool = False, tmp_path: Path) -> ModeloExportResult:
    return ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        output_path=tmp_path / "modelo-100.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime.now(UTC),
        actor="operator",
        bucket_event_id="event-1",
        trabajo_deductions_not_computed=trabajo_deductions_not_computed,
    )


def test_an_export_resting_on_a_work_income_record_serves_the_limitation_in_verification_words(tmp_path: Path) -> None:
    result = _result(trabajo_deductions_not_computed=True, tmp_path=tmp_path)

    with override_settings(cadrumo_output_language="en"):
        notices = export_notices(result)

    limitation = next(notice for notice in notices if notice.code == _LIMITATION_CODE)
    assert limitation.severity is NoticeSeverity.WARNING
    assert limitation.message == tr("application.modelo.findings.trabajo_deduction_not_computed", locale="en")
    for box in ("0014", "0015", "0016", "0020"):
        assert box in limitation.message
    assert limitation.context == {"modelo": "100", "filing_year": str(_YEAR), "period": "0A"}


def test_an_export_without_work_income_emits_no_limitation(tmp_path: Path) -> None:
    assert _LIMITATION_CODE not in {notice.code for notice in export_notices(_result(tmp_path=tmp_path))}


def test_the_limitation_survives_the_public_receipt_round_trip(tmp_path: Path) -> None:
    result = _result(trabajo_deductions_not_computed=True, tmp_path=tmp_path)

    restored = ModeloFicheroBoePublicReceipt.from_result(result).to_result()

    assert restored.trabajo_deductions_not_computed is True
