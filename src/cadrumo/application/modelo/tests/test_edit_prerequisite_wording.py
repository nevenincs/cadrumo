"""A refused Apply's prerequisite is said once for every frontend, from the box it names on the real form."""

from __future__ import annotations

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..edit_prerequisite_wording import form_prerequisite_words, prerequisite_words
from ..work_form_models import ModeloFormCasillaAddressV1
from ..work_form_source_groups import earlier_filing_text
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EN = OutputLanguage.EN


def test_a_carried_box_names_its_earlier_declaration_and_the_boxes_its_source_reads(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "130", 2026, "2T", entered=frozenset())
    carried = next(
        field
        for field in form.fields()
        if field.source is not None
        and field.source.earlier_filings
        and isinstance(field.address, ModeloFormCasillaAddressV1)
    )
    boxes = (validated_casilla_id("07"),)

    words = prerequisite_words(carried, operator_entries_known=True, source_boxes=boxes, language=_EN)

    assert carried.source is not None
    assert words.splitlines() == [
        tr("workspace.modelo.apply_prerequisite.earlier", locale="en"),
        earlier_filing_text(carried.source.earlier_filings, _EN),
        tr("workspace.modelo.apply_prerequisite.source_boxes", boxes="[07]", locale="en"),
    ]
    unknown = prerequisite_words(carried, operator_entries_known=False, source_boxes=(), language=_EN)
    assert tr("workspace.modelo.apply_prerequisite.legacy", locale="en") in unknown.splitlines()
    assert isinstance(carried.address, ModeloFormCasillaAddressV1)
    assert form_prerequisite_words(form, carried.address.casilla_id, boxes, _EN) == prerequisite_words(
        carried, operator_entries_known=form.operator_entries_known, source_boxes=boxes, language=_EN
    )


def test_a_box_with_no_earlier_declaration_says_what_its_source_is(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "210", 2025, "0A", entered=frozenset())
    plain = next(field for field in form.fields() if field.source is None or not field.source.earlier_filings)

    words = prerequisite_words(plain, operator_entries_known=True, source_boxes=(), language=OutputLanguage.ES)

    assert words == tr("workspace.modelo.apply_prerequisite.what", locale="es")
    assert form_prerequisite_words(form, validated_casilla_id("no_such_box"), (), _EN) is None
