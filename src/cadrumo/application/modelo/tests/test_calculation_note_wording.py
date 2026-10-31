"""Every note sentence reads as words a person can act on, and a rename reaches them without moving a revision.

An id, a hash or a raw token in a sentence is a defect a person cannot do anything
with, so the whole family is rendered with facts of the shape the calculation
stores, in every language. Which facts a sentence takes comes from the catalogue's
own placeholders, so a sentence added to the family is covered without a new row.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from string import Formatter
from typing import cast

import pytest

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from ....core.i18n.render import lookup_translation
from ....domain.calculations.registry.actividad_asset_disposal_bindings import activity_asset_disposal_route_casillas
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    activity_asset_amortization_casillas,
)
from ....domain.calculations.registry.ledger_renta_income_bindings import renta_income_target_casilla
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ...actividad_asset.history import ActivityAssetHistory
from ...actividad_asset.ports import ActivityAssetHistoryRepository
from ...aggregation.tests.test_modelo_source_mesh_ledger import register_asset, resolve_m100
from ..calculation_notes import fact_locale_key, note_fact_text, read_element_names, read_recorded_notes
from ..printed_boxes import snapshot_printed_boxes
from ..work_form_issue_lines import form_issue_lines
from .test_work_form_gate_agreement import _checked_form, _revision, _work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPORT = published_supported_filing_years()
assert _SUPPORT is not None, "the published authority declares no support envelope"

_ASSET = "asset-" + "7f3a9c" * 6
_ROW = "e" * 64
_VALUES = {
    "start": "2025-01-01",
    "end": "2025-12-31",
    "date": "2025-06-30",
    "row_date": "2025-03-14",
    "period_end": "2025-03-31",
    "amount": "1200.00",
    "cost": "1500.00",
    "paid": "1400.00",
    "price": "1500.00",
    "base": "1400.00",
    "remainder": "100.00",
    "effect": "297.53",
    "transmission_value": "12000.00",
    "net_value": "11702.47",
    "row_amount": "1452.00",
    "box": "0208",
    "year": "2024",
    "count": "2",
}
_RAW = re.compile(
    r"[0-9a-f]{12,}"  # a hash or the tail of one
    r"|asset-|transaction:"  # a reference's own spelling
    r"|\b[a-z]+_[a-z_]+\b"  # a stored token
    r"|\{[a-z_]+\}"  # a placeholder left unfilled
    r"|\b[1-4]T\b|\b0A\b"  # a period's code
    r"|\d{4}-\d{2}-\d{2}"  # a date as stored rather than as the language writes it
)


def _placeholders(sentence: CalculationNoteSentence, language: str) -> set[str]:
    text = lookup_translation(fact_locale_key(sentence), locale=language)
    assert text is not None
    return {field for _, field, _, _ in Formatter().parse(text) if field is not None}


def _fact(sentence: CalculationNoteSentence, language: str) -> CalculationNoteFact:
    named = _placeholders(sentence, language)
    return CalculationNoteFact.of(
        sentence,
        elements=(_ASSET,) if named & {"element", "elements"} else (),
        rows=(_ROW,) if "row_date" in named else (),
        **{name: value for name, value in _VALUES.items() if name in named},
    )


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("sentence", tuple(CalculationNoteSentence))
@pytest.mark.parametrize("names", [((_ASSET, "Office laptop"),), ()], ids=["named", "unnamed"])
def test_no_sentence_shows_an_id_a_hash_or_a_raw_token(
    sentence: CalculationNoteSentence, language: str, names: tuple[tuple[str, str], ...]
) -> None:
    text = note_fact_text(_fact(sentence, language), element_names=names, locale=language)

    assert _RAW.search(text) is None, text
    if names and _placeholders(sentence, language) & {"element", "elements"}:
        assert "Office laptop" in text


def test_a_name_with_a_stored_look_still_reads_only_as_itself() -> None:
    fact = CalculationNoteFact.of(CalculationNoteSentence.ACCRUAL_UNAVAILABLE, elements=(_ASSET,))

    assert _ASSET not in note_fact_text(fact, locale="en")
    assert "An asset with no name" in note_fact_text(fact, locale="en")


def test_the_sentence_writes_dates_and_amounts_as_the_language_does() -> None:
    fact = CalculationNoteFact.of(
        CalculationNoteSentence.DISPOSAL_FIGURE_IN_BOX,
        elements=(_ASSET,),
        date="2025-06-30",
        amount="1200.00",
        box="1654",
    )

    assert "30/06/2025" in note_fact_text(fact, locale="es")
    assert "1.200,00" in note_fact_text(fact, locale="es")


def _described(name: str) -> ActivityAssetHistory:
    return ActivityAssetHistory(revisions=(register_asset("furniture", transaction_id="c" * 64),)).describe(
        "furniture",
        ActivityAssetDescriptorFacts(name=name),
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_a_rename_leaves_the_calculation_and_its_consumption_alone_and_the_sentence_shows_the_new_name(
    operation: PinnedAuthorityOperation,
) -> None:
    """Both calculations rest on one register but for a name, so the revision and its drift inputs are equal."""
    before, after = _described("Old desk"), _described("Standing desk")

    first, second = resolve_m100(before), resolve_m100(after)

    assert [item.fact for item in first.diagnostics] == [item.fact for item in second.diagnostics]
    assert first.provenance == second.provenance
    unit = _work_unit(operation)
    from ..calculation_bucket_actions import _unrouted_source_issues

    boxes = snapshot_printed_boxes(operation, operation.snapshot("100", filing_year=2025, period="0A"))
    revision_before = _revision(unit, *_unrouted_source_issues(first.diagnostics, boxes))
    revision_after = _revision(unit, *_unrouted_source_issues(second.diagnostics, boxes))
    assert revision_before.calculation_revision_id == revision_after.calculation_revision_id

    (gap,) = [
        issue.fact
        for issue in revision_after.source_issues
        if issue.reason == "activity_asset_claim_gap" and issue.fact is not None
    ]
    names = tuple((item.asset_id, item.facts.name) for item in after.descriptors)
    assert "Standing desk" in note_fact_text(gap, element_names=names, locale="en")
    assert "Old desk" not in note_fact_text(gap, element_names=names, locale="en")


def test_the_form_shows_the_current_name_from_the_read_it_was_given(operation: PinnedAuthorityOperation) -> None:
    from ..calculation_bucket_actions import _unrouted_source_issues

    boxes = snapshot_printed_boxes(operation, operation.snapshot("100", filing_year=2025, period="0A"))
    diagnostics = resolve_m100(_described("Standing desk")).diagnostics
    revision = _revision(_work_unit(operation), *_unrouted_source_issues(diagnostics, boxes))

    form = _checked_form(operation, revision)
    note = next(note for note in form.calculation_notes if note.reason == "activity_asset_claim_gap")
    named = form.model_copy(
        update={
            "calculation_notes": tuple(
                item.model_copy(update={"element_names": (("furniture", "Standing desk"),)}) if item is note else item
                for item in form.calculation_notes
            )
        }
    )

    assert any("Standing desk" in line.message for line in form_issue_lines(named, OutputLanguage.EN))
    assert any("An asset with no name" in line.message for line in form_issue_lines(form, OutputLanguage.EN))


def test_a_recorded_note_arrives_in_words_for_a_reader_that_only_draws_it(operation: PinnedAuthorityOperation) -> None:
    from ..calculation_bucket_actions import _unrouted_source_issues

    class _Register:
        def load(self) -> ActivityAssetHistory:
            return _described("Standing desk")

    boxes = snapshot_printed_boxes(operation, operation.snapshot("100", filing_year=2025, period="0A"))
    issues = _unrouted_source_issues(resolve_m100(_described("Standing desk")).diagnostics, boxes)

    named = read_recorded_notes(issues, cast(ActivityAssetHistoryRepository, _Register()))
    unnamed = read_recorded_notes(issues, None)

    gap = next(note for note in named if note.reason == "activity_asset_claim_gap")
    assert "Standing desk" in gap.message
    assert gap.message == note_fact_text(gap.fact, element_names=gap.element_names)
    assert all(note.message and note.detail and "{" not in note.message + note.detail for note in named)
    assert all("Standing desk" not in note.message for note in unnamed)
    assert {note.reason for note in unnamed} == {note.reason for note in named}


def test_a_register_that_is_not_there_leaves_the_plain_phrase() -> None:
    assert read_element_names(None) == {}


@pytest.mark.parametrize("year", _SUPPORT.years)
def test_every_box_a_note_names_is_the_number_the_form_prints(year: int, operation: PinnedAuthorityOperation) -> None:
    annual = operation.snapshot("100", filing_year=year, period="0A")
    instalment = operation.snapshot("130", filing_year=year, period="1T")
    annual_boxes = snapshot_printed_boxes(operation, annual)
    instalment_boxes = snapshot_printed_boxes(operation, instalment)

    named = {
        *activity_asset_amortization_casillas(annual.revision).values(),
        *activity_asset_disposal_route_casillas(annual.revision).values(),
    }
    assert named
    assert {box: annual_boxes.number(box) for box in named} == {box: box for box in named}
    income_box = renta_income_target_casilla(instalment.revision, modelo="130")
    assert instalment_boxes.number(income_box) == income_box
