"""An income family with no calculator is a blocking finding on the annual return, never a silent absence.

Every case runs the production Modelo 100 resolver over real ledger rows, against
the revision and the coverage fact of the published authority. The ledger rows are
read raw for the filing period: an outgoing gain row or a capital row is exactly
what the income aggregation does not keep, so reading its observations would see
nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
)
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.facts.resolution import (
    GovernedFactQuery,
    ResolvedGovernedFact,
    ResolvedMappingFact,
)
from ....domain.calculations.registry.irpf_income_categories import (
    irpf_income_categories_without_calculator,
    irpf_income_family_casilla_sections,
)
from ....domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.tests.register_support import MemoryRepository
from ...modelo.bucket_unrouted_source_issues import unrouted_source_issues
from ...modelo.calculation_note_gate import gate_refuses
from ...modelo.calculation_notes import CALCULATION_NOTE_ATTENTION, GATE_REFUSED_REASONS, note_fact_text
from ...modelo.printed_boxes import snapshot_printed_boxes
from ..income_family_not_computed import (
    income_family_casilla_ids,
    income_family_entry_digests_after_edit,
    income_family_not_computed_diagnostics,
    income_family_row_digests,
)
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..retencion_soportada_source import IRPF_INCOME_CATEGORIES_PROFILE_PATH
from ..source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceResolution
from .ledger_source_mesh_support import InMemoryTransactionCatalogueRepository, cash_criterion_profile
from .renta_income_aggregation_support import catalogue_read_ports, renta_income_aggregation_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "c4f1a2b3-5d6e-4f70-8a91-b2c3d4e5f607"
_REASON = "income_family_not_computed"
_YEAR = newest_authored_edition("100")
_COVERAGE_FACT_ID = "irpf-income-family-calculator-coverage"
_CAPITAL = "capital_mobiliario"
_GAINS = "ganancias_patrimoniales"
_RENTA_INCOME = BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION


def _row(
    provider_id: str,
    *,
    category: str | None,
    direction: TransactionDirection = TransactionDirection.INCOMING,
    value_date: date | None = None,
) -> Transaction:
    booked = value_date or date(_YEAR, 6, 15)
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked,
        value_date=booked,
        amount=Decimal("120.00"),
        currency="EUR",
        counterparty="Banco SA",
        description="movimiento",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_YEAR, 7, 1, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 7, 1, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _context(
    *,
    modelo: str = "100",
    period_code: str = "0A",
    declared: str | None = None,
    entered: dict[str, str] | None = None,
) -> CalculationSourceContext:
    extra = () if declared is None else (UserProfileFact(path=IRPF_INCOME_CATEGORIES_PROFILE_PATH, value=declared),)
    return CalculationSourceContext(
        bucket_id=_BUCKET,
        modelo=modelo,
        filing_year=_YEAR,
        period=renta_income_aggregation_period(_YEAR, period_code),
        revision=published_snapshot(modelo, filing_year=_YEAR, period=period_code).revision,
        profile=cash_criterion_profile(_YEAR, extra_facts=extra),
        income_family_entry_digests=entered or {},
    )


def _resolve(*rows: Transaction, context: CalculationSourceContext) -> CalculationSourceResolution:
    transactions = TransactionCatalogue.from_transactions(rows)
    repository = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=InvoiceCatalogue(), transactions=transactions),
    )
    return resolver.resolve(context)


def _findings(resolution: CalculationSourceResolution) -> list[CalculationSourceDiagnostic]:
    return [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == _REASON]


def _family(diagnostic: CalculationSourceDiagnostic) -> str:
    assert diagnostic.source_ref is not None
    return diagnostic.source_ref.removeprefix("income-family:")


def test_a_capital_row_in_the_window_raises_one_blocking_finding_with_its_count() -> None:
    resolution = _resolve(_row("interest-1", category=_CAPITAL), context=_context())

    (finding,) = _findings(resolution)
    assert _family(finding) == _CAPITAL
    assert "1 ledger row(s)" in finding.message
    assert finding.binding_source is _RENTA_INCOME
    assert finding.source_kind == _RENTA_INCOME.value
    assert _REASON in GATE_REFUSED_REASONS
    assert gate_refuses(_REASON, finding.binding_source)


def test_the_count_is_the_number_of_rows_of_the_family() -> None:
    resolution = _resolve(
        _row("interest-1", category=_CAPITAL),
        _row("interest-2", category=_CAPITAL, value_date=date(_YEAR, 9, 1)),
        _row("interest-3", category=_CAPITAL, value_date=date(_YEAR, 12, 31)),
        context=_context(),
    )

    (finding,) = _findings(resolution)
    assert "3 ledger row(s)" in finding.message


def test_an_outgoing_gain_row_raises_the_finding_for_its_family() -> None:
    resolution = _resolve(_row("loss-1", category=_GAINS, direction=TransactionDirection.OUTGOING), context=_context())

    (finding,) = _findings(resolution)
    assert _family(finding) == _GAINS
    assert "1 ledger row(s)" in finding.message


def test_each_family_raises_its_own_finding() -> None:
    resolution = _resolve(_row("interest-1", category=_CAPITAL), _row("gain-1", category=_GAINS), context=_context())

    assert sorted(_family(finding) for finding in _findings(resolution)) == sorted([_CAPITAL, _GAINS])


def test_a_declared_category_with_no_rows_raises_the_finding_with_count_zero() -> None:
    resolution = _resolve(context=_context(declared=_CAPITAL))

    (finding,) = _findings(resolution)
    assert _family(finding) == _CAPITAL
    assert "0 ledger row(s)" in finding.message
    assert "the profile declares it" in finding.message


def test_a_declaration_and_rows_of_the_same_family_raise_one_finding() -> None:
    resolution = _resolve(_row("interest-1", category=_CAPITAL), context=_context(declared=f"trabajo,{_CAPITAL}"))

    (finding,) = _findings(resolution)
    assert "1 ledger row(s)" in finding.message
    assert "the profile declares it" in finding.message


def test_a_computed_family_row_and_declaration_raise_nothing() -> None:
    resolution = _resolve(_row("pay-1", category="trabajo"), context=_context(declared="trabajo"))

    assert _findings(resolution) == []


def test_a_row_outside_the_filing_window_raises_nothing() -> None:
    resolution = _resolve(
        _row("old-interest", category=_CAPITAL, value_date=date(_YEAR - 1, 6, 15)), context=_context()
    )

    assert _findings(resolution) == []


def test_the_finding_persists_and_the_gate_refuses_on_it(operation: PinnedAuthorityOperation) -> None:
    resolution = _resolve(_row("interest-1", category=_CAPITAL), context=_context())
    snapshot = operation.snapshot("100", filing_year=_YEAR, period="0A")

    issues = unrouted_source_issues(resolution.diagnostics, snapshot_printed_boxes(operation, snapshot))

    (issue,) = [issue for issue in issues if issue.reason == _REASON]
    assert issue.binding_source is _RENTA_INCOME
    assert gate_refuses(issue.reason, issue.binding_source)


def test_the_finding_is_on_the_blocking_level_of_the_scale() -> None:
    assert CALCULATION_NOTE_ATTENTION[_REASON].name == "BLOCKS"


def test_the_quarterly_instalment_modelo_raises_nothing() -> None:
    resolution = _resolve(
        _row("interest-1", category=_CAPITAL), context=_context(modelo="130", period_code="2T", declared=_CAPITAL)
    )

    assert _findings(resolution) == []


@dataclass
class _CoverageVariant:
    """Authority whose coverage fact marks the chosen families computed; every other fact is the published one."""

    inner: PinnedAuthorityOperation
    computed: frozenset[str]

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        resolved = self.inner.resolve_governed_fact(query)
        if query.fact_id != _COVERAGE_FACT_ID:
            return resolved
        assert isinstance(resolved, ResolvedMappingFact)
        marked = {f"irpf_income_family.{family}.computed" for family in self.computed}
        entries = tuple(
            entry.model_copy(update={"value": "true"}) if entry.key in marked else entry
            for entry in resolved.payload.entries
        )
        return resolved.model_copy(update={"payload": resolved.payload.model_copy(update={"entries": entries})})

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.inner.supported_filing_years()


def _diagnostics_under(
    authority: _CoverageVariant | PinnedAuthorityOperation, rows: tuple[Transaction, ...]
) -> tuple[CalculationSourceDiagnostic, ...]:
    return income_family_not_computed_diagnostics(
        _context(declared=_GAINS), rows, authority=authority, resolver_id="ledger_renta_income_aggregation"
    )


def test_the_uncomputed_set_is_read_from_the_registry_fact(operation: PinnedAuthorityOperation) -> None:
    rows = (_row("interest-1", category=_CAPITAL), _row("gain-1", category=_GAINS))

    authored = _diagnostics_under(operation, rows)
    capital_computed = _diagnostics_under(_CoverageVariant(operation, frozenset({_CAPITAL})), rows)
    all_computed = _diagnostics_under(_CoverageVariant(operation, frozenset({_CAPITAL, _GAINS})), rows)

    assert sorted(_family(item) for item in authored) == sorted([_CAPITAL, _GAINS])
    assert [_family(item) for item in capital_computed] == [_GAINS]
    assert all_computed == ()


def test_the_registry_fact_names_the_two_families_without_a_calculator(operation: PinnedAuthorityOperation) -> None:
    assert irpf_income_categories_without_calculator(
        effective_date=date(filing_year_envelope().horizon, 12, 31), authority=operation
    ) == {_CAPITAL, _GAINS}


# Binding a hand entry to the rows present at entry.


def _entered(*rows: Transaction, families: tuple[str, ...] = (_CAPITAL,)) -> dict[str, str]:
    """The entry digests an edit records for ``families`` when ``rows`` are the window's rows."""
    return income_family_row_digests(rows, families)


def test_figures_entered_against_the_rows_present_clear_the_finding() -> None:
    rows = (_row("interest-1", category=_CAPITAL), _row("interest-2", category=_CAPITAL))

    resolution = _resolve(*rows, context=_context(entered=_entered(*rows)))

    assert _findings(resolution) == []


def test_a_row_added_after_the_entry_raises_the_finding_again_saying_the_rows_changed() -> None:
    entered = _entered(_row("interest-1", category=_CAPITAL))

    resolution = _resolve(
        _row("interest-1", category=_CAPITAL), _row("interest-2", category=_CAPITAL), context=_context(entered=entered)
    )

    (finding,) = _findings(resolution)
    assert _family(finding) == _CAPITAL
    assert "changed after its figures were entered by hand" in finding.message
    assert finding.fact == CalculationNoteFact.of(
        CalculationNoteSentence.INCOME_FAMILY_ROWS_CHANGED_SINCE_ENTRY, count=2
    )
    assert gate_refuses(finding.reason, finding.binding_source)


def test_a_row_reclassified_away_after_the_entry_raises_the_finding_again() -> None:
    entered = _entered(_row("interest-1", category=_CAPITAL), _row("interest-2", category=_CAPITAL))

    resolution = _resolve(
        _row("interest-1", category=_CAPITAL), _row("interest-2", category="trabajo"), context=_context(entered=entered)
    )

    (finding,) = _findings(resolution)
    assert finding.fact == CalculationNoteFact.of(
        CalculationNoteSentence.INCOME_FAMILY_ROWS_CHANGED_SINCE_ENTRY, count=1
    )


def test_a_finding_never_entered_keeps_its_first_words_and_no_fact() -> None:
    resolution = _resolve(_row("interest-1", category=_CAPITAL), context=_context())

    (finding,) = _findings(resolution)
    assert finding.fact is None
    assert "changed" not in finding.message


def test_an_entry_for_one_family_leaves_the_other_family_raised() -> None:
    rows = (_row("interest-1", category=_CAPITAL), _row("gain-1", category=_GAINS))

    resolution = _resolve(*rows, context=_context(entered=_entered(*rows, families=(_CAPITAL,))))

    assert [_family(finding) for finding in _findings(resolution)] == [_GAINS]


def test_a_declared_family_with_no_rows_is_cleared_by_an_entry_made_while_it_had_none() -> None:
    resolution = _resolve(context=_context(declared=_CAPITAL, entered=_entered()))

    assert _findings(resolution) == []


def test_the_row_digest_reads_the_ids_of_the_family_rows_only_and_not_their_order() -> None:
    first, second = _row("interest-1", category=_CAPITAL), _row("interest-2", category=_CAPITAL)
    other = _row("pay-1", category="trabajo")

    assert _entered(first, second) == _entered(other, second, first)
    assert _entered(first) != _entered(first, second)
    assert _entered() != _entered(first)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_changed_rows_sentence_is_worded_in_every_language(language: OutputLanguage) -> None:
    fact = CalculationNoteFact.of(CalculationNoteSentence.INCOME_FAMILY_ROWS_CHANGED_SINCE_ENTRY, count=3)

    words = note_fact_text(fact, locale=language.value)

    assert "3" in words
    assert "{" not in words
    assert fact.sentence.value not in words


# Which entry digests an edit leaves on the operator layer.

_C1, _C2, _G1 = (validated_casilla_id(token) for token in ("0027", "0029", "0310"))
_FAMILY_CASILLAS = {_CAPITAL: frozenset({_C1, _C2}), _GAINS: frozenset({_G1})}
_EARLIER = {_CAPITAL: "a" * 64}
_NOW = "b" * 64


@dataclass
class _Reader:
    """The ledger digests an edit would read now, recording which families it was asked for."""

    asked: list[frozenset[str]]

    def __call__(self, families: frozenset[str]) -> dict[str, str]:
        self.asked.append(families)
        return dict.fromkeys(families, _NOW)


def _after_edit(*, entered: frozenset[CasillaId], set_now: frozenset[CasillaId], reader: _Reader) -> dict[str, str]:
    return income_family_entry_digests_after_edit(
        _EARLIER,
        family_casilla_ids=_FAMILY_CASILLAS,
        entered_casilla_ids=entered,
        set_casilla_ids=set_now,
        current_digests=reader,
    )


def test_setting_a_family_casilla_binds_the_family_to_the_rows_present_now() -> None:
    reader = _Reader([])

    assert _after_edit(entered=frozenset({_C1, _G1}), set_now=frozenset({_C1, _G1}), reader=reader) == {
        _CAPITAL: _NOW,
        _GAINS: _NOW,
    }
    assert reader.asked == [frozenset({_CAPITAL, _GAINS})]


def test_an_edit_that_sets_no_family_casilla_keeps_the_earlier_entry_and_reads_no_ledger() -> None:
    reader = _Reader([])

    assert _after_edit(entered=frozenset({_C1, _C2}), set_now=frozenset(), reader=reader) == _EARLIER
    assert reader.asked == []


def test_a_partial_clear_keeps_the_entry_and_a_full_clear_drops_it() -> None:
    reader = _Reader([])

    assert _after_edit(entered=frozenset({_C2}), set_now=frozenset(), reader=reader) == _EARLIER
    assert _after_edit(entered=frozenset(), set_now=frozenset(), reader=reader) == {}


def test_a_family_entered_without_a_recorded_entry_gains_none_until_it_is_set_again() -> None:
    reader = _Reader([])

    assert _after_edit(entered=frozenset({_C1, _G1}), set_now=frozenset(), reader=reader) == _EARLIER


def test_each_uncomputed_family_names_casillas_of_every_admitted_modelo_100_year(
    operation: PinnedAuthorityOperation,
) -> None:
    admitted = 0
    for year in sorted(operation.supported_filing_years().years):
        try:
            snapshot = operation.reading_snapshot("100", filing_year=year, period="0A")
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted += 1
        sections = irpf_income_family_casilla_sections(effective_date=date(year, 12, 31), authority=operation)
        casillas = income_family_casilla_ids(
            snapshot.revision, {str(family): tokens for family, tokens in sections.items()}
        )

        assert set(casillas) == {_CAPITAL, _GAINS}, year
        assert all(casillas.values()), (year, casillas)
        assert not casillas[_CAPITAL] & casillas[_GAINS], year
    assert admitted
