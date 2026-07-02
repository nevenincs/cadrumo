"""Modelo 151 impatriado (Ley Beckham) Spanish-source base aggregation tests.

The régimen especial del art. 93 LIRPF (Ley Beckham) taxes a resident
impatriado by the IRNR scope rules: only Spanish-source income enters the base
liquidable general (art. 93.2, art. 25.1.f TRLIRNR segregation). These tests
prove the source-scope classifier consumes the per-row ``source_jurisdiction``
axis the CLI compels an impatriado to declare:

- an ES-source row folds into ``impatriado.base-liquidable-general``;
- a foreign-source row is segregated (BECKHAM_FOREIGN_SOURCE_SEGREGATED) and
  does NOT silently enter the base — an anti-tautology mutation flips the same
  row's jurisdiction and asserts the base drops and the issue fires;
- a ``source_jurisdiction is None`` row fails loud as the same segregation
  issue rather than being silently coerced to ES (no-silent-under-declaration);
- ``trabajo`` income (nómina — the class the M130 pipeline routes OUT) IS
  admitted into the impatriado base, while the same row is still excluded from
  the M130 actividad-económica casilla.

The expected base is derived from the art. 93.2 source-scope rule (which amounts
are in scope), not by re-running the aggregation arithmetic — a scope/structure
assertion, per no-tautological-calculation-tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.calculations.registry import (
    BindingId,
    RegistryValidationError,
    load_modelo_directory,
    resolve_ledger_impatriado_income_aggregation_binding_values,
    validate_ledger_impatriado_income_aggregation_binding_definition,
)
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
from .._impatriado_income_ledger import (
    ImpatriadoIncomeLedgerAggregation,
    ImpatriadoIncomeLedgerAggregationIssueReason,
    aggregate_impatriado_income_ledger,
)
from .._renta_income_ledger import (
    RentaIncomeLedgerAggregationIssueReason,
    aggregate_renta_m100_income_ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL_2024 = Period.from_year_and_code(2024, "0A")
_BASE_CASILLA = "impatriado.base-liquidable-general"
_M151_REGISTRY_DIR = Path(__file__).resolve().parents[3] / "_data" / "registry" / "aeat" / "modelos" / "151"


def _impatriado_transaction(
    provider_id: str,
    *,
    amount: Decimal,
    source_jurisdiction: str | None,
    irpf_category: str | None = "trabajo",
    direction: TransactionDirection = TransactionDirection.INCOMING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    value_date: date = date(2024, 3, 1),
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Empleador SA",
                description=f"impatriado income {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": provider_id},
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": source_jurisdiction,
            "business_classification": business_classification,
            "irpf_category": irpf_category,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _base_total(aggregation: ImpatriadoIncomeLedgerAggregation) -> Decimal:
    values = aggregation.casilla_aggregation.casilla_values
    return next((v for c, v in values.items() if str(c) == _BASE_CASILLA), Decimal("0"))


def test_es_source_income_folds_into_impatriado_base() -> None:
    """An ES-source trabajo row enters the impatriado base liquidable general."""
    tx = _impatriado_transaction("es-001", amount=Decimal("50000.00"), source_jurisdiction="ES")
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_impatriado_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)

    assert len(result.observations) == 1
    assert result.observations[0].transaction_id == tx.transaction_id
    assert result.observations[0].source_jurisdiction == "ES"
    # Base equals the single ES amount — derived from the art. 93.2 scope rule.
    assert _base_total(result) == Decimal("50000.00")
    assert not result.issues


def test_foreign_source_row_is_segregated_and_excluded() -> None:
    """A foreign-source row is segregated out of the base, never silently admitted.

    Anti-tautology: the SAME row with source_jurisdiction="ES" enters the base;
    mutating only the jurisdiction to a foreign code drops it from the base and
    fires the BECKHAM_FOREIGN_SOURCE_SEGREGATED issue carrying the rejected code.
    """
    es_row = _impatriado_transaction("row-es", amount=Decimal("40000.00"), source_jurisdiction="ES")
    fr_row = _impatriado_transaction("row-fr", amount=Decimal("40000.00"), source_jurisdiction="FR")

    admitted = aggregate_impatriado_income_ledger(
        TransactionCatalogue.from_transactions((es_row,)),
        bucket_id="test",
        period=_ANNUAL_2024,
    )
    segregated = aggregate_impatriado_income_ledger(
        TransactionCatalogue.from_transactions((fr_row,)),
        bucket_id="test",
        period=_ANNUAL_2024,
    )

    # ES admits; the identical foreign row is fully excluded from the base.
    assert _base_total(admitted) == Decimal("40000.00")
    assert _base_total(segregated) == Decimal("0")
    assert not segregated.observations
    assert len(segregated.issues) == 1
    issue = segregated.issues[0]
    assert issue.reason is ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED
    assert issue.rejected_source_jurisdiction == "FR"
    assert issue.transaction_id == fr_row.transaction_id


def test_none_jurisdiction_fails_loud_never_silently_es() -> None:
    """A None source_jurisdiction fails loud as a segregation issue, not an ES default.

    This is the load-bearing no-silent-under-declaration safeguard: an
    unresolved jurisdiction must NOT be coerced to ES and silently admitted.
    """
    tx = _impatriado_transaction("unresolved-001", amount=Decimal("70000.00"), source_jurisdiction=None)
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_impatriado_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)

    assert not result.observations
    assert _base_total(result) == Decimal("0")
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.reason is ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED
    # Distinguishable from a foreign-source segregation: no rejected code.
    assert issue.rejected_source_jurisdiction is None
    assert "unresolved" in issue.detail.lower()


def test_trabajo_income_admitted_into_m151_base_but_excluded_from_m130() -> None:
    """A trabajo (nómina) ES-source row feeds the M151 base yet stays out of M130.

    The impatriado base is predominantly rendimientos del trabajo — the exact
    income class the M130 actividad-económica pipeline routes OUT via
    TRABAJO_INCOME. This proves the two pipelines are complementary.
    """
    nomina = _impatriado_transaction(
        "nomina-001",
        amount=Decimal("90000.00"),
        source_jurisdiction="ES",
        irpf_category="trabajo",
    )
    catalogue = TransactionCatalogue.from_transactions((nomina,))

    m151 = aggregate_impatriado_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)
    assert _base_total(m151) == Decimal("90000.00")
    assert len(m151.observations) == 1

    # Same row through the M130 / M100 actividad-económica pipeline is excluded.
    m130 = aggregate_renta_m100_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)
    assert not m130.observations
    assert any(issue.reason is RentaIncomeLedgerAggregationIssueReason.TRABAJO_INCOME for issue in m130.issues)


def test_outgoing_row_is_not_owned_by_the_impatriado_base_pipeline() -> None:
    """An OUTGOING row is out of scope for the base and produces neither obs nor issue."""
    outgoing = _impatriado_transaction(
        "out-001",
        amount=Decimal("500.00"),
        source_jurisdiction="ES",
        direction=TransactionDirection.OUTGOING,
    )
    result = aggregate_impatriado_income_ledger(
        TransactionCatalogue.from_transactions((outgoing,)),
        bucket_id="test",
        period=_ANNUAL_2024,
    )
    assert not result.observations
    assert not result.issues
    assert _base_total(result) == Decimal("0")


def test_registry_binding_resolves_es_source_total_into_base() -> None:
    """The M151 registry binding resolves the ES-source observation total end to end.

    Loads the real M151 revision (with the ledger_impatriado_income_aggregation
    binding), aggregates a mixed ES/foreign catalogue, and asserts the binding
    value equals the ES-source total — segregated foreign income never reaches it.
    """
    revision = load_modelo_directory(_M151_REGISTRY_DIR).revisions["2015-y-siguientes"]
    es_row = _impatriado_transaction("bind-es", amount=Decimal("120000.00"), source_jurisdiction="ES")
    foreign_row = _impatriado_transaction("bind-de", amount=Decimal("55000.00"), source_jurisdiction="DE")
    catalogue = TransactionCatalogue.from_transactions((es_row, foreign_row))

    aggregation = aggregate_impatriado_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)
    resolved = resolve_ledger_impatriado_income_aggregation_binding_values(revision, aggregation.observations)

    binding_id: BindingId = "modelo-151-impatriado-base-liquidable-general"
    assert resolved[binding_id] == Decimal("120000.00")


def test_registry_binding_definition_validates_and_rejects_wrong_casilla() -> None:
    """The build-time validator accepts the shipped binding and rejects an off-target one."""
    revision = load_modelo_directory(_M151_REGISTRY_DIR).revisions["2015-y-siguientes"]
    binding = next(b for b in revision.bindings if b.id == "modelo-151-impatriado-base-liquidable-general")
    # Shipped binding validates.
    validate_ledger_impatriado_income_aggregation_binding_definition(binding)

    # A binding targeting a non-base casilla is rejected (anti-tautology: the
    # validator is not vacuously passing).
    off_target = binding.model_copy(
        update={
            "selector": {
                "modelo": "151",
                "target_casilla_id": "impatriado.retenciones",
                "fact": "ingresos_integros_sum",
            },
        },
    )
    with pytest.raises(RegistryValidationError, match="outside the supported"):
        validate_ledger_impatriado_income_aggregation_binding_definition(off_target)
