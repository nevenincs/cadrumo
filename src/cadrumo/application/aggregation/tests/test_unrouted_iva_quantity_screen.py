"""The IVA quantity screen catches a dropped quantity the row screen cannot see.

Every IVA row carries three INDEPENDENT quantities -- the taxable base, the
cuota charged on it, and the recargo de equivalencia surcharged alongside. The
row-level screen (``unsupported_ledger_iva_observations``) reports a row as
consumed the moment ANY binding selects it, so a row consumed for its cuota
stays "routed" while its base imponible reaches no binding at all. These tests
pin that gap closed on the axis the row screen is blind to, and prove the
blindness rather than asserting it.

Every row here starts from a real :class:`Transaction` driven through the
production projection. Hand-building an ``IvaLedgerObservation`` would let the
fixture assert its own classification: the observation carries category, rate
kind and flow direction as fields, so such a test passes with the projection
deleted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    ModeloRevision,
    unrouted_ledger_iva_quantities,
    unsupported_ledger_iva_observations,
)
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from .. import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC)
_Q1_2025 = Period.from_year_and_code(2025, "1T")

#: The Modelo 303 revision that governs the period above. It declares all three
#: IVA facts, which is what makes it the right control: an advisory here would
#: be a false fire on the quarterly return every taxpayer files.
_M303_REVISION_ID = "2023-y-siguientes"


@cache
def _m303_revision() -> ModeloRevision:
    return resources().modelos.get("303").revisions[_M303_REVISION_ID]


def _sale(
    provider_id: str,
    *,
    base: str,
    iva: str,
    recargo: str | None = None,
) -> Transaction:
    """A domestic standard-rate sale carrying base, cuota and optional recargo."""
    recargo_amount = None if recargo is None else Decimal(recargo)
    gross = Decimal(base) + Decimal(iva) + (recargo_amount or Decimal("0"))
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=gross,
        currency="EUR",
        counterparty="Minorista Recargo SL",
        description=f"venta {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": provider_id},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal(base),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal(iva),
            "recargo_amount": recargo_amount,
            "iva_category": IvaCategory.DOMESTIC_STANDARD,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _observations(*transactions: Transaction) -> tuple[object, ...]:
    """Project real transactions through the production IVA aggregation."""
    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(transactions),
        period=_Q1_2025,
    )
    assert result.observations, "the projection emitted no declarable observation to screen"
    return result.observations


def _revision_without_fact(revision: ModeloRevision, fact: str) -> ModeloRevision:
    """Return ``revision`` with every ``ledger_iva_aggregation`` binding drawing ``fact`` removed.

    Models the regression under test: a revision that draws a row's other
    quantities while never declaring a binding for this one. Modelo 390 is the
    standing real instance for ``base_amount_sum``, but the assertion is pinned
    on the stripped revision rather than on M390's current declarations so that
    closing that gap in the registry cannot turn this test into a false claim.
    """
    kept = [
        binding
        for binding in revision.bindings
        if not (binding.source.value == "ledger_iva_aggregation" and getattr(binding.selector, "fact", None) == fact)
    ]
    return revision.model_copy(update={"bindings": tuple(kept)})


def test_the_committed_revision_draws_every_quantity_its_rows_carry() -> None:
    """The real Modelo 303 revision routes base, cuota and recargo -- no advisory."""
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00", recargo="52.00"))

    assert unrouted_ledger_iva_quantities(_m303_revision(), rows) == ()


def test_a_revision_drawing_no_base_surfaces_the_whole_base() -> None:
    """The Modelo 390 shape: cuota and recargo drawn, base imponible drawn by nothing."""
    revision = _revision_without_fact(_m303_revision(), "base_amount_sum")
    rows = _observations(
        _sale("s-1", base="1000.00", iva="210.00"),
        _sale("s-2", base="2000.00", iva="420.00"),
    )

    unrouted = unrouted_ledger_iva_quantities(revision, rows)

    assert len(unrouted) == 1
    assert unrouted[0].fact == "base_amount_sum"
    assert unrouted[0].total == Decimal("3000.00")
    assert len(unrouted[0].observations) == 2


def test_the_row_screen_stays_silent_on_the_same_defect() -> None:
    """The blindness this screen exists for, proved rather than asserted.

    Same revision and rows as the test above. The row screen reports nothing,
    because both rows are still consumed by the cuota bindings -- so without the
    quantity screen the undrawn base imponible has a clean screen on both sides.
    """
    revision = _revision_without_fact(_m303_revision(), "base_amount_sum")
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00"))

    assert unsupported_ledger_iva_observations(revision, rows) == ()
    assert unrouted_ledger_iva_quantities(revision, rows) != ()


def test_a_quantity_the_rows_do_not_carry_raises_nothing() -> None:
    """A legitimate zero is not a modelling gap.

    Anti-false-fire control: the recargo bindings are absent AND the rows carry
    no recargo. Without this the screen would fire on every taxpayer who simply
    sells to no recargo-regime retailer.
    """
    revision = _revision_without_fact(_m303_revision(), "recargo_amount_sum")
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00"))

    assert unrouted_ledger_iva_quantities(revision, rows) == ()


@pytest.mark.parametrize(
    ("fact", "expected_total"),
    [
        ("base_amount_sum", Decimal("1000.00")),
        ("iva_amount_sum", Decimal("210.00")),
        ("recargo_amount_sum", Decimal("52.00")),
    ],
)
def test_no_iva_fact_is_excluded_as_an_alternative_measure(fact: str, expected_total: Decimal) -> None:
    """The IVA exclusion set is empty, and that is a measured property.

    On the renta side three income measures ARE alternatives, so omitting two of
    them is a modelling choice and screening them would fire on every revision.
    Base, cuota and recargo are not measures of one quantity: no one of them
    stands in for another, so dropping ANY of the three loses a real amount and
    every one of them must report.
    """
    revision = _revision_without_fact(_m303_revision(), fact)
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00", recargo="52.00"))

    unrouted = unrouted_ledger_iva_quantities(revision, rows)

    assert [entry.fact for entry in unrouted] == [fact]
    assert unrouted[0].total == expected_total


def test_the_screen_reads_the_revision_it_is_given() -> None:
    """Guards against a screen that hardcodes which facts M303 draws.

    An implementation asserting "the IVA family draws all three" would pass
    every test above. This one fails it: the same rows must report differently
    against a revision that draws the fact and one that does not.
    """
    committed = _m303_revision()
    stripped = _revision_without_fact(committed, "base_amount_sum")
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00"))

    assert unrouted_ledger_iva_quantities(committed, rows) == ()
    assert unrouted_ledger_iva_quantities(stripped, rows) != ()
