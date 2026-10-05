"""M303 special-case IVA casilla routing — reverse-charge double-entry + recargo anomaly.

Verification fences for the special-case IvaCategory -> Modelo 303 casilla routing
(P05 still-open, reachable after the #50 calculate unblock). Each test drives the
REAL registry engine (``calculate_registry_snapshot``) or the REAL aggregation
classifier — no mocks — and reds if the routing regresses.

Covered:

- INTRACOM ACQUISITION REVERSE CHARGE (LIVA art. 84.Uno.2 + art. 92): one
  classified intra-community acquisition row self-assesses output IVA (its cuota
  feeds ``iva.cuota-devengada-total`` through
  ``iva.autorepercutido.intracomunitaria``) AND is simultaneously deductible (the
  same cuota reaches box [37] and through it ``iva.cuota-deducible-total``, which
  the diseño de registro states as [29] + [31] + [33] + [35] + [37] + [39] + [41]
  + [42] + [43] + [44]). The two legs net to zero in
  ``iva.resultado-regimen-general`` for a fully-deductible acquisition — the
  correct reverse-charge double-entry. The row goes through the real ledger
  aggregation and the published ``ledger_iva_aggregation`` bindings, so both legs
  come from one ledger fact rather than from hand-picked binding values.

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

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue, derive_transaction_id
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
_PROFILE_ID = "m303-special-test"

#: The profile's state attribution ratio (100 % common territory). Every other
#: binding the ledger does not carry -- prior-period compensación, operator
#: inputs, regularisations -- is supplied as zero so the régimen-general result
#: isolates the intracom double-entry under test.
_STATE_RATIO_BINDING: BindingId = "modelo-303-profile-state-attribution-ratio"

#: 200.00 of base at 21 % self-assesses 42.00 of cuota.
_INTRACOM_BASE = Decimal("200.00")
_INTRACOM_CUOTA = Decimal("42.00")

_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_CASILLA: CasillaId = validated_casilla_id("iva.autorepercutido.intracomunitaria")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_M303_BOX_11_CASILLA: CasillaId = validated_casilla_id("11")
_M303_BOX_37_CASILLA: CasillaId = validated_casilla_id("37")


def _intracom_acquisition() -> Transaction:
    """One intra-community goods acquisition from Germany, classified as a current deduction."""
    raw = RawTransaction(
        provider_transaction_id="intracom-acquisition-001",
        booked_date=date(_YEAR, 2, 10),
        value_date=date(_YEAR, 2, 10),
        # The self-assessed cuota is not paid to the supplier: the movement is the base.
        amount=_INTRACOM_BASE,
        currency="EUR",
        counterparty="Lieferant GmbH",
        description="Adquisicion intracomunitaria de mercaderia",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(_YEAR, 2, 10, 10, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )
    return Transaction.model_validate(
        {
            "transaction_id": derive_transaction_id(raw),
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "category_id": "material_oficina",
            "iva_category": IvaCategory("intra_community_acquisition_reverse_charge"),
            "taxable_base": _INTRACOM_BASE,
            "iva_rate": Decimal("0.21"),
            "iva_amount": _INTRACOM_CUOTA,
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("intra_eu_current"),
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment"),
                source_locator="evidence:intracom-acquisition-001",
                evidence_digest="b" * 64,
            ),
            "counterparty_country": "DE",
            "counterparty_identification_state": "DE",
            "classified_at": datetime(_YEAR, 2, 11, 12, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _calculate_intracom_quarter(operation: PinnedAuthorityOperation) -> dict[CasillaId, Decimal]:
    """Aggregate the one acquisition through the real ledger and run the published 303 formulas."""
    snapshot = operation.snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD)
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((_intracom_acquisition(),)),
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        ledger_profile_id=_PROFILE_ID,
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_PROFILE_ID,
        operation=operation,
    )
    assert aggregation.issues == (), aggregation.issues
    ledger_values = resolve_iva_ledger_binding_values(
        snapshot.revision,
        aggregation.observations,
        prorrata_apportionment=None,
        operation=operation,
    )
    others: dict[BindingId, Decimal] = {
        binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.id not in ledger_values
    }
    others[_STATE_RATIO_BINDING] = Decimal("100")
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, ledger_values),
        binding_values=others,
        date_context={"filing_period": date(_YEAR, 12, 31)},
    )
    return dict(result.values)


def test_intracom_acquisition_self_assesses_and_deducts_the_same_cuota(*, operation: PinnedAuthorityOperation) -> None:
    """A reverse-charge intracom cuota feeds BOTH devengada-total AND deducible-total.

    LIVA art. 84.Uno.2.a) makes the acquirer the sujeto pasivo (output IVA,
    devengada); art. 92 makes that same self-assessed cuota deductible. One ledger
    row reaches ``iva.autorepercutido.intracomunitaria`` on the devengado side and
    box [37] on the deducible side, so a fully-deductible acquisition nets to zero
    régimen-general result. Reds if either leg drops the intracom cuota.
    """
    values = _calculate_intracom_quarter(operation)

    # The intracom cuota self-assesses as output IVA (devengada leg, art. 84)...
    assert values[_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_CASILLA] == _INTRACOM_CUOTA
    assert values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA] == _INTRACOM_CUOTA
    assert values[_M303_BOX_11_CASILLA] == _INTRACOM_CUOTA
    assert values[_M303_BOX_37_CASILLA] == _INTRACOM_CUOTA
    # ...AND is deductible by the same amount (deducible leg, art. 92).
    assert values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA] == _INTRACOM_CUOTA
    # The reverse-charge double-entry nets to zero régimen-general result.
    assert values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA] == Decimal("0.00")


def test_intracom_cuota_is_not_silently_dropped_from_deducible(*, operation: PinnedAuthorityOperation) -> None:
    """Anti-tautology: a NON-zero intracom cuota must move the deducible-total off zero.

    If the deducible-total formula ever dropped the intracom deducible leg, this
    would show deducible-total == 0 while devengada-total == 42 (output IVA with no
    offset) — a net positive result that over-states the IVA payable on a neutral
    acquisition.
    """
    values = _calculate_intracom_quarter(operation)

    assert values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA] > Decimal("0")
    assert values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA] > Decimal("0"), (
        "intracom autorepercutido cuota was dropped from the deducible total — "
        "reverse-charge acquisition would over-state IVA payable"
    )


def _recargo_purchase() -> Transaction:
    """A recargo-equivalencia retailer purchase: input IVA + RE surcharge, non-deductible."""
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
