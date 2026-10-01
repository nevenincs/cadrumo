"""M303 special-case IVA casilla routing — reverse-charge double-entry + recargo anomaly.

Verification fences for the special-case IvaCategory -> Modelo 303 casilla routing
(P05 still-open, reachable after the #50 calculate unblock). Each test drives the
REAL registry engine (``calculate_registry_snapshot``) or the REAL aggregation
classifier — no mocks — and reds if the routing regresses.

Covered:

- INTRACOM ACQUISITION REVERSE CHARGE (LIVA art. 84.Uno.2 + art. 92): the
  self-assessed cuota of an intra-community acquisition is accrued (it feeds
  ``iva.cuota-devengada-total``, box [27], and box [11]) AND deductible: box [37]
  ("En adquisiciones intracomunitarias de bienes y servicios corrientes", base
  [36]) carries it into ``iva.cuota-deducible-total``, box [45]. The two legs net
  to zero in ``iva.resultado-regimen-general`` for a fully-deductible acquisition,
  the correct reverse-charge double-entry. The binding values come from the real
  IVA ledger aggregation of one classified acquisition, so the engine receives
  exactly the bindings such a ledger row reaches.

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
The AEAT diseno de registro of Modelo 303 for ejercicio 2025 prints box [45] as
"Total a deducir ( [29] + [31] + [33] + [35] + [37] + [39] + [41] + [42] + [43] +
[44] )" and box [37] as the cuota deducible "En adquisiciones intracomunitarias de
bienes y servicios corrientes". The worked first-quarter liquidation in the AEAT
Manual practico IVA 2025 (capitulo 9) counts the same 4.410 euros of
adquisiciones intracomunitarias in both TOTAL CUOTA DEVENGADA and TOTAL A DEDUCIR.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...aggregation.iva_ledger import (
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations,
    resolve_iva_ledger_binding_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR = 2025
_PERIOD = "1T"

#: The engine bindings the M303 régimen-general result drives off, each supplied
#: as zero unless the aggregated reverse-charge acquisition reaches it.
_LEDGER_CUOTA_BINDINGS = (
    "modelo-303-iva-repercutido-general-cuota",
    "modelo-303-iva-repercutido-reducido-cuota",
    "modelo-303-iva-repercutido-super-reducido-cuota",
    "modelo-303-iva-soportado-interiores-cuota",
    "modelo-303-iva-soportado-importaciones-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-cuota",
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
_M303_BOX_11_CASILLA: CasillaId = validated_casilla_id("11")
_M303_BOX_37_CASILLA: CasillaId = validated_casilla_id("37")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")


def _intracom_acquisition(*, base: Decimal, cuota: Decimal) -> Transaction:
    """An intra-community acquisition of current goods, self-assessed and fully deductible."""
    from ....domain.transactions.models import derive_transaction_id

    raw = RawTransaction(
        provider_transaction_id="intracom-acquisition-001",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=base,
        currency="EUR",
        counterparty="Proveedor UE GmbH",
        description="Adquisicion intracomunitaria de mercaderia",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2025, 2, 10, 10, 0, tzinfo=UTC),
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
        iva_category=IvaCategory("intra_community_acquisition_reverse_charge"),
        taxable_base=base,
        iva_rate=Decimal("0.21"),
        iva_amount=cuota,
        deduction_fact_kind=IvaDeductionFactKind.from_registry("intra_eu_current"),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment"),
            source_locator="fixture:intracom-acquisition-001",
            evidence_digest="d" * 64,
        ),
    )


def _calculate_intracom_acquisition(*, base: Decimal, cuota: Decimal) -> dict[CasillaId, Decimal]:
    """Aggregate one acquisition through the real IVA ledger and calculate the M303 snapshot."""
    snapshot = published_snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD)
    with _indexed_authority_for_test().operation() as operation:
        report = aggregate_iva_ledger_observations(
            TransactionCatalogue.from_transactions((_intracom_acquisition(base=base, cuota=cuota),)),
            period=Period.from_year_and_code(_YEAR, _PERIOD),
            ledger_profile_id="m303-special-test",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="m303-special-test",
            operation=operation,
        )
        ledger_values = resolve_iva_ledger_binding_values(snapshot.revision, report.observations, operation=operation)
    binding_values = {
        _AUTOCONSUMO_BINDING: Decimal("0"),
        _STATE_RATIO_BINDING: Decimal("100"),
        _PRIOR_COMPENSATION_BINDING: Decimal("0"),
        **{b: Decimal("0") for b in _LEDGER_CUOTA_BINDINGS},
        **ledger_values,
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(_YEAR, 12, 31)},
    )
    return dict(result.values)


def test_intracom_acquisition_self_assesses_and_deducts_the_same_cuota() -> None:
    """A reverse-charge intracom cuota feeds BOTH devengada-total AND deducible-total.

    LIVA art. 84.Uno.2 makes the acquirer the sujeto pasivo (output IVA, devengada);
    art. 92 makes that same self-assessed cuota deductible. The accrued leg reaches
    box [27] through ``iva.autorepercutido.intracomunitaria`` and box [11]; the
    deductible leg reaches box [37], one of the ten summands of box [45]. A
    fully-deductible acquisition therefore nets to a zero régimen-general result,
    box [46] = [27] - [45]. Reds if either leg drops the intracom cuota.
    """
    intracom_cuota = Decimal("42.00")
    values = _calculate_intracom_acquisition(base=Decimal("200.00"), cuota=intracom_cuota)

    # The intracom cuota self-assesses as output IVA (devengada leg, art. 84)...
    assert values[_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_CASILLA] == intracom_cuota
    assert values[_M303_BOX_11_CASILLA] == intracom_cuota
    assert values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA] == intracom_cuota
    # ...AND is deductible by the same amount through box [37] (deducible leg, art. 92).
    assert values[_M303_BOX_37_CASILLA] == intracom_cuota
    assert values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA] == intracom_cuota
    # The reverse-charge double-entry nets to zero régimen-general result.
    assert values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA] == Decimal("0.00")


def test_intracom_cuota_is_not_silently_dropped_from_deducible() -> None:
    """Anti-tautology: a NON-zero intracom cuota must move the deducible-total off zero.

    If box [45] ever dropped box [37], or the acquisition stopped reaching box [37],
    this would show deducible-total == 0 while devengada-total == 42 (output IVA
    with no offset), a net positive result that over-states the IVA payable on a
    neutral acquisition.
    """
    values = _calculate_intracom_acquisition(base=Decimal("200.00"), cuota=Decimal("42.00"))

    assert values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA] > Decimal("0"), (
        "intracom autorepercutido cuota was dropped from the deducible total — "
        "reverse-charge acquisition would over-state IVA payable"
    )
    assert values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA] == values[_M303_BOX_37_CASILLA]


def _recargo_purchase() -> Transaction:
    """A recargo-equivalencia retailer purchase: input IVA + RE surcharge, non-deductible."""
    from ....domain.transactions.models import derive_transaction_id

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
        iva_category=IvaCategory("recargo_equivalencia"),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )


def test_recargo_equivalencia_is_surfaced_not_silently_deducted() -> None:
    """A recargo-equivalencia purchase is surfaced as non-declarable, never silently deducted.

    LIVA arts. 148-163: the recargo-equivalencia retailer does not deduct input IVA
    (the IVA + RE surcharge is non-deductible acquisition cost). The aggregation
    classifier must NOT silently bucket it into the M303 soportado/deducible leg; it
    surfaces an explicit UNSUPPORTED_IVA_CATEGORY issue so the operator sees the
    anomaly. Reds if the category ever produces a silent declarable deducible
    observation.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        report = aggregate_iva_ledger_observations(
            TransactionCatalogue.from_transactions((_recargo_purchase(),)),
            period=Period.from_year_and_code(_YEAR, _PERIOD),
            ledger_profile_id="m303-special-test",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="m303-special-test",
            operation=_authority_operation_for_test,
        )

        # No declarable deducible observation was _produced for the recargo purchase...
        assert all(obs.category != IvaCategory("recargo_equivalencia") for obs in report.observations), (
            "recargo-equivalencia must not yield a declarable IVA observation (non-deductible cost)"
        )
        # ...and the exclusion is SURFACED (non-silent) with the unsupported-category reason.
        assert any(
            issue.reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_CATEGORY for issue in report.issues
        ), "recargo-equivalencia exclusion must be surfaced as an UNSUPPORTED_IVA_CATEGORY issue, not silent"
