"""M303 special-case IVA casilla routing — reverse-charge double-entry + recargo anomaly.

Verification fences for the special-case IvaCategory -> Modelo 303 casilla routing
(P05 still-open, reachable after the #50 calculate unblock). Each test drives the
REAL registry engine (``calculate_registry_snapshot``) or the REAL aggregation
classifier — no mocks — and reds if the routing regresses.

Covered:

- INTRACOM ACQUISITION REVERSE CHARGE (LIVA art. 84.Uno.2 + art. 92): a single
  ``iva.autorepercutido.intracomunitaria`` cuota self-assesses output IVA (it
  feeds ``iva.cuota-devengada-total``) AND is simultaneously deductible (it feeds
  ``iva.cuota-deducible-total``). The two legs net to zero in
  ``iva.resultado-regimen-general`` for a fully-deductible acquisition — the
  correct reverse-charge double-entry. This is the routing the foreign persona
  could not reach behind the B1/B3 wall.

- RECARGO DE EQUIVALENCIA ANOMALY (LIVA arts. 148-163): a recargo-equivalencia
  retailer's input IVA is NON-deductible acquisition cost, so it must NOT silently
  feed the M303 soportado/deducible bucket. The aggregation classifier SURFACES it
  as an explicit ``UNSUPPORTED_IVA_CATEGORY`` issue (non-silent), never a silent
  mis-bucket into a normal deduction.

The domestic-reverse-charge routing gap surfaced during this verification is
reported separately; export and export-assimilated base rows are current Modelo 303
ledger bindings.

Legal grounding: LIVA (Ley 37/1992) art. 84.Uno.2 (inversion del sujeto pasivo en
adquisiciones intracomunitarias), art. 92 (cuotas deducibles), arts. 148-163
(regimen especial del recargo de equivalencia); Orden EHA/3786/2008 (M303 form).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot

from ....core import CasillaId, Period, validated_casilla_id
from ....domain.bienes_inversion import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.iva import (
    IvaCategory,
)
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR = 2025
_PERIOD = "1T"

#: The single intracom autorepercutido cuota leg + the engine bindings the M303
#: régimen-general result drives off (each supplied as zero unless named below).
_INTRACOM_BINDING = "modelo-303-iva-autorepercutido-intracomunitaria-cuota"
_LEDGER_CUOTA_BINDINGS = (
    "modelo-303-iva-repercutido-general-cuota",
    "modelo-303-iva-repercutido-reducido-cuota",
    "modelo-303-iva-repercutido-super-reducido-cuota",
    "modelo-303-iva-soportado-interiores-cuota",
    "modelo-303-iva-soportado-importaciones-cuota",
    _INTRACOM_BINDING,
    "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base",
    "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota",
    "modelo-303-iva-autorepercutido-interior-devengado-cuota",
    "modelo-303-iva-autorepercutido-interior-deducible-cuota",
    "modelo-303-casilla-59-entregas-intracomunitarias-base",
    "modelo-303-casilla-60-exportaciones-base",
    "modelo-303-casilla-120-no-sujetas-localizacion-base",
    "modelo-303-casilla-122-inversion-sujeto-pasivo-base",
    "modelo-303-iva-repercutido-general-base",
    "modelo-303-iva-repercutido-reducido-base",
    "modelo-303-iva-repercutido-super-reducido-base",
    "modelo-303-iva-soportado-interiores-base",
    "modelo-303-recargo-equivalencia-general-cuota",
    "modelo-303-recargo-equivalencia-reducido-cuota",
    "modelo-303-recargo-equivalencia-super-reducido-cuota",
    # Criterio-de-caja informational bindings (LIVA arts. 163 decies ff.) for
    # casillas 62/63/74/75; zero when the fixture has no cash-accounting rows.
    "modelo-303-criterio-caja-entregas-art75-base",
    "modelo-303-criterio-caja-entregas-art75-cuota",
    "modelo-303-criterio-caja-adquisiciones-base",
    "modelo-303-criterio-caja-adquisiciones-cuota",
)
_AUTOCONSUMO_BINDING = "modelo-303-autoconsumo-promotor-base"
_STATE_RATIO_BINDING = "modelo-303-profile-state-attribution-ratio"
#: Casilla 110 is a bound casilla the engine always requires a fact for; supplied
#: as zero (no prior-period carry) so the régimen-general result isolates the
#: intracom double-entry under test.
_PRIOR_COMPENSATION_BINDING = "modelo-303-compensacion-pendiente-anteriores"


_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_CASILLA: CasillaId = validated_casilla_id("iva.autorepercutido.intracomunitaria")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")


def test_intracom_acquisition_self_assesses_and_deducts_the_same_cuota(tmp_path: Path) -> None:
    """A reverse-charge intracom cuota feeds BOTH devengada-total AND deducible-total.

    LIVA art. 84.Uno.2 makes the acquirer the sujeto pasivo (output IVA, devengada);
    art. 92 makes that same self-assessed cuota deductible. The M303 engine wires the
    single ``iva.autorepercutido.intracomunitaria`` casilla into both totals, so a
    fully-deductible acquisition nets to zero régimen-general result. Reds if either
    leg drops the intracom casilla.
    """
    intracom_cuota = Decimal("42.00")
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = bundled_authority().snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD)
        binding_values = {
            _INTRACOM_BINDING: intracom_cuota,
            _AUTOCONSUMO_BINDING: Decimal("0"),
            _STATE_RATIO_BINDING: Decimal("100"),
            _PRIOR_COMPENSATION_BINDING: Decimal("0"),
            **{b: Decimal("0") for b in _LEDGER_CUOTA_BINDINGS if b != _INTRACOM_BINDING},
        }
        inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            binding_values=binding_values,
            date_context={"filing_period": date(_YEAR, 12, 31)},
        )

    # The intracom cuota self-assesses as output IVA (devengada leg, art. 84)...
    assert result.values[_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_CASILLA] == intracom_cuota
    assert result.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA] == intracom_cuota
    # ...AND is deductible by the same amount (deducible leg, art. 92).
    assert result.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA] == intracom_cuota
    # The reverse-charge double-entry nets to zero régimen-general result.
    assert result.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA] == Decimal("0.00")


def test_intracom_cuota_is_not_silently_dropped_from_deducible(tmp_path: Path) -> None:
    """Anti-tautology: a NON-zero intracom cuota must move the deducible-total off zero.

    If the deducible-total formula ever dropped the autorepercutido leg, this would
    show deducible-total == 0 while devengada-total == 42 (output IVA with no offset)
    — a net positive result that over-states the IVA payable on a neutral acquisition.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = bundled_authority().snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD)
        binding_values = {
            _INTRACOM_BINDING: Decimal("42.00"),
            _AUTOCONSUMO_BINDING: Decimal("0"),
            _STATE_RATIO_BINDING: Decimal("100"),
            _PRIOR_COMPENSATION_BINDING: Decimal("0"),
            **{b: Decimal("0") for b in _LEDGER_CUOTA_BINDINGS if b != _INTRACOM_BINDING},
        }
        inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            binding_values=binding_values,
            date_context={"filing_period": date(_YEAR, 12, 31)},
        )
    assert result.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA] > Decimal("0"), (
        "intracom autorepercutido cuota was dropped from the deducible total — "
        "reverse-charge acquisition would over-state IVA payable"
    )


def _recargo_purchase() -> Transaction:
    """A recargo-equivalencia retailer purchase: input IVA + RE surcharge, non-deductible."""
    from ....domain.transactions import derive_transaction_id

    raw = RawTransaction(
        provider_transaction_id="recargo-purchase-001",
        booked_date=date(2025, 2, 1),
        value_date=date(2025, 2, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Mayorista SL",
        description="Compra mercaderia (recargo de equivalencia)",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2025, 2, 1, 10, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )
    return Transaction(
        transaction_id=derive_transaction_id(raw),
        raw=raw,
        direction=TransactionDirection.OUTGOING,
        group_label=None,
        business_classification=BusinessClassification.BUSINESS,
        source_jurisdiction="ES",
        iva_category=IvaCategory.RECARGO_EQUIVALENCIA,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )


def test_recargo_equivalencia_is_surfaced_not_silently_deducted(tmp_path: Path) -> None:
    """A recargo-equivalencia purchase is surfaced as non-declarable, never silently deducted.

    LIVA arts. 148-163: the recargo-equivalencia retailer does not deduct input IVA
    (the IVA + RE surcharge is non-deductible acquisition cost). The aggregation
    classifier must NOT silently bucket it into the M303 soportado/deducible leg; it
    surfaces an explicit UNSUPPORTED_IVA_CATEGORY issue so the operator sees the
    anomaly. Reds if the category ever produces a silent declarable deducible
    observation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        report = aggregate_iva_ledger_observations(
            TransactionCatalogue.from_transactions((_recargo_purchase(),)),
            period=Period.from_year_and_code(_YEAR, _PERIOD),
            ledger_profile_id="m303-special-test",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="m303-special-test",
        )

    # No declarable deducible observation was produced for the recargo purchase...
    assert all(obs.category is not IvaCategory.RECARGO_EQUIVALENCIA for obs in report.observations), (
        "recargo-equivalencia must not yield a declarable IVA observation (non-deductible cost)"
    )
    # ...and the exclusion is SURFACED (non-silent) with the unsupported-category reason.
    assert any(issue.reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_CATEGORY for issue in report.issues), (
        "recargo-equivalencia exclusion must be surfaced as an UNSUPPORTED_IVA_CATEGORY issue, not silent"
    )
