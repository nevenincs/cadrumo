"""What earlier years left pending on a let property comes from the filer's statement per origin year.

LIRPF art. 23.1.a.1.º and RIRPF art. 13.a carry the excess of interest and
repairs over a property's gross income to the following years of the carry
window, property by property, and anexo C.1 follows it by the ejercicio it
arose in. With no earlier return read, each origin year's opening amount is
unknown, never zero: the resolver keeps the rows, withholds the net yield and
says so with one finding per origin year whose door is the statement on that
year's opening column. A statement settles only the property and the origin
year it names, on a column whose registry family takes it.

Every finding states its facts in each output language, naming the property
it speaks of by the record's own number and the opening box it asks for.

Real behaviour: the published Modelo 100 revision of every year of the support
envelope, the real profile record and the real resolver; only the ledger and
withholding stores are in-memory stand-ins.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....domain.calculations.registry.renta_inmueble_bindings import RentaInmuebleOriginPart
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO, RowCarryAttestation
from ....domain.modelos.calculation_revision_sources import CalculationNoteFact
from ...modelo.calculation_notes import fact_locale_key, note_fact_text
from ..renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleDoor
from ..renta_inmueble_source import RentaInmuebleRowField
from .ledger_source_mesh_support import m100_revision
from .renta_inmueble_carry_support import (
    RENT,
    ROW,
    column,
    findings,
    nothing_pending,
    origin_column,
    resolve_carry,
    sentence,
    stated,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEARS = filing_year_envelope().years
_UNSTATED = RentaInmuebleCause.PENDING_EXPENSES_UNSTATED
_LET_YEARS_BEFORE = 3
"""The default property of the support was first let this many ejercicios before the one filed."""


@pytest.mark.parametrize("year", _YEARS)
def test_each_unstated_origin_year_keeps_the_rows_withholds_the_net_yield_and_names_its_opening_column(
    year: int,
) -> None:
    revision = m100_revision(year)
    resolution = resolve_carry(year)
    values = resolution.row_binding_values

    raised = findings(resolution, _UNSTATED)
    assert len(raised) == _LET_YEARS_BEFORE
    assert all(finding.reason == "source_domain_not_ready" and finding.source_ref == ROW for finding in raised)
    opened = {
        origin_column(revision, RentaInmuebleOriginPart.OPENING, back) for back in range(1, _LET_YEARS_BEFORE + 1)
    }
    named = set()
    for finding in raised:
        assert finding.fact is not None
        values_of = dict(finding.fact.values)
        named.add(values_of["binding"])
        assert finding.remedy is not None
        assert f"{RentaInmuebleDoor.ATTEST_NO_AMOUNT.value} <work-unit> {values_of['binding']} --row {ROW}" in (
            finding.remedy
        )
        assert values_of["record"] == "3"
    assert named == opened
    assert values[(column(revision, RentaInmuebleRowField.INGRESOS_INTEGROS), 1)] == RENT * 12
    for field in (
        RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES,
        RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS,
        RentaInmuebleRowField.RENDIMIENTO_NETO,
        RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO,
    ):
        assert (column(revision, field), 1) not in values, (year, field)


@pytest.mark.parametrize("year", _YEARS)
def test_stated_amounts_apply_oldest_first_before_the_year_s_own_within_the_income(year: int) -> None:
    revision = m100_revision(year)
    resolution = resolve_carry(year, stated(year, 1, "6000"), stated(year, 2, "4000"), stated(year, 3, None))
    values = resolution.row_binding_values

    assert findings(resolution, _UNSTATED) == []
    # The limit is the 10.800 of rent: 4.000 of the older origin, then 6.000 of the newer, then 800 of
    # the year's own 1.000 repairs; 200 of the year's own carry on, and nothing of either origin does.
    assert values[(column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES), 1)] == Decimal(10000)
    assert values[(column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_APLICADOS), 1)] == Decimal(10000)
    assert values[(column(revision, RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS), 1)] == Decimal(800)
    assert values[(column(revision, RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES), 1)] == Decimal(200)
    assert values[(column(revision, RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES_FUTUROS), 1)] == Decimal(200)
    assert values[(origin_column(revision, RentaInmuebleOriginPart.APPLIED, 2), 1)] == Decimal(4000)
    assert values[(origin_column(revision, RentaInmuebleOriginPart.APPLIED, 1), 1)] == Decimal(6000)
    assert (origin_column(revision, RentaInmuebleOriginPart.CARRIED, 1), 1) not in values


@pytest.mark.parametrize("year", _YEARS)
def test_a_statement_that_nothing_is_pending_settles_the_property_and_fills_no_carry_box(year: int) -> None:
    revision = m100_revision(year)
    resolution = resolve_carry(year, *nothing_pending(year))
    values = resolution.row_binding_values

    assert findings(resolution, _UNSTATED) == []
    assert (column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES), 1) not in values
    assert (column(revision, RentaInmuebleRowField.ANEXO_C1_TITULAR), 1) not in values
    assert (column(revision, RentaInmuebleRowField.RENDIMIENTO_NETO), 1) in values


@pytest.mark.parametrize("year", _YEARS)
def test_a_statement_for_another_property_another_origin_or_another_column_settles_nothing(year: int) -> None:
    revision = m100_revision(year)
    others = tuple(stated(year, back, None) for back in range(2, _LET_YEARS_BEFORE + 1))
    applied = origin_column(revision, RentaInmuebleOriginPart.APPLIED, 1)

    elsewhere = resolve_carry(year, *others, stated(year, 1, None, row="inmueble:4"))
    wrong_column = resolve_carry(
        year,
        *others,
        RowCarryAttestation(binding_id=applied, source_row_identity=ROW, amount=ATTESTED_ZERO, absent=True),
    )

    for resolution in (elsewhere, wrong_column):
        (finding,) = findings(resolution, _UNSTATED)
        assert finding.fact is not None
        assert dict(finding.fact.values)["binding"] == origin_column(revision, RentaInmuebleOriginPart.OPENING, 1)


def test_every_finding_reads_in_every_language_naming_its_record() -> None:
    for cause in RentaInmuebleCause:
        worded = sentence(cause)
        key = fact_locale_key(worded)
        authored = {language: lookup_translation(key, locale=language.value) for language in OutputLanguage}
        assert all(words is not None for words in authored.values()), (key, authored)
        assert len(set(authored.values())) == len(authored), (key, authored)
        for placeholder in ("{record}", "{box}", "{binding}"):
            named = placeholder in (authored[OutputLanguage.EN] or "")
            assert all((placeholder in (words or "")) == named for words in authored.values()), (key, placeholder)
        if "{record}" in (authored[OutputLanguage.EN] or ""):
            fact = CalculationNoteFact.of(
                worded, rows=("inmueble:7",), record="7", box="1221", binding="renta-inmueble-column"
            )
            for language in OutputLanguage:
                text = note_fact_text(fact, locale=language.value)
                assert "7" in text and "{" not in text, (key, language, text)
