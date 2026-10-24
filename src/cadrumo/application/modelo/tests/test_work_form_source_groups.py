"""The form says where every value comes from: each box in exactly one group, sources under their groups.

Forms are built by the real builder over the published registry. A Modelo
303 period with nothing calculated groups its record-fed boxes under the
records, each source not read yet; the same groups are carried on the form,
said in its language, in the form's own order.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..work_form_models import ModeloFormSourceGroupKind, ModeloFormSourceState, address_key
from ..work_form_source_groups import group_name, source_groups, worded_source_groups
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_box_sits_in_exactly_one_group_in_form_order(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "303", 2026, "1T")

    grouped = [address_key(address) for group in form.source_groups for address in group.addresses]

    assert sorted(grouped) == sorted(address_key(field.address) for field in form.fields())
    assert len(grouped) == len(set(grouped))
    kinds = [group.kind for group in form.source_groups]
    assert kinds == [kind for kind in ModeloFormSourceGroupKind if kind in kinds]


def test_record_fed_boxes_read_as_not_read_yet_before_any_calculation(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "303", 2026, "1T")

    records = next(group for group in form.source_groups if group.kind is ModeloFormSourceGroupKind.RECORDS)

    assert records.readings
    assert all(reading.state is ModeloFormSourceState.NOT_YET for reading in records.readings)
    assert records.summary == " · ".join(reading.words for reading in records.readings)
    listed = {address_key(address) for reading in records.readings for address in reading.addresses}
    assert listed <= {address_key(address) for address in records.addresses}


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_the_carried_groups_are_the_groups_said_in_the_forms_language(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    form = built_form(operation, "303", 2026, "1T", language=language)

    assert form.source_groups == worded_source_groups(form)
    names = [group.name for group in form.source_groups]
    assert names == [group_name(group.kind, language=language) for group in source_groups(form)]
