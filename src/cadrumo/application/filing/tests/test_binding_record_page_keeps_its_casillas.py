"""A fixed page mixing casillas and bindings is suppressed only when both are empty."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ..record_renderer import record_render_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(scope="module")
def mixed_page() -> ExportRecordDefinition:
    """A resolved mixed page; current generated M131 pages no longer use bindings."""
    return ExportRecordDefinition(
        id="mixed-page",
        record_type="1",
        order=0,
        binding_record="mixed-page",
        encoding="iso-8859-1",
        line_ending="none",
        fields=(
            ExportFieldDefinition(
                id="amount",
                kind="casilla",
                casilla_id="01",
                offset=1,
                length=17,
                data_type=CasillaDataType.MONEY,
                padding="left_zero",
                justification="right",
                required=False,
                signed=False,
                legal_refs=("orden-hac-773-2019:art-4",),
                source_refs=("aeat-dr-131-2026",),
            ),
            ExportFieldDefinition(
                id="binding",
                kind="binding",
                binding="mixed-binding",
                offset=18,
                length=1,
                data_type=CasillaDataType.TEXT,
                padding="right_space",
                justification="left",
                required=False,
                signed=False,
                legal_refs=("orden-hac-773-2019:art-4",),
                source_refs=("aeat-dr-131-2026",),
            ),
        ),
    )


def _a_casilla_id(record: ExportRecordDefinition) -> str:
    return next(field.casilla_id for field in record.fields if field.casilla_id is not None)


def _a_binding_id(record: ExportRecordDefinition) -> str:
    return next(field.binding for field in record.fields if field.binding is not None)


def test_casillas_alone_keep_the_page(mixed_page: ExportRecordDefinition) -> None:
    """Casilla data with no binding value still files the page."""
    rows = record_render_rows(
        mixed_page,
        {},
        {_a_casilla_id(mixed_page): Decimal("1234.56")},
    )

    assert len(rows) == 1


def test_bindings_alone_keep_the_page(mixed_page: ExportRecordDefinition) -> None:
    """The binding channel on its own is still sufficient, as before."""
    rows = record_render_rows(
        mixed_page,
        {(_a_binding_id(mixed_page), None): "G"},
        {},
    )

    assert len(rows) == 1


def test_a_page_carrying_neither_is_left_out(mixed_page: ExportRecordDefinition) -> None:
    """Suppression still happens; only its condition narrowed.

    Without this the fix would read as "always emit", which would put a page of
    bare identifier constants into every fichero.
    """
    rows = record_render_rows(mixed_page, {}, {})

    assert rows == ()


def test_an_empty_string_is_not_a_value(mixed_page: ExportRecordDefinition) -> None:
    """An empty casilla is absence, matching the binding channel's own test."""
    rows = record_render_rows(mixed_page, {}, {_a_casilla_id(mixed_page): ""})

    assert rows == ()
