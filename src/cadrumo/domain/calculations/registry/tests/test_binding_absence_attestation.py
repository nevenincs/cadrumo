"""A statement of absence is declared only on a carry the declaration cannot read from its own records.

A scalar family sits on a decimal carry read from an earlier filing; a row
family sits on a money column of a repeating group, stated row by row. Such a
carry is unknown, never zero, while no earlier return supplies it, so a filer
may state it holds nothing or what it holds. On any other binding the
statement would assert a figure the declaration takes from somewhere else, and
the registry refuses it. Real behaviour: the published Modelo 100 revision's
own bindings, validated by the production schema, for every Modelo 100 year
the support envelope admits.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingSourceKind
from .....core.authority_grade import RegistryAuthorityGrade
from ..binding_absence_attestation import AbsenceAttestationFamily
from ..binding_value_contract import BindingValueChannel
from ..errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ..renta_inmueble_bindings import RentaInmuebleProvider
from ..schema import BindingDefinition
from .published_authority import published_snapshot, published_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FAMILY = AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
_ROW_FAMILY = AbsenceAttestationFamily.RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES
_WORK_INCOME_FAMILY = AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED
_PENDING_EXPENSES_BOX = "0103"
_DECLARED = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)


def _renta_years() -> tuple[int, ...]:
    """The Modelo 100 years the envelope admits at calculation grade."""
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            _renta_bindings(year)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    return tuple(admitted)


def _renta_bindings(year: int) -> dict[str, BindingDefinition]:
    snapshot = published_snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
    return {binding.id: binding for binding in snapshot.revision.bindings}


@pytest.mark.parametrize("year", _renta_years())
def test_the_pending_negative_bases_declare_the_statement_and_validate(year: int) -> None:
    bindings = _renta_bindings(year)
    for binding_id in _DECLARED:
        binding = bindings[binding_id]
        assert binding.absence_attestation is _FAMILY
        assert BindingDefinition.model_validate(binding.model_dump()).absence_attestation is _FAMILY
    # Only those carries declare this family: other families (the work-income statement) are separate.
    assert {binding.id for binding in bindings.values() if binding.absence_attestation is _FAMILY} == set(_DECLARED)


def _pending_expense_columns(bindings: dict[str, BindingDefinition]) -> set[str]:
    return {
        binding.id
        for binding in bindings.values()
        if isinstance(binding.provider, RentaInmuebleProvider)
        and binding.provider.target_casilla_id == _PENDING_EXPENSES_BOX
    }


def test_some_admitted_year_offers_the_pending_rental_expenses_column() -> None:
    assert any(_pending_expense_columns(_renta_bindings(year)) for year in _renta_years())


@pytest.mark.parametrize("year", _renta_years())
def test_the_pending_rental_expenses_column_declares_the_row_statement(year: int) -> None:
    bindings = _renta_bindings(year)
    columns = _pending_expense_columns(bindings)
    assert {binding.id for binding in bindings.values() if binding.absence_attestation is _ROW_FAMILY} == columns
    for binding_id in columns:
        binding = bindings[binding_id]
        assert binding.value.channel is BindingValueChannel.ROW_SET
        assert BindingDefinition.model_validate(binding.model_dump()).absence_attestation is _ROW_FAMILY
    assert {
        binding.absence_attestation for binding in bindings.values() if binding.absence_attestation is not None
    } <= {_FAMILY, _ROW_FAMILY, _WORK_INCOME_FAMILY}


@pytest.mark.parametrize("year", _renta_years())
def test_a_row_statement_on_a_scalar_carry_and_a_scalar_statement_on_a_column_are_refused(year: int) -> None:
    bindings = _renta_bindings(year)
    carry = bindings[_DECLARED[0]].model_dump()
    with pytest.raises((RegistryValidationError, ValidationError)) as refused:
        BindingDefinition.model_validate({**carry, "absence_attestation": _ROW_FAMILY.value})
    assert "absence_attestation" in str(refused.value)
    for binding_id in _pending_expense_columns(bindings):
        column = bindings[binding_id].model_dump()
        with pytest.raises((RegistryValidationError, ValidationError)) as refused:
            BindingDefinition.model_validate({**column, "absence_attestation": _FAMILY.value})
        assert "absence_attestation" in str(refused.value)


@pytest.mark.parametrize("year", _renta_years())
def test_a_statement_on_a_binding_not_read_from_an_earlier_filing_is_refused(year: int) -> None:
    elsewhere = next(
        binding
        for binding in _renta_bindings(year).values()
        if binding.source is not BindingSourceKind.PREVIOUS_FILING
        and binding.value.channel is BindingValueChannel.DECIMAL
    )
    with pytest.raises((RegistryValidationError, ValidationError)) as refused:
        BindingDefinition.model_validate({**elsewhere.model_dump(), "absence_attestation": _FAMILY.value})
    assert "absence_attestation" in str(refused.value)


@pytest.mark.parametrize("year", _renta_years())
def test_a_statement_on_an_earlier_filing_read_that_is_not_an_amount_is_refused(year: int) -> None:
    carry = _renta_bindings(year)[_DECLARED[0]].model_dump()
    counted = {**carry, "value": {"data_type": "integer", "channel": BindingValueChannel.INTEGER.value}}
    # The same earlier-filing read as a count is a valid binding, until it declares the statement.
    assert BindingDefinition.model_validate({**counted, "absence_attestation": None}).absence_attestation is None
    with pytest.raises((RegistryValidationError, ValidationError)) as refused:
        BindingDefinition.model_validate(counted)
    assert "absence_attestation" in str(refused.value)
