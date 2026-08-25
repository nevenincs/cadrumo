"""The agrarian volumen box is empty for a reason, and the reason must be said.

Modelo 131 casilla 05 admits a row only when it declares a tipo de actividad in
the art. 110.1.c) set. Nothing in production writes that field, so every real
filer's rows are undeclared and the box resolves to zero — the same zero a filer
with no agrarian activity at all correctly produces.

The exclusion rule is right and is not under test here except to prove it is
UNCHANGED: admitting an undeclared row would route a non-agrarian filer's income
into an agrarian box. What is under test is the signal, and the assertions divide
in two. The firing half proves the advisory appears, names the casilla, and
carries the registry's own grounding rather than prose minted in the application.

The non-firing half is the load-bearing one. An advisory that fired on every
filer with an empty box would fire on every inactive quarter, and an operator who
learns to skip it is an operator it cannot protect on the quarter where it is
genuinely right. So three populations are pinned silent: the filer with no income
at all, the filer who declared some other activity, and the filer whose box is
actually populated.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache

import pytest

from ....core import Modelo, Period, TipoActividad
from ....core.resources import resources
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from ....domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from .._renta_income_ledger import (
    RentaIncomeLedgerAggregation,
    _m131_agrarian_activity_codes,
    aggregate_renta_income_ledger,
    aggregate_renta_m131_agrario_income_ledger,
)
from .._source_mesh import CalculationSourceDiagnostic
from .._undeclared_activity_advisory import undeclared_activity_income_advisory_observations
from ._renta_income_aggregation_support import _raw_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "9f86d081-884c-4d65-9a2f-eaa0c55ad015"  # was 'test'
_Q1 = Period.from_year_and_code(2025, "1T")
_IN_WINDOW = date(2025, 2, 14)
_CASILLA_05 = "05"


@cache
def _m131_revision() -> ModeloRevision:
    """The real Modelo 131 revision, so the grounding assertions read real refs."""
    return resources().modelos.get(Modelo.M131.value).revisions["2025"]


def _income_row(
    provider_id: str,
    *,
    amount: Decimal = Decimal("1000.00"),
    tipo_actividad: TipoActividad | None = None,
    direction: TransactionDirection = TransactionDirection.INCOMING,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=_IN_WINDOW,
                value_date=_IN_WINDOW,
                amount=amount,
                currency="EUR",
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "tipo_actividad": tipo_actividad,
            "concepto_ingreso": None,
        },
    )


def _catalogue(*transactions: Transaction) -> TransactionCatalogue:
    return TransactionCatalogue.model_validate(
        {"transactions": {row.transaction_id: row for row in transactions}},
    )


def _advisories(
    *transactions: Transaction,
) -> tuple[RentaIncomeLedgerAggregation, tuple[CalculationSourceDiagnostic, ...]]:
    aggregation = aggregate_renta_m131_agrario_income_ledger(
        _catalogue(*transactions),
        bucket_id=_BUCKET,
        period=_Q1,
    )
    return aggregation, undeclared_activity_income_advisory_observations(aggregation, _m131_revision())


def _non_agrarian_code() -> TipoActividad:
    """A declared activity the art. 110.1.c) selector excludes, resolved live.

    Derived from the registry selector rather than named, so a revision that
    widens or narrows the agrarian set cannot leave this test asserting against a
    code that has quietly changed sides.
    """
    agrarian = _m131_agrarian_activity_codes()
    return next(code for code in TipoActividad if code not in agrarian)


def test_income_with_no_declared_activity_raises_the_advisory() -> None:
    """A quarter carrying undeclared income against an empty box is reported."""
    aggregation, advisories = _advisories(_income_row("row-1"), _income_row("row-2"))

    assert len(advisories) == 1
    advisory = advisories[0]
    assert advisory.reason == "aggregation_activity_undeclared"
    assert advisory.casilla_id == _CASILLA_05
    assert aggregation.casilla_aggregation.casilla_values.get(_CASILLA_05) is None


def test_the_advisory_quotes_the_income_it_measured() -> None:
    """The figure is the excluded income, not a placeholder."""
    _aggregation, advisories = _advisories(
        _income_row("row-1", amount=Decimal("1200.00")),
        _income_row("row-2", amount=Decimal("800.00")),
    )

    assert "2000.00" in advisories[0].message
    assert "2 income row(s)" in advisories[0].message


def test_the_advisory_carries_the_registry_grounding() -> None:
    """Refs are READ from the casilla and its binding, never minted here.

    The expectation is derived from the revision — the authority — rather than
    written as a literal, so a production path that hardcoded an article would
    fail this even if the article happened to be the right one today.
    """
    revision = _m131_revision()
    casilla = next(candidate for candidate in revision.casillas if candidate.id == _CASILLA_05)
    binding = next(candidate for candidate in revision.bindings if candidate.id == casilla.binding)
    expected_legal = tuple(dict.fromkeys((*casilla.legal_refs, *binding.legal_refs)))
    expected_source = tuple(dict.fromkeys((*casilla.source_refs, *binding.source_refs)))

    _aggregation, advisories = _advisories(_income_row("row-1"))

    assert expected_legal, "the registry casilla carries no legal_refs; the assertion would be vacuous"
    assert advisories[0].legal_refs == expected_legal
    assert advisories[0].source_refs == expected_source
    assert advisories[0].binding_id == casilla.binding


def test_the_exclusion_rule_is_untouched_when_the_advisory_fires() -> None:
    """The advisory adds a signal; it never admits the row it speaks about."""
    aggregation, advisories = _advisories(_income_row("row-1"))

    assert advisories, "precondition: this is the firing case"
    assert aggregation.observations == ()
    assert aggregation.casilla_aggregation.casilla_values == {}


def test_an_empty_income_set_never_fires() -> None:
    """The load-bearing negative: a filer with no activity is not flagged.

    Firing here would put an advisory on every inactive quarter, which is how a
    diagnostic channel becomes noise the operator learns to skip.
    """
    _aggregation, advisories = _advisories()

    assert advisories == ()


def test_a_filer_with_only_outgoing_rows_never_fires() -> None:
    """No income means no excluded income, whatever else the ledger holds."""
    _aggregation, advisories = _advisories(
        _income_row("row-1", direction=TransactionDirection.OUTGOING),
    )

    assert advisories == ()


def test_a_declared_non_agrarian_activity_silences_it() -> None:
    """A filer who answered the question is not asked it again.

    The row is still excluded — correctly, it is not an art. 110.1.c) activity —
    but its exclusion is a declared answer rather than a silence, so the empty
    box is the right one and nothing needs saying.
    """
    _aggregation, advisories = _advisories(_income_row("row-1", tipo_actividad=_non_agrarian_code()))

    assert advisories == ()


def test_one_declared_row_among_undeclared_ones_silences_it() -> None:
    """The predicate is ANY declared activity, deliberately.

    A ledger that declares an activity anywhere is a ledger where the capture
    channel is in use, so an undeclared row beside it is an ordinary gap in data
    entry rather than the structural silence this advisory exists to report.
    """
    _aggregation, advisories = _advisories(
        _income_row("row-1"),
        _income_row("row-2", tipo_actividad=_non_agrarian_code()),
    )

    assert advisories == ()


def test_a_populated_casilla_is_not_reported() -> None:
    """A box with money in it is not a silent zero."""
    aggregation, advisories = _advisories(
        _income_row("row-1", tipo_actividad=TipoActividad.B01_AGRICOLA, amount=Decimal("500.00")),
        _income_row("row-2"),
    )

    assert aggregation.casilla_aggregation.casilla_values[_CASILLA_05] == Decimal("500.00")
    assert advisories == ()


def test_the_m130_path_carries_no_census_and_never_fires() -> None:
    """No narrowing ran, so there is no excluded population to speak about.

    ``None`` here is a different claim from an empty census: it says the question
    was never asked on this projection, and the advisory must not answer it.
    """
    aggregation = aggregate_renta_income_ledger(
        _catalogue(_income_row("row-1")),
        bucket_id=_BUCKET,
        period=_Q1,
    )

    assert aggregation.unadmitted_activity_income is None
    assert undeclared_activity_income_advisory_observations(aggregation, _m131_revision()) == ()
