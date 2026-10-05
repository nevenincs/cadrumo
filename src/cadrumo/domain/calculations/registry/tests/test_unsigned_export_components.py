"""Unsigned component inversion requires one complete declared logical target."""

from decimal import Decimal

import pytest

from ..errors import RegistryValidationError
from ..export_parse import parse_export_payload
from ..export_value_policy import ExportValuePolicy, ParsedExportPolicyWireValue
from ..schema_exports import ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition
from .test_export_value_policy import _field

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def _components(
    *, fraction_length: int = 2, fraction_offset: int = 6, fraction_casilla: str = "01"
) -> tuple[ExportFieldDefinition, ...]:
    return (
        _field(ExportValuePolicy.INTEGER_PART, field_id="integer", length=5),
        _field(
            ExportValuePolicy.FRACTIONAL_DIGITS,
            field_id="fraction",
            casilla_id=fraction_casilla,
            length=fraction_length,
            payload_overrides={"offset": fraction_offset},
        ),
    )


def _layout(fields: tuple[ExportFieldDefinition, ...]) -> ExportLayoutDefinition:
    return ExportLayoutDefinition(
        id="unsigned-pair-layout",
        legal_refs=("ley-27-2014:art-40",),
        source_refs=("aeat-dr-200-2025",),
        records=(
            ExportRecordDefinition(
                id="record", record_type="1", order=0, encoding="ascii", line_ending="none", fields=fields
            ),
        ),
    )


@pytest.mark.parametrize(
    ("payload", "scale", "expected"),
    [(b"0001275", 2, Decimal("12.75")), (b"00000123", 3, Decimal("0.123")), (b"0000000", 2, Decimal("0.00"))],
)
def test_complete_amount_preserves_each_source_slot(payload: bytes, scale: int, expected: Decimal) -> None:
    parsed = parse_export_payload(_layout(_components(fraction_length=scale)), payload)
    assert [field.value for field in parsed.fields] == [expected, expected]
    assert [field.raw for field in parsed.fields] == [payload[:5].decode("ascii"), payload[5:].decode("ascii")]
    assert [field.source_locator for field in parsed.fields] == [
        "unsigned-pair-layout:record:integer:1:5",
        f"unsigned-pair-layout:record:fraction:6:{scale}",
    ]


@pytest.mark.parametrize("variant", ["missing", "different_target", "gap", "reversed"])
def test_incomplete_or_unrelated_components_keep_their_wire_meaning(variant: str) -> None:
    fields = _components()
    payload = b"0001275"
    if variant == "missing":
        fields = fields[:1]
        payload = b"00012"
    elif variant == "different_target":
        fields = _components(fraction_casilla="02")
    elif variant == "gap":
        fields = _components(fraction_offset=7)
        payload = b"00012 75"
    else:
        fields = (fields[1].model_copy(update={"offset": 1}), fields[0].model_copy(update={"offset": 3}))
        payload = b"7500012"
    parsed = parse_export_payload(_layout(fields), payload)
    assert all(isinstance(field.value, ParsedExportPolicyWireValue) for field in parsed.fields)


@pytest.mark.parametrize("payload", [b"0001X75", b"00012-5", b"00012 5"])
def test_complete_components_refuse_non_numeric_wire_bytes(payload: bytes) -> None:
    with pytest.raises(RegistryValidationError):
        parse_export_payload(_layout(_components()), payload)
