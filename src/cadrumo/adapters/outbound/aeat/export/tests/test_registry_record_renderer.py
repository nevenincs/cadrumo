"""The registry-to-fichero-BOE renderer places and encodes fields as declared.

Expected bytes here are derived from two independent statements, never from the
renderer's own output: the registry declaration under test (which fixes each
field's offset, length, padding and justification) and the AEAT fixed-width
convention documented on the encoder - money travels as zero-padded cents under
ROUND_HALF_UP, text is padded to its declared width. A test that asserted what
the renderer happened to emit would pass against a renderer that placed every
field at the wrong offset.

Every refusal test is paired with the observation that the same record renders
when only the offending field is corrected, so a refusal cannot pass because the
fixture was unbuildable for some unrelated reason.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import pytest

from ......domain.calculations.registry import (
    CasillaFieldKind,
    ExportFieldDefinition,
    ExportRecordDefinition,
)
from ......domain.modelos import ModeloExportError
from .._registry_record_renderer import RegistryFixedWidthRecordRenderer

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_LITERAL = "145"
_NIF = "12345678Z"
_NIF_OFFSET, _NIF_LENGTH = 4, 9
_COUNT_OFFSET, _COUNT_LENGTH = 13, 4
_MONEY_OFFSET, _MONEY_LENGTH = 17, 10
_FILLER_OFFSET, _FILLER_LENGTH = 27, 5

#: max(offset + length - 1) across the declaration below.
_TOTAL_LENGTH = _FILLER_OFFSET + _FILLER_LENGTH - 1


def _field(
    field_id: str,
    *,
    offset: int | None,
    length: int | None,
    kind: CasillaFieldKind,
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"] = "text",
    casilla_id: str | None = None,
    literal: str | None = None,
    header_key: str | None = None,
    padding: Literal["left_zero", "left_space", "right_space", "none"] = "right_space",
    justification: Literal["left", "right", "none"] = "left",
    signed: bool = False,
) -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=field_id,
        offset=offset,
        length=length,
        kind=kind,
        casilla_id=casilla_id,
        literal=literal,
        header_key=header_key,
        data_type=data_type,
        required=False,
        padding=padding,
        justification=justification,
        signed=signed,
        # The schema requires every export field to carry grounding; these are
        # the Modelo 145 communication's own basis, so the fixtures are shaped
        # like real declarations rather than passing an empty tuple the model
        # would reject anyway.
        legal_refs=("rd-439-2007:art-88",),
        source_refs=("aeat-dr-145-v20",),
    )


def _record(*fields: ExportFieldDefinition) -> ExportRecordDefinition:
    return ExportRecordDefinition(
        id="m145-record",
        record_type="1",
        order=1,
        encoding="latin-1",
        line_ending="crlf",
        fields=fields,
    )


def _literal_field() -> ExportFieldDefinition:
    return _field("literal", offset=1, length=3, kind=CasillaFieldKind.LITERAL, literal=_LITERAL)


def _nif_field() -> ExportFieldDefinition:
    return _field(
        "nif",
        offset=_NIF_OFFSET,
        length=_NIF_LENGTH,
        kind=CasillaFieldKind.CASILLA,
        casilla_id="01",
        data_type="text",
    )


def _count_field() -> ExportFieldDefinition:
    return _field(
        "count",
        offset=_COUNT_OFFSET,
        length=_COUNT_LENGTH,
        kind=CasillaFieldKind.CASILLA,
        casilla_id="02",
        data_type="integer",
        padding="left_zero",
        justification="right",
    )


def _money_field() -> ExportFieldDefinition:
    return _field(
        "money",
        offset=_MONEY_OFFSET,
        length=_MONEY_LENGTH,
        kind=CasillaFieldKind.CASILLA,
        casilla_id="03",
        data_type="money",
        padding="left_zero",
        justification="right",
    )


def _filler_field() -> ExportFieldDefinition:
    return _field("filler", offset=_FILLER_OFFSET, length=_FILLER_LENGTH, kind=CasillaFieldKind.FILLER)


def _full_record() -> ExportRecordDefinition:
    return _record(_literal_field(), _nif_field(), _count_field(), _money_field(), _filler_field())


_VALUES = {"01": _NIF, "02": "7", "03": "123.45"}


def _slice(body: bytes, offset: int, length: int) -> bytes:
    """Return the bytes the declaration assigns to a one-based ``offset``."""
    return body[offset - 1 : offset - 1 + length]


def _error_context(error: ModeloExportError) -> Mapping[str, object]:
    """Return an error's context while leaving missing expected keys loud."""
    return error.context or {}


def test_body_length_equals_the_declared_extent() -> None:
    """The body spans exactly the declaration's furthest field, with no terminator."""
    body = RegistryFixedWidthRecordRenderer().render_record_body(_full_record(), field_values=_VALUES)

    assert len(body) == _TOTAL_LENGTH
    assert not body.endswith(b"\r\n"), "terminator ownership belongs to the caller, not the renderer"


def test_each_field_lands_at_its_declared_offset() -> None:
    """Placement and padding follow the declaration, not declaration order."""
    body = RegistryFixedWidthRecordRenderer().render_record_body(_full_record(), field_values=_VALUES)

    assert _slice(body, 1, 3) == _LITERAL.encode("iso-8859-1")
    # text: declared right_space/left, so the value sits left and pads to width.
    assert _slice(body, _NIF_OFFSET, _NIF_LENGTH) == _NIF.encode("iso-8859-1")
    # integer: declared left_zero/right.
    assert _slice(body, _COUNT_OFFSET, _COUNT_LENGTH) == b"0007"
    # money: AEAT convention is zero-padded cents, so 123.45 EUR is 12345 cents.
    money = _slice(body, _MONEY_OFFSET, _MONEY_LENGTH)
    assert money == b"0" * (_MONEY_LENGTH - 5) + b"12345"
    assert int(money) == 12345
    assert _slice(body, _FILLER_OFFSET, _FILLER_LENGTH) == b" " * _FILLER_LENGTH


def test_a_shorter_text_value_pads_to_the_declared_width() -> None:
    """A value narrower than its field must not shift every later field left."""
    body = RegistryFixedWidthRecordRenderer().render_record_body(
        _full_record(),
        field_values={**_VALUES, "01": "AB"},
    )

    assert _slice(body, _NIF_OFFSET, _NIF_LENGTH) == b"AB" + b" " * (_NIF_LENGTH - 2)
    assert len(body) == _TOTAL_LENGTH
    assert _slice(body, _MONEY_OFFSET, _MONEY_LENGTH) == b"0" * (_MONEY_LENGTH - 5) + b"12345"


def test_an_omitted_money_value_renders_as_zero_not_blank() -> None:
    """A casilla the operator left blank is a declared zero, never a hole."""
    body = RegistryFixedWidthRecordRenderer().render_record_body(
        _full_record(),
        field_values={"01": _NIF, "02": "7"},
    )

    assert _slice(body, _MONEY_OFFSET, _MONEY_LENGTH) == b"0" * _MONEY_LENGTH
    assert len(body) == _TOTAL_LENGTH


def test_declaration_order_does_not_change_the_wire_layout() -> None:
    """Fields are placed by declared offset, so shuffling the tuple is inert."""
    forward = RegistryFixedWidthRecordRenderer().render_record_body(_full_record(), field_values=_VALUES)
    shuffled = _record(_filler_field(), _money_field(), _literal_field(), _count_field(), _nif_field())

    assert RegistryFixedWidthRecordRenderer().render_record_body(shuffled, field_values=_VALUES) == forward


def test_a_field_without_coordinates_is_refused_and_named() -> None:
    """A half-declared field must refuse rather than silently drop off the wire."""
    broken = _record(
        _literal_field(),
        _field("nif", offset=None, length=_NIF_LENGTH, kind=CasillaFieldKind.CASILLA, casilla_id="01"),
        _count_field(),
        _money_field(),
        _filler_field(),
    )

    with pytest.raises(ModeloExportError) as caught:
        RegistryFixedWidthRecordRenderer().render_record_body(broken, field_values=_VALUES)

    context = _error_context(caught.value)
    assert context["reason"] == "missing_coordinates"
    assert context["export_field_id"] == "nif"
    # Positive control: the same record renders once the coordinate is restored.
    assert RegistryFixedWidthRecordRenderer().render_record_body(_full_record(), field_values=_VALUES)


def test_an_unparseable_money_value_is_refused_and_named() -> None:
    """A money casilla carrying prose must refuse, not encode garbage."""
    with pytest.raises(ModeloExportError) as caught:
        RegistryFixedWidthRecordRenderer().render_record_body(
            _full_record(),
            field_values={**_VALUES, "03": "not-a-number"},
        )

    context = _error_context(caught.value)
    assert context["reason"] == "money_value"
    assert context["export_field_id"] == "money"
    assert RegistryFixedWidthRecordRenderer().render_record_body(_full_record(), field_values=_VALUES)


def test_an_unparseable_integer_value_is_refused_and_named() -> None:
    """An integer casilla carrying a decimal must refuse rather than truncate."""
    with pytest.raises(ModeloExportError) as caught:
        RegistryFixedWidthRecordRenderer().render_record_body(
            _full_record(),
            field_values={**_VALUES, "02": "7.5"},
        )

    context = _error_context(caught.value)
    assert context["reason"] == "integer_value"
    assert context["export_field_id"] == "count"


def test_an_unsupported_data_type_is_refused_and_named() -> None:
    """A data_type this encoder cannot place must refuse, naming the type."""
    broken = _record(
        _literal_field(),
        _nif_field(),
        _count_field(),
        _field(
            "money",
            offset=_MONEY_OFFSET,
            length=_MONEY_LENGTH,
            kind=CasillaFieldKind.CASILLA,
            casilla_id="03",
            data_type="date",
        ),
        _filler_field(),
    )

    with pytest.raises(ModeloExportError) as caught:
        RegistryFixedWidthRecordRenderer().render_record_body(broken, field_values=_VALUES)

    context = _error_context(caught.value)
    assert context["reason"] == "data_type"
    assert context["data_type"] == "date"


def test_a_field_kind_this_renderer_cannot_place_is_refused() -> None:
    """A declared kind outside LITERAL/FILLER/CASILLA must refuse, not render blank.

    ``CasillaFieldKind`` carries eight members; this renderer places three, and
    a record reaching it with a HEADER, BINDING, COMPUTED, DRAFT or CHECKSUM
    field is asking for a value it has no channel for. Refusing keeps that a
    loud gap rather than a silently short record.

    The sibling case - a CASILLA field naming no casilla - is unreachable here:
    ``ExportFieldDefinition`` already rejects it at construction, so it cannot
    be expressed through a validated declaration. The renderer still guards it,
    but this test does not claim to cover it.
    """
    broken = _record(
        _literal_field(),
        _field(
            "header",
            offset=_NIF_OFFSET,
            length=_NIF_LENGTH,
            kind=CasillaFieldKind.HEADER,
            header_key="ejercicio",
        ),
        _count_field(),
        _money_field(),
        _filler_field(),
    )

    with pytest.raises(ModeloExportError) as caught:
        RegistryFixedWidthRecordRenderer().render_record_body(broken, field_values=_VALUES)

    context = _error_context(caught.value)
    assert context["reason"] == "field_kind"
    assert context["export_field_id"] == "header"
    assert RegistryFixedWidthRecordRenderer().render_record_body(_full_record(), field_values=_VALUES)


def test_the_renderer_refuses_a_record_with_no_renderable_fields() -> None:
    """An empty record would otherwise compute a length from an empty max()."""
    with pytest.raises(ModeloExportError) as caught:
        RegistryFixedWidthRecordRenderer().render_record_body(_record(), field_values={})

    assert _error_context(caught.value)["reason"] == "empty_record"
