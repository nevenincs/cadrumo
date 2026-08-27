"""A padded export field owes its slot the full declared width.

``_pad`` dispatches on the field's ``padding`` axis, and the
``padding = "none"`` arm returned the value unpadded. That is invisible in
production today for two independent reasons, neither of which is a property of
``_pad``:

* ``_render_record`` builds positioned records into a space-prefilled buffer and
  writes ``buffer[start:start + len(rendered)]``, so a short field leaves the
  remainder of its slot as the buffer's own spaces.
* Every one of the shipped export fields declares an ``offset``, so the
  unpositioned arm of ``_render_record`` -- a bare concatenation of rendered
  fields, with no buffer to backfill anything -- is not currently reached.

So the record came out at its declared width by accident of assembly path and
registry content rather than because the renderer padded. A record whose fields
omitted their offsets, or a future caller that renders a field outside the
buffer, would silently emit a short record: 425 shipped fields declare
``padding = "none"``.

These expectations are structural, not numeric, so there is no AEAT figure to
ground them against and none is claimed. The property under test is that
``_pad`` is total in its declared width, and that the two assembly paths in
``_render_record`` agree -- a disagreement between them is the defect
regardless of which one AEAT would have accepted.

Real-behaviour: the real ``ExportFieldDefinition`` / ``ExportRecordDefinition``
schema objects and the real renderer. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.fixed_width_codec import ExportJustification, ExportPadding, pad_fixed_width_text
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from .._export import _RecordRenderRow, _render_record
from ._export_support import _approved_registry_draft, _typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PADDING_MODES = tuple(ExportPadding)
_JUSTIFICATION_BY_PADDING = {
    ExportPadding.LEFT_ZERO: ExportJustification.RIGHT,
    ExportPadding.LEFT_SPACE: ExportJustification.RIGHT,
    ExportPadding.RIGHT_SPACE: ExportJustification.LEFT,
    ExportPadding.NONE: ExportJustification.NONE,
}


def _field(
    field_id: str,
    *,
    offset: int | None,
    length: int,
    padding: ExportPadding,
    literal: str,
) -> ExportFieldDefinition:
    """Build one literal-valued export field at the given padding mode."""
    return ExportFieldDefinition(
        id=field_id,
        offset=offset,
        length=length,
        kind="literal",
        literal=literal,
        data_type="text",
        required=False,
        padding=padding,
        justification=_JUSTIFICATION_BY_PADDING[padding],
        signed=False,
        legal_refs=("ley-27-2014:art-40",),
        source_refs=("aeat-dr-232-2018",),
    )


def _record(fields: tuple[ExportFieldDefinition, ...]) -> ExportRecordDefinition:
    return ExportRecordDefinition(
        id="pad-totality-probe",
        record_type="1",
        order=0,
        encoding="iso-8859-1",
        line_ending="none",
        fields=fields,
    )


def _render(fields: tuple[ExportFieldDefinition, ...]) -> str:
    return _render_record(
        _record(fields),
        draft=_approved_registry_draft(),
        producer_values={},
        producer_snapshot=_typed_producer_snapshot(),
        casilla_values={},
        binding_values={},
        row=_RecordRenderRow(row_index=None, active_binding_ids=frozenset()),
        render_context=None,
        projection_values={},
    )


@pytest.mark.parametrize("padding", _PADDING_MODES)
def test_pad_fills_the_declared_width_in_every_padding_mode(padding: ExportPadding) -> None:
    """Every padding mode returns exactly ``field.length`` characters."""
    rendered = pad_fixed_width_text(
        "AB",
        length=10,
        padding=padding,
        justification=_JUSTIFICATION_BY_PADDING[padding],
    )

    assert len(rendered) == 10, f"padding={padding!r} returned {rendered!r}"
    assert rendered.strip("0 ") == "AB"


def test_unpositioned_record_matches_the_positioned_record_byte_for_byte() -> None:
    """The two assembly paths must not disagree about a record's bytes.

    The positioned path's buffer is what masked the short return, so the
    unpositioned path is where a regression surfaces first.
    """
    positioned = (
        _field("a", offset=1, length=10, padding=ExportPadding.NONE, literal="AB"),
        _field("b", offset=11, length=4, padding=ExportPadding.LEFT_ZERO, literal="7"),
    )
    unpositioned = (
        _field("a", offset=None, length=10, padding=ExportPadding.NONE, literal="AB"),
        _field("b", offset=None, length=4, padding=ExportPadding.LEFT_ZERO, literal="7"),
    )

    assert _render(unpositioned) == _render(positioned)
    assert len(_render(unpositioned)) == 14


def test_a_padding_none_field_occupies_its_whole_slot() -> None:
    """A short value under ``padding = "none"`` still consumes its declared width."""
    fields = (
        _field("a", offset=None, length=10, padding=ExportPadding.NONE, literal="AB"),
        _field("b", offset=None, length=4, padding=ExportPadding.LEFT_ZERO, literal="7"),
    )

    rendered = _render(fields)

    assert rendered == "AB        0007"
