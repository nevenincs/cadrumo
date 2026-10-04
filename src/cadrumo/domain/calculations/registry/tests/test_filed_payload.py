"""Downloaded evidence has distinct framing and reserved-slot rules from export."""

from decimal import Decimal

import pytest

from ...export_field_kind import CasillaFieldKind
from ..authority import bundled_indexed_authority
from ..errors import RegistryValidationError
from ..export_parse import parse_export_payload, parse_filed_payload
from ..schema_exports import ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PREFIX = b"<T303020241T0000>" + b" " * (328 - 17)
_CLOSER = b"</T303020241T0000>"
_FIRST = b"A01234SIGZ"
_SECOND = b"B00056   Z"


@pytest.fixture
def layout() -> ExportLayoutDefinition:
    with bundled_indexed_authority().operation() as operation:
        source = operation.snapshot("303", filing_year=2024, period="1T").revision.export_layouts[0]
        assert source.filing_envelope is not None
        records = []
        for index, marker in enumerate(("A", "B")):
            common = dict(
                required=True,
                padding="none",
                justification="none",
                signed=False,
                source_refs=source.source_refs,
                legal_refs=source.legal_refs,
            )
            fields = (
                ExportFieldDefinition.model_validate(
                    dict(
                        **common,
                        id=f"{marker}.start",
                        kind=CasillaFieldKind.LITERAL,
                        literal=marker,
                        offset=1,
                        length=1,
                        data_type="text",
                    )
                ),
                ExportFieldDefinition.model_validate(
                    dict(
                        **{**common, "padding": "left_zero", "justification": "right"},
                        id=f"{marker}.amount",
                        kind=CasillaFieldKind.CASILLA,
                        casilla_id=f"0{index + 1}",
                        offset=2,
                        length=5,
                        data_type="decimal",
                        decimals=2,
                    )
                ),
                ExportFieldDefinition.model_validate(
                    dict(
                        **common,
                        id=f"{marker}.reserved",
                        kind=CasillaFieldKind.FILLER,
                        offset=7,
                        length=3,
                        data_type="text",
                    )
                ),
                ExportFieldDefinition.model_validate(
                    dict(
                        **common,
                        id=f"{marker}.end",
                        kind=CasillaFieldKind.LITERAL,
                        literal="Z",
                        offset=10,
                        length=1,
                        data_type="text",
                    )
                ),
            )
            records.append(
                ExportRecordDefinition(
                    id=f"record-{marker.lower()}",
                    record_type=marker,
                    order=index,
                    encoding="iso-8859-1",
                    line_ending="crlf",
                    fields=fields,
                )
            )
        return ExportLayoutDefinition(
            id="filed-framing-proof",
            records=tuple(records),
            source_refs=source.source_refs,
            legal_refs=source.legal_refs,
            filing_envelope=source.filing_envelope.model_copy(update={"body_record_ids": tuple(r.id for r in records)}),
        )


@pytest.mark.parametrize("separator", [b"", b"\r\n"])
def test_filed_payload_preserves_reserved_bytes_without_promoting_them(
    layout: ExportLayoutDefinition, separator: bytes
) -> None:
    body = _PREFIX + _FIRST + separator + _SECOND + separator + _CLOSER
    parsed = parse_filed_payload(layout, body)
    assert [row.value for row in parsed.casillas] == [Decimal("12.34"), Decimal("0.56")]
    reserved = next(row for row in parsed.fields if row.field_id == "A.reserved")
    assert (reserved.raw, reserved.value, reserved.casilla_id) == ("SIG", None, None)
    with pytest.raises(RegistryValidationError):
        parse_export_payload(layout, body)
    assert all(record.line_ending.value == "crlf" for record in layout.records)


def test_strict_export_still_requires_declared_terminators(layout: ExportLayoutDefinition) -> None:
    blank = _FIRST.replace(b"SIG", b"   ")
    parsed = parse_export_payload(layout, _PREFIX + blank + b"\r\n" + _SECOND + b"\r\n" + _CLOSER)
    assert parsed.casillas[0].value == Decimal("12.34")
    with pytest.raises(RegistryValidationError, match="missing declared line ending"):
        parse_export_payload(layout, _PREFIX + blank + _SECOND + _CLOSER)


@pytest.mark.parametrize(
    "body",
    [
        _FIRST[:-1] + _SECOND,
        _FIRST.replace(b"Z", b"X") + _SECOND,
        _SECOND + _FIRST,
        _FIRST + b"\r\n" + _SECOND,
        _FIRST + _SECOND + b"\r\n",
        _FIRST.replace(b"01234", b"01X34") + _SECOND,
    ],
)
def test_filed_payload_refuses_bad_width_literal_order_framing_and_numeric_data(
    layout: ExportLayoutDefinition, body: bytes
) -> None:
    with pytest.raises(RegistryValidationError):
        parse_filed_payload(layout, _PREFIX + body + _CLOSER)


def test_filed_payload_requires_matching_envelope_closer(layout: ExportLayoutDefinition) -> None:
    with pytest.raises(RegistryValidationError, match="relative closer"):
        parse_filed_payload(layout, _PREFIX + _FIRST + _SECOND + _CLOSER.replace(b"1T", b"2T"))


def test_compact_admission_requires_a_declared_envelope(layout: ExportLayoutDefinition) -> None:
    with pytest.raises(RegistryValidationError, match="missing declared line ending"):
        parse_filed_payload(layout.model_copy(update={"filing_envelope": None}), _FIRST + _SECOND)
