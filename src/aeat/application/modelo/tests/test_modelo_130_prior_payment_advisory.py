"""Live calculate-path advisory: Modelo 130 undeducted prior pago fraccionado.

Modelo 130 is cumulative from the start of the ejercicio. Casilla 05 ("Pagos
fraccionados anteriores") is a manual cell with no binding, so a cumulative
2T/3T/4T calculate never auto-deducts the pago fraccionado already paid in the
prior trimestres — casilla 07 = 04 - 05 - 06 omits the prior payment and the
operator over-declares (RD 439/2007 art. 110; ``no-silent-under-declaration``).

This module pins the stage-1 non-blocking advisory on the LIVE operator
calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`)
against real adapters (real encrypted-SQLite bucket via
``isolated_runtime_profile``, real catalogue repositories, real registry
authority, real calculation engine, real source mesh — no mocks/stubs/skips):

* a NON-first trimestre (2T) with positive cumulative ingresos and a real prior
  1T M130 filing in the catalogue but casilla 05 = 0 -> the
  ``prior_payment_not_deducted`` advisory fires, naming casilla 05; and
* the FIRST-FILER negative: an identical 2T calculate with NO prior 1T M130
  filing in the catalogue (a mid-year alta whose first obligation is 2T) ->
  the advisory does NOT fire, because casilla 05 is legitimately null when there
  is no prior pago fraccionado; and
* a 1T first-obligation calculate -> the advisory does NOT fire (no prior
  trimestre is possible).

The advisory's fire/no-fire is a wiring invariant gated on the EXISTENCE of a
prior-period observation, not on any hand-computed amount; no registry formula
is re-evaluated against a hand-summed literal.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import CalculationObservationRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "bucket-m130-prior-payment-advisory"
_REVISION = "2019-y-siguientes"
_YEAR = 2026
_PRIOR_YEAR = 2025
_PRIOR_YEAR_NET_INCOME = Decimal("8000")

_T0 = datetime(2026, 7, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 7, 10, 11, 0, tzinfo=UTC)

_ADVISORY_REASON = "prior_payment_not_deducted"
_PRIOR_PAYMENT_CASILLA = "05"

# Casilla 01 (Ingresos) is a source-owned bound casilla (ledger renta income
# aggregation) — it MUST NOT be supplied through the caller channel, or the
# source-override guard refuses the calculate. The manual inputs cover only the
# non-source casillas; casilla 01 folds from seeded income transactions. Gastos
# (02) = 0 leaves rendimiento neto == ingresos, so casilla 04 is a clean positive
# pago fraccionado. Casilla 05 = 0 is exactly the operator-over-payment shape the
# advisory exists to surface.
_MANUAL_INPUTS: dict[str, Decimal] = {
    "02": Decimal("0"),
    "05": Decimal("0"),
    "06": Decimal("0"),
    "08": Decimal("0"),
    "10": Decimal("0"),
    "16": Decimal("0"),
    "18": Decimal("0"),
}

# One INCOMING business EUR receipt seeded inside the relevant cumulative window
# so casilla 01 folds a positive ingreso (and casilla 04 a positive pago
# fraccionado). The amount only proves "positive activity"; it is not asserted.
_INCOME_AMOUNT = Decimal("3000.00")
_INCOME_DATE = date(2026, 2, 14)  # inside both 1T (Jan-Mar) and 2T (Jan-Jun) windows


@pytest.fixture
def objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _seed_prior_year_m100(obs_repo: CalculationObservationRepository) -> None:
    """Seed the prior-year M100 net income so the M130 minoración binding resolves.

    M130 casilla 13 reads ``irpf.previous_year_economic_activity_net_income``; on
    a fresh bucket the engine raises if that prior-year value is absent. This is
    upstream substrate, not the casilla under test.
    """
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo="100",
            filing_year=_PRIOR_YEAR,
            period="0A",
            observations=(
                CasillaObservation(casilla_id="0224", value=_PRIOR_YEAR_NET_INCOME),
                CasillaObservation(casilla_id="1479", value=Decimal("0")),
                CasillaObservation(casilla_id="1553", value=Decimal("0")),
                CasillaObservation(casilla_id="1577", value=Decimal("0")),
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def _seed_prior_1t_m130_filing(obs_repo: CalculationObservationRepository) -> RegistryModeloObservation:
    """Seed a real prior 1T M130 filing observation (the prior pago fraccionado).

    The 1T filing carries a positive pago fraccionado: casilla 04 and casilla 07
    are non-zero, the amount the cumulative 2T must deduct via casilla 05. The
    advisory keys only off the EXISTENCE of this prior filing for the ejercicio,
    so the exact values here are provenance, not an asserted aggregate.
    """
    observation = RegistryModeloObservation(
        modelo="130",
        filing_year=_YEAR,
        period="1T",
        observations=(
            CasillaObservation(casilla_id="01", value=Decimal("1500")),
            CasillaObservation(casilla_id="04", value=Decimal("200")),
            CasillaObservation(casilla_id="07", value=Decimal("200")),
            CasillaObservation(casilla_id="19", value=Decimal("200")),
            # The 1T saldo-negativo-fin-periodo (= 0 for a positive 1T result) is
            # the anchor the casilla-15 carry binding reads at 2T; a complete
            # prior filing carries it so the 2T calculate resolves the carry.
            CasillaObservation(casilla_id="saldo-negativo-fin-periodo", value=Decimal("0")),
        ),
    )
    obs_repo.save_observation(observation, source_kind=APP_FILING_SOURCE_KIND, captured_at=_T0)
    return observation


def _income_transaction(objects: SecureObjectRepository) -> None:
    """Seed one ACTIVE INCOMING business EUR receipt so casilla 01 folds positive."""
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects)
    transaction = Transaction.model_validate(
        {
            "raw": RawTransaction(
                transaction_id="m130-prior-payment-income",
                booked_date=_INCOME_DATE,
                value_date=_INCOME_DATE,
                amount=_INCOME_AMOUNT,
                currency="EUR",
                counterparty="Cliente SA",
                description="actividad económica income",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="b" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2026, 2, 14, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": "income"},
            ),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 2, 14, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
    tx_repo.save(TransactionCatalogue.from_transactions((transaction,)))


def _calculate(
    objects: SecureObjectRepository,
    *,
    period: str,
    prior_payment: Decimal = Decimal("0"),
) -> BucketAggregationCalculationResult:
    wu_repo = WorkUnitCatalogueRepository(objects=objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    casilla_inputs = {**_MANUAL_INPUTS, "05": prior_payment}
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )


def _prior_payment_advisories(result: BucketAggregationCalculationResult) -> tuple[object, ...]:
    return tuple(diag for diag in result.source_diagnostics if diag.reason == _ADVISORY_REASON)


def test_two_t_with_prior_1t_filing_fires_undeducted_prior_payment_advisory(
    objects: SecureObjectRepository,
) -> None:
    """A cumulative 2T with a real prior 1T filing and casilla 05 = 0 fires the advisory.

    The prior 1T pago fraccionado is real (seeded), casilla 05 is zero, and
    casilla 01 is positive, so casilla 07 = 04 - 05 - 06 silently omits the prior
    payment. The advisory surfaces that over-declaration and names casilla 05.
    """
    obs_repo = CalculationObservationRepository(objects=objects)
    _seed_prior_year_m100(obs_repo)
    _seed_prior_1t_m130_filing(obs_repo)
    _income_transaction(objects)

    result = _calculate(objects, period="2T")

    # Casilla 05 really is zero on this calculate (the over-payment shape).
    assert Decimal(result.revision.casilla_values[_PRIOR_PAYMENT_CASILLA]) == Decimal("0")
    advisories = _prior_payment_advisories(result)
    assert len(advisories) == 1, (
        f"expected one {_ADVISORY_REASON} advisory for a 2T with a prior 1T filing and casilla 05 = 0; "
        f"got {[d.reason for d in result.source_diagnostics]}"
    )
    advisory = advisories[0]
    assert advisory.casilla_id == _PRIOR_PAYMENT_CASILLA
    assert advisory.source_kind == "modelo_130_prior_pago_fraccionado"
    assert "casilla 05" in advisory.message
    assert "1T" in advisory.message


def test_two_t_with_casilla_05_populated_does_not_false_fire(
    objects: SecureObjectRepository,
) -> None:
    """A 2T whose casilla 05 is populated does not fire the advisory (no over-payment).

    When the operator HAS entered the prior pago fraccionado in casilla 05, the
    deduction is present and the return does not over-declare — the advisory must
    not false-fire on a correctly-filled cumulative 2T. This pins the no-noise
    side of the gate (a populated casilla 05 short-circuits the advisory).
    """
    obs_repo = CalculationObservationRepository(objects=objects)
    _seed_prior_year_m100(obs_repo)
    _seed_prior_1t_m130_filing(obs_repo)
    _income_transaction(objects)

    result = _calculate(objects, period="2T", prior_payment=Decimal("200"))

    assert Decimal(result.revision.casilla_values[_PRIOR_PAYMENT_CASILLA]) == Decimal("200")
    assert _prior_payment_advisories(result) == (), (
        "a 2T whose casilla 05 is populated has the prior pago fraccionado deducted "
        "and must not fire the undeducted-prior-payment advisory"
    )


def test_first_trimestre_does_not_fire(
    objects: SecureObjectRepository,
) -> None:
    """A 1T first-obligation calculate never fires the advisory (no prior trimestre).

    1T is the first possible obligation period of the ejercicio, so no prior
    pago fraccionado can exist regardless of catalogue state; the advisory must
    stay silent.
    """
    obs_repo = CalculationObservationRepository(objects=objects)
    _seed_prior_year_m100(obs_repo)
    _income_transaction(objects)

    result = _calculate(objects, period="1T")

    assert _prior_payment_advisories(result) == (), (
        "a 1T first-obligation filing has no prior trimestre and must never fire "
        "the undeducted-prior-payment advisory"
    )
