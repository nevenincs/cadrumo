"""The capital-mobiliario concept vocabulary and withholding rate are read from the registry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from ..authority import PinnedAuthorityOperation
from ..capital_mobiliario_facts import (
    CapitalMobiliarioAmountRole,
    resolve_capital_mobiliario_concept_vocabulary,
    resolve_capital_mobiliario_withholding_rate,
)
from ..errors import RegistryValidationError
from ..facts.resolution import (
    GovernedFactQuery,
    MappingFactQuery,
    ResolvedGovernedFact,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
)
from ..schema_base import DateAxis
from ..snapshot_globals import SupportedFilingYearsCatalogue
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON = date(filing_year_envelope().horizon, 3, 10)


@dataclass
class _FixedFact:
    resolved: ResolvedGovernedFact
    support: SupportedFilingYearsCatalogue

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        return self.resolved

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.support


def _vocabulary(operation: PinnedAuthorityOperation) -> ResolvedMappingFact:
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="capital-mobiliario-concept-vocabulary",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=_ON,
        ),
    )
    assert isinstance(resolved, ResolvedMappingFact)
    return resolved


def _with_entry(resolved: ResolvedMappingFact, key: str, value: str) -> ResolvedMappingFact:
    entries = tuple(
        entry.model_copy(update={"value": value}) if entry.key == key else entry for entry in resolved.payload.entries
    )
    return resolved.model_copy(update={"payload": resolved.payload.model_copy(update={"entries": entries})})


def test_the_published_vocabulary_names_each_concept_record_and_casilla_role(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = resolve_capital_mobiliario_concept_vocabulary(effective_date=_ON, authority=operation)

    assert catalogue.tokens == ("intereses", "dividendos", "gasto_administracion_deposito")
    assert [
        (item.detail_record, item.amount_element, item.casilla_semantic_role, item.requires_position_kind)
        for item in catalogue.concepts
    ] == [
        ("RegistroB11", "IMP1DB11", "irpf_rendimiento_capital_mobiliario_ahorro_intereses_cuentas", None),
        ("RegistroB13", "IMP1DB13", "irpf_rendimiento_capital_mobiliario_ahorro_dividendos", None),
        (
            "RegistroB13",
            "IMP3DB13",
            "irpf_rendimiento_capital_mobiliario_ahorro_gastos_deducibles",
            "valores_negociables",
        ),
    ]


def test_the_published_vocabulary_says_which_amounts_are_income_and_which_are_expenses(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = resolve_capital_mobiliario_concept_vocabulary(effective_date=_ON, authority=operation)

    assert [item.amount_role for item in catalogue.concepts] == [
        CapitalMobiliarioAmountRole.GROSS_INCOME,
        CapitalMobiliarioAmountRole.GROSS_INCOME,
        CapitalMobiliarioAmountRole.DEDUCTIBLE_EXPENSE,
    ]


def test_an_unknown_amount_role_is_refused(operation: PinnedAuthorityOperation) -> None:
    changed = _with_entry(_vocabulary(operation), "concept.intereses.amount_role", "net_income")
    authority = _FixedFact(changed, operation.supported_filing_years())

    with pytest.raises(RegistryValidationError) as raised:
        resolve_capital_mobiliario_concept_vocabulary(effective_date=_ON, authority=authority)

    assert "concept.intereses.amount_role" in str(raised.value)


def test_the_vocabulary_resolves_for_every_supported_filing_year(operation: PinnedAuthorityOperation) -> None:
    for year in filing_year_envelope().years:
        catalogue = resolve_capital_mobiliario_concept_vocabulary(
            effective_date=date(year, 12, 31), authority=operation
        )

        assert catalogue.tokens == ("intereses", "dividendos", "gasto_administracion_deposito")


def test_a_changed_registry_entry_changes_the_resolved_concept(operation: PinnedAuthorityOperation) -> None:
    changed = _with_entry(_vocabulary(operation), "concept.intereses.detail_record", "RegistroB99")
    authority = _FixedFact(changed, operation.supported_filing_years())

    catalogue = resolve_capital_mobiliario_concept_vocabulary(effective_date=_ON, authority=authority)

    assert catalogue.require("intereses").detail_record == "RegistroB99"


def test_a_declared_token_without_its_record_is_refused(operation: PinnedAuthorityOperation) -> None:
    changed = _with_entry(_vocabulary(operation), "concept.dividendos.detail_record", " ")
    authority = _FixedFact(changed, operation.supported_filing_years())

    with pytest.raises(RegistryValidationError) as raised:
        resolve_capital_mobiliario_concept_vocabulary(effective_date=_ON, authority=authority)

    assert "concept.dividendos.detail_record" in str(raised.value)


@pytest.mark.parametrize("token", ["cupon", "", "  ", 3])
def test_an_unknown_token_is_refused(operation: PinnedAuthorityOperation, token: object) -> None:
    catalogue = resolve_capital_mobiliario_concept_vocabulary(effective_date=_ON, authority=operation)

    with pytest.raises(RegistryValidationError):
        catalogue.require(token)


def test_the_withholding_rate_is_nineteen_per_cent_for_every_supported_year(
    operation: PinnedAuthorityOperation,
) -> None:
    years = filing_year_envelope().years
    assert years

    for year in years:
        rate = resolve_capital_mobiliario_withholding_rate(effective_date=date(year, 12, 31), authority=operation)

        assert rate == Decimal("0.19")


def test_a_changed_scalar_changes_the_resolved_rate(operation: PinnedAuthorityOperation) -> None:
    published = operation.resolve_governed_fact(
        ScalarFactQuery(
            fact_id="capital-mobiliario-withholding-rate",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=_ON,
        ),
    )
    assert isinstance(published, ResolvedScalarFact)
    changed = published.model_copy(
        update={"payload": published.payload.model_copy(update={"value": Decimal("0.21")})},
    )
    authority = _FixedFact(changed, operation.supported_filing_years())

    assert resolve_capital_mobiliario_withholding_rate(effective_date=_ON, authority=authority) == Decimal("0.21")


def test_a_rate_outside_zero_and_one_is_refused(operation: PinnedAuthorityOperation) -> None:
    published = operation.resolve_governed_fact(
        ScalarFactQuery(
            fact_id="capital-mobiliario-withholding-rate",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=_ON,
        ),
    )
    assert isinstance(published, ResolvedScalarFact)
    changed = published.model_copy(update={"payload": published.payload.model_copy(update={"value": Decimal("19")})})
    authority = _FixedFact(changed, operation.supported_filing_years())

    with pytest.raises(RegistryValidationError):
        resolve_capital_mobiliario_withholding_rate(effective_date=_ON, authority=authority)
