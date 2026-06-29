"""Renta income source-jurisdiction and M100 annual aggregation tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import resolve_ledger_renta_income_aggregation_binding_values
from ....domain.transactions import TransactionCatalogue
from .._renta_income_ledger import aggregate_renta_income_ledger, aggregate_renta_m100_income_ledger
from ._renta_income_aggregation_support import (
    _ANNUAL_2024,
    _M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA,
    _M130_INGRESOS_CASILLA,
    _Q1_2024,
    _actividad_transaction_with_source,
    _income_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# S385a: source_jurisdiction provenance pass-through (#258)
#
# LIRPF Art. 8 establishes the universal-base presumption for Spanish-
# resident taxpayers: M100 / M130 actividad-económica income aggregates
# ALL source jurisdictions into the same base, with foreign-source rows
# carrying their declared jurisdiction through for audit. The IRNR /
# Beckham per-row gating concerns (Art. 25 TRLIRNR, Art. 93.5 LIRPF)
# belong on those engines (#256 IRNR pending; M151 pending); on the
# resident-IRPF surface the source_jurisdiction is provenance only.
# ---------------------------------------------------------------------------


def test_renta_income_observation_preserves_es_source_jurisdiction() -> None:
    """A Spanish-source actividad row carries source_jurisdiction="ES" on the observation.

    Provenance witness for the M100 / M130 income pipeline. The
    aggregation does NOT filter on source_jurisdiction (Art. 8 universal-
    base presumption); it propagates the declared value from the ledger
    row onto the typed observation so downstream auditors and the future
    IRNR / Beckham engines can read the jurisdiction without retrofitting
    the read-side.
    """
    tx = _actividad_transaction_with_source(
        "ae-es-001",
        value_date=date(2024, 2, 1),
        amount=Decimal("3000.00"),
        source_jurisdiction="ES",
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert len(result.observations) == 1
    assert result.observations[0].source_jurisdiction == "ES"


def test_renta_income_aggregation_mixes_es_and_foreign_source() -> None:
    """LIRPF Art. 8: ES and foreign-source rows BOTH enter the M130 base; jurisdictions distinct.

    The universal-base presumption (LIRPF Art. 8.1) taxes Spanish residents
    on worldwide income, so a foreign-source row from an FR client must
    aggregate into casilla 01 alongside ES rows. This test guards against
    a future "clean-up" refactor that filters foreign-source out of the
    resident-IRPF surface — that would silently under-state the base for
    every resident with cross-border income (Pedro intracom, Olivia UK
    landlord pre-IRNR move, etc.).

    Distinct-preservation: both observations must carry their declared
    jurisdiction; collapsing both to "ES" or to None would lose the audit
    trail and break the future IRNR / Beckham read-side.
    """
    es_amount = Decimal("1000.00")
    fr_amount = Decimal("500.00")
    es_row = _actividad_transaction_with_source(
        "ae-es-002",
        value_date=date(2024, 1, 15),
        amount=es_amount,
        source_jurisdiction="ES",
    )
    fr_row = _actividad_transaction_with_source(
        "ae-fr-001",
        value_date=date(2024, 2, 10),
        amount=fr_amount,
        source_jurisdiction="FR",
    )
    catalogue = TransactionCatalogue.from_transactions((es_row, fr_row))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    # Art. 8 universal-base: both rows enter the casilla aggregation.
    assert len(result.observations) == 2
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == es_amount + fr_amount
    # Distinct-preservation witness: each observation carries its own
    # jurisdiction unchanged.
    by_id = {obs.transaction_id: obs for obs in result.observations}
    assert by_id[es_row.transaction_id].source_jurisdiction == "ES"
    assert by_id[fr_row.transaction_id].source_jurisdiction == "FR"


# ---------------------------------------------------------------------------
# Modelo 100 annual actividad-económica income aggregation (casilla 0171)
# ---------------------------------------------------------------------------


def test_m100_annual_income_sums_full_ejercicio_into_casilla_0171() -> None:
    """The annual M100 path sums actividad income over the full year into 0171.

    Unlike the M130 cumulative-quarter window, the annual window spans Jan 1 to
    Dec 31, so a December receipt is included and the target is the M100 income
    leaf 0171, not the M130 casilla 01.
    """
    jan_amount, dec_amount = Decimal("3000.00"), Decimal("5000.00")
    jan = _income_transaction("m100-jan", value_date=date(2024, 1, 20), amount=jan_amount)
    dec = _income_transaction("m100-dec", value_date=date(2024, 12, 28), amount=dec_amount)
    prior = _income_transaction("m100-prior", value_date=date(2023, 12, 31), amount=Decimal("999.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, dec, prior))

    result = aggregate_renta_m100_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)

    assert all(o.target_casilla_id == _M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA for o in result.observations)
    assert result.casilla_aggregation.modelo == "100"
    # Prior-year row excluded; in-year receipts summed into 0171.
    assert {o.transaction_id for o in result.observations} == {jan.transaction_id, dec.transaction_id}
    assert result.casilla_aggregation.casilla_values[_M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA] == sum(
        (jan_amount, dec_amount),
        Decimal("0"),
    )


def test_m100_annual_income_rejects_non_annual_period() -> None:
    """The annual M100 income aggregator refuses a quarterly period."""
    from .._errors import AggregationPeriodError

    catalogue = TransactionCatalogue.from_transactions(())
    with pytest.raises(AggregationPeriodError):
        aggregate_renta_m100_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)


def test_m100_revision_binds_0171_to_income_source_and_resolves() -> None:
    """The real M100 2025 revision binds casilla 0171 to the income source and folds it.

    Uses the live registry revision so the binding id, selector, and casilla
    wiring under test are exactly what ships. Expected value derived from the
    input, never copied from engine output.
    """
    modelo_def = next(item for item in resources().modelos.all() if item.id == "100")
    revision = modelo_def.revisions["2025"]
    casilla_0171 = next(c for c in revision.casillas if c.id == _M100_ACTIVIDAD_ECONOMICA_INGRESOS_CASILLA)
    assert str(casilla_0171.input_kind) == "bound"
    binding = next(b for b in revision.bindings if b.id == casilla_0171.binding)
    assert str(binding.source) == "ledger_renta_income_aggregation"

    base = Decimal("4200.00")
    tx = _income_transaction("m100-res", value_date=date(2024, 6, 1), amount=base)
    catalogue = TransactionCatalogue.from_transactions((tx,))
    aggregation = aggregate_renta_m100_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    assert resolved[binding.id] == base
