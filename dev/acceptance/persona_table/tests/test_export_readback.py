"""The export readback holds each stated casilla the design carries to the value the written fichero gives."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.fixed_width_codec import render_absent_slot, render_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import ExpectedValue, YearToken

from ..export_readback import read_fields, readback_mismatches, readback_reason
from ..roles import CasillaIdentity, edition_identities, identities, resolve

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "130"
_PERIOD = "1T"


@cache
def _year() -> int:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation).horizon - 1


@cache
def _layout() -> ExportLayoutDefinition:
    with bundled_indexed_authority().operation() as operation:
        revision = operation.revision_for_context(_MODELO, filing_year=_year(), period=_PERIOD)
        return operation.revision_with_export_layouts(_MODELO, revision.id).export_layouts[0]


def _carried() -> list[str]:
    """The casillas the design carries, in layout order."""
    return [str(f.casilla_id) for r in _layout().records for f in r.fields if f.casilla_id is not None]


def _piece(field: ExportFieldDefinition, bound: Mapping[str, Decimal]) -> str:
    if field.literal is not None:
        return field.literal
    if field.casilla_id is not None and str(field.casilla_id) in bound:
        return render_fixed_width_export_field(field, bound[str(field.casilla_id)])
    return render_absent_slot(field)


def _fichero(bound: Mapping[str, Decimal]) -> bytes:
    record = _layout().records[0]
    text = [" "] * max((f.offset or 0) - 1 + (f.length or 0) for f in record.fields)
    for field in record.fields:
        assert field.offset is not None
        assert field.length is not None
        text[field.offset - 1 : field.offset - 1 + field.length] = list(_piece(field, bound))
    return _enveloped("".join(text).encode("iso-8859-1"))


def _enveloped(body: bytes) -> bytes:
    """The body inside the design's filing envelope: an opening tag over a blank prefix, and the derived closer."""
    envelope = _layout().filing_envelope
    assert envelope is not None
    tag = f"<DR{_MODELO}0{_year()}{_PERIOD}".encode("ascii")
    tag = tag[: envelope.opening_tag_extent].ljust(envelope.opening_tag_extent)
    prefix = tag.ljust(envelope.prefix_extent)
    return prefix + body + envelope.closer_for(tag)


def _stated(casillas: tuple[tuple[str, str], ...] = (), roles: tuple[tuple[str, str], ...] = ()) -> ExpectedValue:
    return ExpectedValue(
        modelo=_MODELO,
        period=_PERIOD,
        year=YearToken(anchor="horizon", offset=-1),
        counterparty=None,
        casillas=casillas,
        roles=roles,
        concepts=(),
        parameters=(),
        derivation=None,
        legal_ref=("rd-439-2007:art-110",),
        grounding="verified",
        reason=None,
    )


def _mismatches(value: ExpectedValue, payload: bytes, unchecked: tuple[str, ...] = ()) -> list[str]:
    casillas = edition_identities(_MODELO, _year(), _PERIOD)
    with bundled_indexed_authority().operation() as operation:
        parsed = read_fields(_layout(), payload, modelo=_MODELO, year=_year(), period=_PERIOD, operation=operation)
    return readback_mismatches([value], casillas, unchecked, parsed)


def test_a_carried_casilla_the_file_gives_equal_has_no_mismatch() -> None:
    casilla = _carried()[0]
    payload = _fichero({casilla: Decimal("812.40")})
    assert _mismatches(_stated(((casilla, "812.4"),)), payload) == []


def test_a_carried_casilla_the_file_gives_differently_is_named() -> None:
    casilla = _carried()[0]
    payload = _fichero({casilla: Decimal("812.41")})
    found = _mismatches(_stated(((casilla, "812.40"),)), payload)
    assert found == [f"c{casilla} exp 812.40 got 812.41"]
    assert readback_reason(found) == f"export readback: c{casilla} exp 812.40 got 812.41"


def test_a_stated_nonzero_amount_the_file_leaves_unfilled_is_a_mismatch_and_a_stated_zero_is_not() -> None:
    casilla = _carried()[0]
    payload = _fichero({})
    assert _mismatches(_stated(((casilla, "5.00"),)), payload) == [f"c{casilla} exp 5.00 got 0.00"]
    assert _mismatches(_stated(((casilla, "0"),)), payload) == []


def test_a_casilla_the_design_does_not_carry_is_not_reported() -> None:
    absent = "99999"
    assert absent not in _carried()
    assert _mismatches(_stated(((absent, "1.00"),)), _fichero({})) == []


def test_a_role_resolved_to_a_carried_casilla_is_compared_in_the_edition() -> None:
    casillas = edition_identities(_MODELO, _year(), _PERIOD)
    carried = set(_carried())
    keys = [
        (key, item)
        for item in casillas
        if item.casilla_id in carried
        for key in (item.continuidad_id, item.semantic_role)
        if key is not None and resolve(casillas, key) == item.casilla_id
    ]
    assert keys, "the edition names no carried casilla by a unique role"
    key, item = keys[0]
    assert isinstance(item, CasillaIdentity)
    payload = _fichero({item.casilla_id: Decimal("7.00")})
    assert _mismatches(_stated(roles=((key, "7.00"),)), payload) == []
    found = _mismatches(_stated(roles=((key, "8.00"),)), payload)
    assert found == [f"role {key} (casilla {item.casilla_id}) exp 8.00 got 7.00"]


def test_the_reason_lists_the_first_few_and_counts_the_rest() -> None:
    reason = readback_reason([f"c{n} exp 1 got none" for n in range(5)])
    assert reason == "export readback: c0 exp 1 got none; c1 exp 1 got none; c2 exp 1 got none; and 2 more"
    assert readback_reason([]) == ""


_XML_FIXTURE = Path(__file__).resolve().parents[4] / (
    "src/cadrumo/tests/fixtures/aeat-sede/submitted-files/modelo-100-2024-0A-carry-agreement-synthetic.xml"
)


def test_a_modelo_100_xml_dictionary_file_is_read_with_casilla_ids_and_a_wrong_amount_is_named() -> None:
    payload = _XML_FIXTURE.read_bytes()
    stamp = re.search(rb'ejercicio="(\d+)"', payload)
    assert stamp is not None
    year = int(stamp[1])
    with bundled_indexed_authority().operation() as operation:
        revision = operation.revision_for_context("100", filing_year=year, period="0A")
        layout = operation.revision_with_export_layouts("100", revision.id).export_layouts[0]
        parsed = read_fields(layout, payload, modelo="100", year=year, period="0A", operation=operation)
    casillas = identities(revision)
    carried = {str(f.casilla_id): f.value for f in parsed if f.casilla_id is not None}
    assert carried, "the XML parse gave no field a casilla id"
    casilla, value = next(iter(carried.items()))
    stated = _stated(((casilla, str(value)),))
    stated = dataclasses.replace(stated, modelo="100", period="0A")
    assert readback_mismatches([stated], casillas, (), parsed) == []
    wrong = dataclasses.replace(stated, casillas=((casilla, "99999999.99"),))
    assert readback_mismatches([wrong], casillas, (), parsed) == [f"c{casilla} exp 99999999.99 got {value}"]
