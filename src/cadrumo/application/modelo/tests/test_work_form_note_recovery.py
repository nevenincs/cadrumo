"""A form calculation note carries the way out its reason and fact open, served as a refusal verdict serves it.

A Modelo 349 note about one invoice with no operation type opens the invoice
update, binding the invoice and leaving the operation type to the filer. The
note carries that door with its words in the form's language and the registered
operation it submits; a note whose reason opens no door carries none, and its
serialized form leaves the field out.
"""

from __future__ import annotations

import json

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...operator_actions.served_actions import ACTION_WORDS_LOCALE_KEYS
from ..calculation_notes import CALCULATION_SCREEN_OUTDATED_REASON
from ..work_form_declaration_facts import ModeloFormCalculationNote
from ..work_form_findings import ModeloFormAttention
from ..work_form_notes import note_recovery

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNCLASSIFIED = "m349_operation_unclassified"
_DOOR = "operator.ledger.invoice.update.operation_type"
_INVOICE_ID = "inv-0001"


def _unclassified_fact() -> CalculationNoteFact:
    return CalculationNoteFact.of(
        CalculationNoteSentence.M349_OPERATION_UNCLASSIFIED,
        rows=(_INVOICE_ID,),
        invoice="DE-1",
        party="EU Counterparty GmbH (DE123456789)",
    )


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_a_note_with_a_door_serves_its_words_and_operations_in_the_form_language(language: OutputLanguage) -> None:
    recovery = note_recovery(_UNCLASSIFIED, _unclassified_fact(), language)
    note = ModeloFormCalculationNote(
        reason=_UNCLASSIFIED, attention=ModeloFormAttention.MISSING, fact=_unclassified_fact(), recovery=recovery
    )

    document = json.loads(note.model_dump_json())["recovery"]

    assert document["action_id"] == _DOOR
    assert document["action_words"] == lookup_translation(ACTION_WORDS_LOCALE_KEYS[_DOOR], locale=language.value)
    assert document["action_words_language"] == language.value
    assert document["target_operation_ids"] == ["ledger.invoice.update"]
    assert document["missing_argument_names"] == ["operation_type"]
    bound = {item["argument_name"]: item for item in document["argument_bindings"]}
    assert bound["invoice_id"]["value"] == _INVOICE_ID
    assert ModeloFormCalculationNote.model_validate_json(note.model_dump_json()) == note


def test_a_note_without_a_door_leaves_the_recovery_out() -> None:
    assert note_recovery(CALCULATION_SCREEN_OUTDATED_REASON, None, OutputLanguage.EN) is None
    note = ModeloFormCalculationNote(reason=CALCULATION_SCREEN_OUTDATED_REASON, attention=ModeloFormAttention.INFO)

    assert "recovery" not in json.loads(note.model_dump_json())


def test_a_record_note_naming_more_than_one_row_opens_no_door() -> None:
    fact = CalculationNoteFact.of(
        CalculationNoteSentence.M349_OPERATION_UNCLASSIFIED,
        rows=(_INVOICE_ID, "inv-0002"),
        invoice="DE-1",
        party="EU Counterparty GmbH (DE123456789)",
    )

    assert note_recovery(_UNCLASSIFIED, fact, OutputLanguage.ES) is None
