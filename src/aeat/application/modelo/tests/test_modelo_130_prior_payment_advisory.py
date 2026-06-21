"""Live calculate-path advisory degradation: Modelo 130 prior pago fraccionado.

Modelo 130 is cumulative from the start of the ejercicio. Stage 2 flips casilla 05
("Pagos fraccionados anteriores") from a manual cell to a bound carry that computes
``Σ max(0, prior 07_q) − Σ prior 16_q`` over the same-ejercicio prior trimestres,
so a cumulative 2T/3T/4T calculate now auto-deducts the prior pago fraccionado.

This module pins the post-Stage-2 advisory behaviour on the LIVE operator
calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`)
against real adapters (real encrypted-SQLite bucket via
``isolated_runtime_profile``, real catalogue repositories, real registry
authority, real calculation engine, real source mesh — no mocks/stubs/skips):

* a NON-first trimestre (2T) with a real prior 1T M130 filing -> the casilla-05
  carry populates the deduction (casilla 05 = the carried prior pago
  fraccionado), so the ``prior_payment_not_deducted`` over-payment advisory
  DEGRADES and stays silent (the carry resolved cleanly); and
* the same 2T whose prior 1T filing carries casilla 07 but NO casilla-16 entry
  ("not captured", distinct from "filed 0") -> the carry proceeds treating the
  absent minoración as zero, but the ``prior_payment_minoracion_not_captured``
  advisory fires naming the gap (``no-silent-under-declaration``); and
* a prior 1T filing that declares casilla 16 explicitly (even 0) -> the carry
  resolves cleanly and NEITHER advisory fires; and
* a 1T first-obligation calculate -> no advisory (no prior trimestre is
  possible).

The carry value is asserted against the seeded prior-filing inputs via an
independent identity (Σ max(0, 07) − Σ 16), a different code path than the span
binding; the advisory fire/no-fire is a wiring invariant gated on the existence
and casilla-16 presence of a prior-period observation.
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
from ...aggregation import CalculationSourceDiagnostic
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
_MINORACION_ADVISORY_REASON = "prior_payment_minoracion_not_captured"
_PRIOR_PAYMENT_CASILLA = "05"

# The prior 1T pago fraccionado the casilla-05 carry deducts at 2T.
_PRIOR_1T_CASILLA_07 = Decimal("200")

# Casilla 01 (Ingresos) is a source-owned bound casilla (ledger renta income
# aggregation) — it MUST NOT be supplied through the caller channel, or the
# source-override guard refuses the calculate. Casilla 02 (Gastos) is likewise a
# source-owned bound casilla now (ledger renta gasto aggregation): with no expense
# transactions seeded its resolver returns 0, leaving rendimiento neto == ingresos
# so casilla 04 is a clean positive pago fraccionado. Casilla 05 (Pagos
# fraccionados anteriores) is a BOUND carry (Stage 2) and likewise must not be
# supplied. The manual inputs cover only the remaining non-source casillas;
# casilla 01 folds from seeded income transactions.
_MANUAL_INPUTS: dict[str, Decimal] = {
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


def _seed_prior_1t_m130_filing(
    obs_repo: CalculationObservationRepository,
    *,
    minoracion: Decimal | None = None,
) -> RegistryModeloObservation:
    """Seed a real prior 1T M130 filing observation (the prior pago fraccionado).

    The 1T filing carries a positive pago fraccionado: casilla 04 and casilla 07
    are non-zero, the amount the cumulative 2T deducts via the casilla-05 carry.

    ``minoracion`` controls the casilla-16 entry:

    * ``None`` (default) -> NO casilla-16 entry is stored. This is the
      "not captured" shape: the carry proceeds treating the absent minoración as
      zero and the not-captured advisory fires.
    * a ``Decimal`` -> casilla 16 is stored with that value (the "filed" shape;
      ``Decimal('0')`` is filed-zero, a silent no-op).
    """
    casillas = [
        CasillaObservation(casilla_id="01", value=Decimal("1500")),
        CasillaObservation(casilla_id="04", value=_PRIOR_1T_CASILLA_07),
        CasillaObservation(casilla_id="07", value=_PRIOR_1T_CASILLA_07),
        CasillaObservation(casilla_id="19", value=_PRIOR_1T_CASILLA_07),
        # The 1T saldo-negativo-fin-periodo (= 0 for a positive 1T result) is
        # the anchor the casilla-15 carry binding reads at 2T; a complete
        # prior filing carries it so the 2T calculate resolves the carry.
        CasillaObservation(casilla_id="saldo-negativo-fin-periodo", value=Decimal("0")),
    ]
    if minoracion is not None:
        casillas.append(CasillaObservation(casilla_id="16", value=minoracion))
    observation = RegistryModeloObservation(
        modelo="130",
        filing_year=_YEAR,
        period="1T",
        observations=tuple(casillas),
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
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        casilla_inputs=dict(_MANUAL_INPUTS),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )


def _prior_payment_advisories(result: BucketAggregationCalculationResult) -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(diag for diag in result.source_diagnostics if diag.reason == _ADVISORY_REASON)


def _minoracion_advisories(result: BucketAggregationCalculationResult) -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(diag for diag in result.source_diagnostics if diag.reason == _MINORACION_ADVISORY_REASON)


def test_two_t_carry_populates_casilla_05_and_degrades_overpayment_advisory(
    objects: SecureObjectRepository,
) -> None:
    """A cumulative 2T with a prior 1T filing auto-carries casilla 05; the over-payment advisory degrades.

    Stage 2: casilla 05 is now a bound carry. With a real prior 1T filing carrying
    casilla 07 = 200, the carry populates casilla 05 = 200 (the prior pago
    fraccionado), so casilla 07 = 04 - 05 - 06 correctly deducts it. The Stage-1
    ``prior_payment_not_deducted`` over-payment advisory therefore DEGRADES and
    stays silent - it now fires only when the carry genuinely could not populate.
    The prior 1T here LACKS casilla 16, so the not-captured minoración
    advisory fires instead, proving the minoración is never silently
    dropped. The carried casilla 05 is asserted against the AEAT identity
    Σ max(0, 07) − Σ 16 = max(0, 200) − 0 = 200, computed independently.
    """
    obs_repo = CalculationObservationRepository(objects=objects)
    _seed_prior_year_m100(obs_repo)
    _seed_prior_1t_m130_filing(obs_repo)  # no casilla-16 entry -> not captured
    _income_transaction(objects)

    result = _calculate(objects, period="2T")

    # Independent identity: Σ max(0, prior 07) − Σ prior 16 = max(0, 200) − 0 = 200.
    expected_casilla_05 = max(Decimal("0"), _PRIOR_1T_CASILLA_07) - Decimal("0")
    assert Decimal(result.revision.casilla_values[_PRIOR_PAYMENT_CASILLA]) == expected_casilla_05

    # The over-payment advisory degrades: the carry resolved casilla 05 cleanly.
    assert _prior_payment_advisories(result) == (), (
        "the casilla-05 carry populated the deduction, so the prior_payment_not_deducted "
        f"over-payment advisory must stay silent; got {[d.reason for d in result.source_diagnostics]}"
    )

    # The minoración not-captured advisory fires: the prior 1T carries casilla 07
    # but no casilla-16 entry, so the carry's minoración term defaulted to zero.
    minoracion = _minoracion_advisories(result)
    assert len(minoracion) == 1, (
        f"expected one {_MINORACION_ADVISORY_REASON} advisory for a prior 1T filing with no casilla-16 "
        f"entry; got {[d.reason for d in result.source_diagnostics]}"
    )
    advisory = minoracion[0]
    assert advisory.casilla_id == _PRIOR_PAYMENT_CASILLA
    assert advisory.source_kind == "modelo_130_prior_pago_fraccionado"
    assert "casilla 16" in advisory.message
    assert "1T" in advisory.message


def test_two_t_with_prior_filing_carrying_casilla_16_fires_no_advisory(
    objects: SecureObjectRepository,
) -> None:
    """A 2T whose prior 1T filing declares casilla 16 explicitly fires NEITHER advisory.

    When the prior 1T filing carries an explicit casilla-16 entry (filed-zero is a
    captured value, not a gap), the carry resolves casilla 05 cleanly and both the
    over-payment advisory (degraded - the carry populated the deduction) and the
    not-captured minoración advisory (the minoración WAS captured) stay silent.
    This is the no-noise side of the gate.
    """
    obs_repo = CalculationObservationRepository(objects=objects)
    _seed_prior_year_m100(obs_repo)
    _seed_prior_1t_m130_filing(obs_repo, minoracion=Decimal("0"))  # filed-zero is captured
    _income_transaction(objects)

    result = _calculate(objects, period="2T")

    # Σ max(0, 200) − Σ 0 = 200, the carry resolves cleanly.
    assert Decimal(result.revision.casilla_values[_PRIOR_PAYMENT_CASILLA]) == Decimal("200")
    assert _prior_payment_advisories(result) == (), (
        "the casilla-05 carry populated the deduction; the over-payment advisory must stay silent"
    )
    assert _minoracion_advisories(result) == (), (
        "the prior filing declared casilla 16 explicitly (filed-zero is captured), so the "
        "not-captured minoración advisory must stay silent"
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
        "a 1T first-obligation filing has no prior trimestre and must never fire the undeducted-prior-payment advisory"
    )
