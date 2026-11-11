"""Verify and export restate what the calculation noted, with each note's own figures."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ....application.modelo.calculation_notes import what_to_do_locale_key
from ....application.modelo.export_contracts import ModeloExportResult
from ....application.modelo.export_projection import ModeloFicheroBoePublicReceipt
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision_sources import (
    CalculationNoteFact,
    CalculationNoteSentence,
    RecordedCalculationNote,
)
from ..modelo_export_commands import export_notices, export_text_lines
from ..modelo_rendering import recorded_note_notices

_YEAR = filing_year_envelope().horizon


pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _gap(element: str, amount: str) -> RecordedCalculationNote:
    return RecordedCalculationNote(
        reason="activity_asset_claim_gap",
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.CLAIM_GAP_ACCRUED,
            elements=(element,),
            start=date(_YEAR, 1, 1).isoformat(),
            end=date(_YEAR + 1, 1, 1).isoformat(),
            amount=amount,
            box="0208",
        ),
    )


def test_an_export_says_each_note_in_its_notices_and_its_lines(tmp_path: Path) -> None:
    exported = ModeloExportResult(
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
        exported_at=datetime(_YEAR + 1, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        calculation_notes=(_gap("furniture", "1200.00"), _gap("lathe", "600.00")),
    )

    restored = ModeloFicheroBoePublicReceipt.from_result(exported).to_result()

    notices = [notice.message for notice in export_notices(restored)]
    lines = export_text_lines(restored)
    for figure in ("1.200,00", "600,00"):
        assert any(figure in message for message in notices)
        assert any(figure in line for line in lines)


def test_a_restated_note_says_its_level_its_facts_and_what_to_do() -> None:
    note = RecordedCalculationNote(
        reason="activity_asset_disposal_finding",
        element_names=(("furniture", "Office desk"),),
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.DISPOSAL_FIGURE_IN_BOX,
            elements=("furniture",),
            date=date(_YEAR, 6, 30).isoformat(),
            amount="897.53",
            box="1654",
        ),
    )

    (notice,), (line,) = recorded_note_notices((note,), code="modelo.calculation_note")

    assert all(part in notice.message for part in ("897,53", "Office desk", f"30 jun {_YEAR}", "1654"))
    assert notice.context is not None
    assert notice.context["level"] == "check"
    assert notice.message in line
    assert tr(what_to_do_locale_key("activity_asset_disposal_finding")) in line
