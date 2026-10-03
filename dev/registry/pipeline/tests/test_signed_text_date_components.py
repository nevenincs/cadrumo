"""Lossless source-shaped sign/magnitude and text-date component wires."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_parse import ParsedExportFieldValue, parse_export_payload
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)

from ...compiler.loader import load_shared_catalogues
from ..joined_record_design import JoinedRecordDesignField, design_view
from ..record_design_intermediate import load_record_design_intermediate
from ..render_profile_validation import _field_anchor
from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _component(
    field_id: str, offset: int, length: int, policy: ExportValuePolicy, *, binding: bool = False
) -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=field_id,
        offset=offset,
        length=length,
        kind="binding" if binding else "casilla",
        binding="amount" if binding else None,
        casilla_id=None if binding else "date-text",
        data_type=(
            CasillaDataType.TEXT
            if policy is ExportValuePolicy.SIGNED_COMPONENT_SIGN
            else CasillaDataType.MONEY
            if policy is ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE
            else CasillaDataType.INTEGER
        ),
        required=True,
        padding="none" if policy is ExportValuePolicy.SIGNED_COMPONENT_SIGN else "left_zero",
        justification="none" if policy is ExportValuePolicy.SIGNED_COMPONENT_SIGN else "right",
        signed=False,
        value_policy=policy,
        legal_refs=("ley-35-2006:art-99",),
        source_refs=("aeat-dr-190-2025" if binding else "aeat-dr-165-2026",),
    )


def _record(fields: tuple[ExportFieldDefinition, ...]) -> ExportRecordDefinition:
    return ExportRecordDefinition(
        id="components",
        record_type="2",
        order=0,
        encoding="ascii",
        line_ending="none",
        fields=fields,
    )


def _parse_components(
    layout_id: str, record_id: str, wire: str, fields: tuple[ExportFieldDefinition, ...]
) -> tuple[ParsedExportFieldValue, ...]:
    """Round-trip a complete declared payload through the public parser."""
    record = _record(fields).model_copy(update={"id": record_id})
    layout = ExportLayoutDefinition(
        id=layout_id,
        records=(record,),
        legal_refs=fields[0].legal_refs,
        source_refs=fields[0].source_refs,
    )
    return parse_export_payload(layout, wire.encode("ascii")).fields


def test_sign_and_magnitude_round_trip_limits_and_refusals() -> None:
    fields = (
        _component("sign", 1, 1, ExportValuePolicy.SIGNED_COMPONENT_SIGN, binding=True),
        _component("magnitude", 2, 13, ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE, binding=True),
    )
    _record(fields)
    for value, prefix in ((Decimal("-99999999999.99"), "N"), (Decimal("0.01"), " ")):
        wire = "".join(render_fixed_width_export_field(field, value) for field in fields)
        assert len(wire) == 14 and wire[0] == prefix
        parsed = _parse_components("layout", "components", wire, fields)
        assert tuple(item.value for item in parsed) == (value, value)
        assert (
            "".join(
                render_fixed_width_export_field(field, item.value) for field, item in zip(fields, parsed, strict=True)
            )
            == wire
        )
    for value in (Decimal("100000000000.00"), Decimal("-0"), Decimal("1.001")):
        with pytest.raises(RegistryValidationError):
            "".join(render_fixed_width_export_field(field, value) for field in fields)
    for wire in ("X0000000000001", "N0000000000000", "N00000000000A1"):
        with pytest.raises(RegistryValidationError):
            _parse_components("layout", "components", wire, fields)
    with pytest.raises(ValueError, match="complete adjacent components"):
        _record((fields[0],))


def test_text_date_components_round_trip_and_calendar_refusal() -> None:
    fields = (
        _component("year", 1, 4, ExportValuePolicy.YYYYMMDD_TEXT_YEAR),
        _component("month", 5, 2, ExportValuePolicy.YYYYMMDD_TEXT_MONTH),
        _component("day", 7, 2, ExportValuePolicy.YYYYMMDD_TEXT_DAY),
    )
    _record(fields)
    for value in ("20240229", "20250101", "99991231"):
        wire = "".join(render_fixed_width_export_field(field, value) for field in fields)
        assert wire == value
        parsed = _parse_components("layout", "components", wire, fields)
        assert tuple(item.value for item in parsed) == (value, value, value)
    for value in ("20250229", "20251301", "20250132", "2025-01-01", "2025011", "202501011"):
        with pytest.raises(RegistryValidationError):
            render_fixed_width_export_field(fields[0], value)
    for wire in ("20250229", "20251301", "20250001", "202501AA"):
        with pytest.raises(RegistryValidationError):
            _parse_components("layout", "components", wire, fields)
    with pytest.raises(ValueError, match="complete adjacent components"):
        _record(fields[:2])
    optional = tuple(field.model_copy(update={"required": False}) for field in fields)
    assert "".join(render_fixed_width_export_field(field, None) for field in optional) == "00000000"
    assert all(item.value is None for item in _parse_components("layout", "components", "00000000", optional))
    with pytest.raises(RegistryValidationError):
        _parse_components("layout", "components", "20250000", optional)


def _signed_triplet(*, integer_width: int, zero_sign: bool = False) -> tuple[ExportFieldDefinition, ...]:
    sign = ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN if zero_sign else ExportValuePolicy.SIGNED_COMPONENT_SIGN
    policies = (
        sign,
        ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
        ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
    )
    lengths = (1, integer_width, 2)
    offset = 1
    fields = []
    for index, (policy, length) in enumerate(zip(policies, lengths, strict=True)):
        fields.append(
            ExportFieldDefinition(
                id=f"part-{index}",
                offset=offset,
                length=length,
                kind="casilla",
                casilla_id="signed-text-amount",
                data_type=CasillaDataType.TEXT if index == 0 else CasillaDataType.INTEGER,
                required=True,
                padding="none" if index == 0 else "left_zero",
                justification="none" if index == 0 else "right",
                signed=False,
                value_policy=policy,
                legal_refs=("ley-35-2006:art-99",),
                source_refs=("aeat-dr-280-2022" if zero_sign else "aeat-dr-165-2026",),
            )
        )
        offset += length
    return tuple(fields)


def test_signed_source_triplets_round_trip_and_refuse_impossible_shapes() -> None:
    fields = _signed_triplet(integer_width=13)
    _record(fields)
    for value, prefix in ((Decimal("-9999999999999.99"), "N"), (Decimal("1.25"), " ")):
        wire = "".join(render_fixed_width_export_field(field, value) for field in fields)
        assert len(wire) == 16 and wire[0] == prefix
        parsed = _parse_components("layout", "components", wire, fields)
        assert tuple(item.value for item in parsed) == (value,) * 3
    with pytest.raises(RegistryValidationError):
        render_fixed_width_export_field(fields[1], Decimal("10000000000000.00"))
    with pytest.raises(RegistryValidationError):
        _parse_components("layout", "components", "N" + "0" * 15, fields)
    with pytest.raises(ValueError, match="complete adjacent components"):
        _record(fields[:2])

    negative_only = _signed_triplet(integer_width=8, zero_sign=True)
    _record(negative_only)
    assert (
        "".join(render_fixed_width_export_field(field, Decimal("-12345678.99")) for field in negative_only)
        == "N1234567899"
    )
    assert "".join(render_fixed_width_export_field(field, Decimal("0")) for field in negative_only) == "0" * 11
    assert (
        tuple(item.value for item in _parse_components("layout", "components", "0" * 11, negative_only))
        == (Decimal(0),) * 3
    )
    with pytest.raises(RegistryValidationError):
        render_fixed_width_export_field(negative_only[0], Decimal("1"))
    with pytest.raises(RegistryValidationError):
        _parse_components("layout", "components", "0" + "0" * 9 + "1", negative_only)


def test_reviewed_pdf_parts_have_distinct_derived_profile_anchors() -> None:
    root = Path("src/cadrumo/_data")
    sources = load_shared_catalogues(root / "registry/aeat").sources
    intermediate = load_record_design_intermediate(
        root, sources, source_ref="aeat-dr-190-2020", filing_year=2020, design_epoch="2020"
    )
    semantic_map = load_semantic_map(Path("dev/registry/mappings/modelo_190/2020"))
    parent = next(
        field
        for sheet in intermediate.sheets
        for field in sheet.fields
        if field.record_identity == "Tipo 2 - Registro De Perceptor" and field.offset == 81
    )
    sign, magnitude = (
        next(entry for entry in semantic_map.entries if entry.export_field_id == field_id)
        for field_id in ("modelo-190-perc-signo-percepcion-dineraria", "modelo-190-perc-percepcion-dineraria")
    )
    sign_view = design_view(JoinedRecordDesignField(parser_field=parent, semantic_entry=sign))
    magnitude_view = design_view(JoinedRecordDesignField(parser_field=parent, semantic_entry=magnitude))
    assert (sign_view.semantic_part_offset, magnitude_view.semantic_part_offset) == (81, 82)
    assert _field_anchor(sign_view) != _field_anchor(magnitude_view)
    assert parent.semantic_part_offset is None
    assert "semantic_part_offset" not in parent.model_dump(mode="json")
