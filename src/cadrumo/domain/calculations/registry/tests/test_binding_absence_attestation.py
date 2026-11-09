"""A statement of absence is declared only on a decimal carry read from an earlier filing.

Such a carry is unknown, never zero, while no earlier return supplies it, so a
filer may state it holds nothing. On any other binding the statement would
assert a figure the declaration takes from somewhere else, and the registry
refuses it. Real behaviour: the published Modelo 100 revision's own bindings,
validated by the production schema, for every Modelo 100 year the support
envelope admits.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingSourceKind
from .....core.authority_grade import RegistryAuthorityGrade
from ..binding_absence_attestation import AbsenceAttestationFamily
from ..binding_value_contract import BindingValueChannel
from ..errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ..schema import BindingDefinition
from .published_authority import published_snapshot, published_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FAMILY = AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING
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
    # Only those carries declare it: every other binding of the revision takes no statement.
    assert {binding.id for binding in bindings.values() if binding.absence_attestation is not None} == set(_DECLARED)


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
