"""A dateless vocabulary read never depends on the date the program runs.

Each catalogue is read through the published authority without a date while the
clock is frozen outside the supported filing years, and the result is compared
with the union of the dated reads at every year of the support envelope.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from .....core.time.clock import frozen_clock, today_madrid
from ..authority import bundled_indexed_authority
from ..concepto_ingreso import resolve_concepto_ingreso_catalogue
from ..entity_type import resolve_entity_vocabulary
from ..eu_member_state_catalogue import resolve_eu_member_state_catalogue
from ..facts.resolution import GovernedFactQuery, MappingFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from ..facts.schema import GovernedFact, GovernedFactCatalogue
from ..gasto_capital_inmobiliario import resolve_gasto_capital_inmobiliario_catalogue
from ..governed_fact_scope import CandidateFactAuthority, GovernedFactSource
from ..irpf_regimes import resolve_irpf_regime_vocabulary
from ..iva_regime_vocabulary import (
    iva_regime_simplificado_token,
    resolve_iva_regime_catalogue,
)
from ..m303_schema_vocabulary import (
    resolve_m303_regime_composition_catalogue,
    resolve_m303_tax_territory_catalogue,
)
from ..renta_codes_catalogue import fiscal_residency_choices, ue_eea_country_codes
from ..schema_base import DateAxis
from ..snapshot_globals import SupportedFilingYearsCatalogue
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> Iterator[GovernedFactSource]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _envelope_dates() -> tuple[date, ...]:
    return tuple(date(year, month, 1) for year in filing_year_envelope().years for month in (1, 7))


def _outside_the_envelope() -> datetime:
    return datetime(filing_year_envelope().floor - 3, 6, 15, 12, tzinfo=UTC)


def _union_of_dated_reads[T](read: Callable[[date], frozenset[T]]) -> frozenset[T]:
    union: frozenset[T] = frozenset()
    for coordinate in _envelope_dates():
        union |= read(coordinate)
    return union


def test_the_dateless_eu_eea_country_set_is_the_envelope_union_whatever_the_run_date(
    authority: GovernedFactSource,
) -> None:
    with frozen_clock(_outside_the_envelope()):
        assert not filing_year_envelope().admits_coordinate(today_madrid().year)
        dateless = ue_eea_country_codes(authority=authority)

    assert dateless == _union_of_dated_reads(lambda on: ue_eea_country_codes(effective_date=on, authority=authority))
    assert "ES" in dateless


def test_the_dateless_eu_member_state_catalogue_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_eu_member_state_catalogue(authority=authority).all_states

    assert dateless == _union_of_dated_reads(
        lambda on: resolve_eu_member_state_catalogue(effective_date=on, authority=authority).all_states
    )


def test_the_dateless_entity_vocabulary_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_entity_vocabulary(authority=authority)

    assert dateless.all_entity_types == _union_of_dated_reads(
        lambda on: resolve_entity_vocabulary(effective_date=on, authority=authority).all_entity_types
    )
    assert dateless.all_legal_entity_forms == _union_of_dated_reads(
        lambda on: resolve_entity_vocabulary(effective_date=on, authority=authority).all_legal_entity_forms
    )


def test_the_dateless_irpf_regime_vocabulary_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_irpf_regime_vocabulary(authority=authority)

    assert dateless.all_estimation_regimes == _union_of_dated_reads(
        lambda on: resolve_irpf_regime_vocabulary(effective_date=on, authority=authority).all_estimation_regimes
    )
    assert dateless.all_special_regimes == _union_of_dated_reads(
        lambda on: resolve_irpf_regime_vocabulary(effective_date=on, authority=authority).all_special_regimes
    )


def test_dateless_fiscal_residency_choices_do_not_follow_the_clock(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        outside = fiscal_residency_choices(authority=authority)
    newest = fiscal_residency_choices(effective_date=date(filing_year_envelope().horizon, 12, 31), authority=authority)

    assert outside == newest


_OLDER_WORDING = "wording of the older edition"
_DESCRIPTION_KEYS = (
    "iva_regime.GENERAL.description",
    "tax_territory.common_regime.description",
    "m303_regime_composition.general.description",
)


@dataclass
class _TwoSchemaVocabularyEditions:
    """The published schema vocabulary split at a mid-year change into an older and a newer wording."""

    base: ResolvedMappingFact
    support: SupportedFilingYearsCatalogue
    change: date

    def _edition(self, *, older: bool, on: date) -> ResolvedMappingFact:
        entries = tuple(
            entry.model_copy(update={"value": _OLDER_WORDING}) if older and entry.key in _DESCRIPTION_KEYS else entry
            for entry in self.base.payload.entries
        )
        return self.base.model_copy(
            update={
                "payload": self.base.payload.model_copy(update={"entries": entries}),
                "variant_id": f"{self.base.fact_id}:{'older' if older else 'newer'}",
                "effective_date": on,
                "valid_from": date(filing_year_envelope().floor, 1, 1) if older else self.change,
                "valid_to": self.change - timedelta(days=1) if older else None,
            },
        )

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        return self._edition(older=query.effective_date < self.change, on=query.effective_date)

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.support


@pytest.fixture(scope="module")
def two_editions(authority: GovernedFactSource) -> _TwoSchemaVocabularyEditions:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-statutory-schema-vocabulary",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(filing_year_envelope().horizon, 3, 10),
        ),
    )
    assert isinstance(resolved, ResolvedMappingFact)
    return _TwoSchemaVocabularyEditions(
        base=resolved,
        support=filing_year_envelope(),
        change=date(filing_year_envelope().horizon, 7, 1),
    )


def _regime_wording(editions: _TwoSchemaVocabularyEditions, on: date | None) -> str:
    catalogue = resolve_iva_regime_catalogue(effective_date=on, authority=editions)
    return catalogue.definition(catalogue.default_token).description


def _territory_wording(editions: _TwoSchemaVocabularyEditions, on: date | None) -> str:
    catalogue = resolve_m303_tax_territory_catalogue(effective_date=on, authority=editions)
    return catalogue.definition("common_regime").description


def _composition_wording(editions: _TwoSchemaVocabularyEditions, on: date | None) -> str:
    catalogue = resolve_m303_regime_composition_catalogue(effective_date=on, authority=editions)
    return catalogue.definition(catalogue.general_only).description


_READS = (_regime_wording, _territory_wording, _composition_wording)


@pytest.mark.parametrize("read", _READS)
@pytest.mark.parametrize("run_year_offset", [-3, 0, 3])
def test_a_dateless_iva_schema_vocabulary_read_is_the_newest_edition_whatever_the_run_date(
    two_editions: _TwoSchemaVocabularyEditions,
    read: Callable[[_TwoSchemaVocabularyEditions, date | None], str],
    run_year_offset: int,
) -> None:
    envelope = filing_year_envelope()
    run_year = (envelope.floor if run_year_offset <= 0 else envelope.horizon) + run_year_offset
    newest = read(two_editions, two_editions.change)

    with frozen_clock(datetime(run_year, 2, 1, 12, tzinfo=UTC)):
        dateless = read(two_editions, None)

    assert newest != _OLDER_WORDING
    assert dateless == newest


@pytest.mark.parametrize("read", _READS)
def test_a_dated_iva_schema_vocabulary_read_still_selects_its_edition(
    two_editions: _TwoSchemaVocabularyEditions,
    read: Callable[[_TwoSchemaVocabularyEditions, date | None], str],
) -> None:
    assert read(two_editions, two_editions.change - timedelta(days=1)) == _OLDER_WORDING
    assert read(two_editions, two_editions.change) != _OLDER_WORDING


def test_a_dateless_iva_regime_semantic_token_does_not_follow_the_clock(
    two_editions: _TwoSchemaVocabularyEditions,
) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = iva_regime_simplificado_token(authority=two_editions)

    assert dateless == iva_regime_simplificado_token(effective_date=two_editions.change, authority=two_editions)


def test_the_dateless_income_concept_vocabulary_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_concepto_ingreso_catalogue(authority=authority).all_tokens

    assert dateless == _union_of_dated_reads(
        lambda on: resolve_concepto_ingreso_catalogue(effective_date=on, authority=authority).all_tokens
    )


def test_the_dateless_rental_expense_vocabulary_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_gasto_capital_inmobiliario_catalogue(authority=authority)
    newest = resolve_gasto_capital_inmobiliario_catalogue(
        effective_date=date(filing_year_envelope().horizon, 12, 31), authority=authority
    )

    assert dateless.all_tokens == _union_of_dated_reads(
        lambda on: resolve_gasto_capital_inmobiliario_catalogue(effective_date=on, authority=authority).all_tokens
    )
    assert dateless.concepts == newest.concepts


def _member_state_editions(withdrawn_on: date) -> CandidateFactAuthority:
    """Author fact 0131 twice: the later edition withdraws one member state."""

    def edition(valid_from: date, valid_to: date | None, order: str, aliases: str) -> dict[str, object]:
        return {
            "variant_id": f"eu-member-state-catalogue.{valid_from.isoformat()}",
            "date_axis": "filing_period",
            "valid_from": valid_from,
            "valid_to": valid_to,
            "payload": {
                "kind": "mapping",
                "entries": (
                    {"key": "member_state.order", "value": order},
                    {"key": "member_state.aliases", "value": aliases},
                ),
            },
            "legal_refs": ("test-law",),
            "source_refs": ("test-source",),
            "source_citations": ({"source_ref": "test-source", "required_text": ("test source",)},),
            "review_status": "pending_review",
            "ownership": "authored",
        }

    envelope = filing_year_envelope()
    fact = GovernedFact.model_validate(
        {
            "fact_id": "eu-member-state-catalogue",
            "family": "mapping",
            "variants": (
                edition(date(envelope.floor, 1, 1), withdrawn_on - timedelta(days=1), "at,be,de", "AT=at,BE=be,DE=de"),
                edition(withdrawn_on, None, "be,at", "AT=at,BE=be"),
            ),
        },
    )
    return CandidateFactAuthority(
        catalogue=GovernedFactCatalogue(facts={fact.fact_id: fact}),
        support=SupportedFilingYearsCatalogue(floor=envelope.floor, horizon=envelope.horizon),
    )


def test_a_member_state_a_later_edition_withdraws_stays_in_the_dateless_catalogue() -> None:
    withdrawn_on = date(filing_year_envelope().horizon, 7, 1)
    authority = _member_state_editions(withdrawn_on)

    dateless = resolve_eu_member_state_catalogue(authority=authority)
    before = resolve_eu_member_state_catalogue(effective_date=withdrawn_on - timedelta(days=1), authority=authority)
    after = resolve_eu_member_state_catalogue(effective_date=withdrawn_on, authority=authority)

    assert [str(definition.token) for definition in dateless.definitions] == ["be", "at", "de"]
    assert {alias: str(state) for alias, state in dateless.aliases.items()} == {"AT": "at", "BE": "be", "DE": "de"}
    assert [str(definition.token) for definition in before.definitions] == ["at", "be", "de"]
    assert [str(definition.token) for definition in after.definitions] == ["be", "at"]
