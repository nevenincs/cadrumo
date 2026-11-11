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
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.facts.resolution import (
    GovernedFactQuery,
    ResolvedGovernedFact,
    ResolvedMappingFact,
)
from ....domain.calculations.registry.irpf_income_categories import irpf_income_categories_without_calculator
from ....domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.tests.register_support import MemoryRepository
from ...modelo.bucket_unrouted_source_issues import unrouted_source_issues
from ...modelo.calculation_note_gate import gate_refuses
from ...modelo.calculation_notes import CALCULATION_NOTE_ATTENTION, GATE_REFUSED_REASONS
from ...modelo.printed_boxes import snapshot_printed_boxes
from ..income_family_not_computed import income_family_not_computed_diagnostics
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


def _context(*, modelo: str = "100", period_code: str = "0A", declared: str | None = None) -> CalculationSourceContext:
    extra = () if declared is None else (UserProfileFact(path=IRPF_INCOME_CATEGORIES_PROFILE_PATH, value=declared),)
    return CalculationSourceContext(
        bucket_id=_BUCKET,
        modelo=modelo,
        filing_year=_YEAR,
        period=renta_income_aggregation_period(_YEAR, period_code),
        revision=published_snapshot(modelo, filing_year=_YEAR, period=period_code).revision,
        profile=cash_criterion_profile(_YEAR, extra_facts=extra),
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
