"""The counterparty comparator holds each stated counterparty to its type-2 record of a written fichero."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.fixed_width_codec import render_absent_slot, render_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import ExpectedValue, Identity, IdentityCatalogue, IdentityKind, YearToken

from ..counterparties import DESIGNS, counterparty_mismatches, is_compared, read_records
from ..rows import planned_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

type Row = Mapping[str, object]

_B347: Row = {
    "modelo-347-contraparte-row-nif": "B00000026",
    "modelo-347-contraparte-row-clave": "A",
    "modelo-347-contraparte-row-importe": Decimal("10684.30"),
}
_C347: Row = {
    "modelo-347-contraparte-row-nif": "H00000018",
    "modelo-347-contraparte-row-clave": "B",
    "modelo-347-contraparte-row-importe": Decimal("6765.00"),
}
_DE349: Row = {
    "iva-349-operador-row-codigo-pais": "DE",
    "iva-349-operador-row-nif": "000000001",
    "iva-349-operador-row-clave": "S",
    "iva-349-operador-row-base": Decimal("7500.05"),
}


@cache
def _layout(modelo: str, period: str) -> tuple[ExportLayoutDefinition, str]:
    with bundled_indexed_authority().operation() as operation:
        year = year_envelope(operation).horizon - 1
        revision = operation.revision_for_context(modelo, filing_year=year, period=period)
        layout = operation.revision_with_export_layouts(modelo, revision.id).export_layouts[0]
    return layout, ("\r\n" if modelo == "347" else "")


def _span(field: ExportFieldDefinition) -> tuple[int, int]:
    assert field.offset is not None
    assert field.length is not None
    return field.offset - 1, field.length


def _piece(field: ExportFieldDefinition, bound: Row) -> str:
    if field.literal is not None:
        return field.literal
    if field.binding is not None and field.binding in bound:
        return render_fixed_width_export_field(field, bound[field.binding])
    return render_absent_slot(field)


def _record(record: ExportRecordDefinition, bound: Row) -> str:
    """One record laid out field by field from the registry design: literals, the bound values, blank elsewhere."""
    text = [" "] * max(start + length for start, length in map(_span, record.fields))
    for field in record.fields:
        start, length = _span(field)
        text[start : start + length] = list(_piece(field, bound))
    return "".join(text)


def _fichero(modelo: str, period: str, rows: Sequence[Row]) -> tuple[ExportLayoutDefinition, bytes]:
    layout, ending = _layout(modelo, period)
    records = sorted(layout.records, key=lambda item: item.order)
    lines = [_record(records[0], {}), *(_record(records[1], row) for row in rows)]
    return layout, "".join(line + ending for line in lines).encode("iso-8859-1")


def _identities() -> IdentityCatalogue:
    def identity(role: str, kind: IdentityKind, value: str, country: str | None = None) -> Identity:
        return Identity(role=role, persona="p", kind=kind, value=value, razon_social=role, country=country)

    return IdentityCatalogue(
        identities=(
            identity("p.proveedor", "cif", "B00000026"),
            identity("p.comunidad", "cif", "H00000018"),
            identity("p.pequeno", "nif", "00000011B"),
            identity("p.cliente-de", "nif_iva", "DE000000001", "DE"),
        ),
        refusals=(),
    )


def _stated(modelo: str, role: str, **concepts: str) -> ExpectedValue:
    return ExpectedValue(
        modelo=modelo,
        period="0A",
        year=YearToken(anchor="horizon", offset=-1),
        counterparty=role,
        casillas=(),
        concepts=tuple(concepts.items()),
        parameters=(),
        derivation=None,
        legal_ref=("rd-1065-2007:art-33",),
        grounding="verified",
        reason=None,
    )


def test_the_reader_gives_each_type_2_record_by_registry_binding() -> None:
    layout, payload = _fichero("347", "0A", [_B347, _C347])
    rows = read_records(layout, payload, DESIGNS["347"])
    assert [row["modelo-347-contraparte-row-nif"] for row in rows] == ["B00000026", "H00000018"]
    assert rows[0]["modelo-347-contraparte-row-importe"] == Decimal("10684.30")


def test_records_that_match_every_stated_counterparty_have_no_mismatch() -> None:
    layout, payload = _fichero("347", "0A", [_B347, _C347])
    stated = [
        _stated("347", "p.proveedor", clave="A", importe_anual="10684.30"),
        _stated("347", "p.comunidad", clave="B", importe_anual="6765.00"),
        _stated("347", "p.pequeno", declared="false", importe_anual="1298.00"),
    ]
    assert counterparty_mismatches(stated, _identities(), layout, payload) == []


def test_a_wrong_amount_a_wrong_clave_a_missing_and_an_unexpected_record_are_each_named() -> None:
    layout, payload = _fichero("347", "0A", [_B347, {**_C347, "modelo-347-contraparte-row-clave": "A"}])
    stated = [
        _stated("347", "p.proveedor", clave="A", importe_anual="10684.31"),
        _stated("347", "p.comunidad", clave="B", importe_anual="6765.00"),
        _stated("347", "p.pequeno", clave="B", importe_anual="4290.00"),
        _stated("347", "p.cliente-de", declared="false", importe_anual="1.00"),
    ]
    assert counterparty_mismatches(stated, _identities(), layout, payload) == [
        "p.proveedor importe_anual exp 10684.31 got 10684.30",
        "p.comunidad clave exp B got A",
        "p.pequeno no type-2 record",
    ]


def test_a_declared_false_counterparty_with_a_record_is_a_mismatch() -> None:
    layout, payload = _fichero("347", "0A", [_B347])
    stated = [_stated("347", "p.proveedor", declared="false", importe_anual="10684.30")]
    assert counterparty_mismatches(stated, _identities(), layout, payload) == [
        "p.proveedor declared exp none got record"
    ]


def test_a_349_operator_is_matched_by_country_and_nif_iva_and_its_base_by_value() -> None:
    layout, payload = _fichero("349", "1T", [_DE349])
    assert (
        counterparty_mismatches(
            [_stated("349", "p.cliente-de", clave="S", base="7500.05")], _identities(), layout, payload
        )
        == []
    )
    assert counterparty_mismatches(
        [_stated("349", "p.cliente-de", clave="I", base="7500.00")], _identities(), layout, payload
    ) == ["p.cliente-de clave exp I got S", "p.cliente-de base exp 7500.00 got 7500.05"]


def test_values_of_other_modelos_are_not_compared() -> None:
    other = _stated("115", "p.proveedor", clave="G")
    assert not is_compared(other)
    layout, payload = _fichero("347", "0A", [_B347])
    assert counterparty_mismatches([other], _identities(), layout, payload) == []


def test_a_return_with_counterparty_values_is_a_row_with_an_oracle() -> None:
    from .test_rows import _envelope, _persona

    envelope = _envelope()
    rows = planned_rows(_persona("intracomunitario-desarrollador"), envelope.horizon, envelope)
    assert [row.has_values for row in rows if row.modelo == "349"] == [True] * sum(row.modelo == "349" for row in rows)
