"""The incomplete M303 exonerado-390 unit refuses before byte emission."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core import (
    Modelo,
    PaymentElection,
    PriorDomiciliationElection,
    RefundElection,
    ResultDisposition,
)
from ....domain.deadlines import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from .. import (
    FilingElectionFacts,
    FilingProducerSnapshotError,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_exonerado_numeric_payload_refuses_before_target_while_atomic_unit_is_incomplete(tmp_path: Path) -> None:
    """An incomplete M303 producer snapshot fails before an artifact can be emitted."""
    output = tmp_path / "modelo-303-exonerado.txt"

    with pytest.raises(FilingProducerSnapshotError, match="modelo 303 requires complete M303FilingFacts"):
        build_filing_producer_snapshot(
            modelo=Modelo.M303,
            taxpayer_tax_id="12345678Z",
            taxpayer_identity=TaxpayerIdentityFacts(
                legal_name=None,
                given_name="Ana",
                surnames="Prueba",
                full_name="Ana Prueba",
            ),
            presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
            model_profile=ModeloIVAProfile(
                tax_territory=M303TaxTerritory.COMMON_REGIME,
                regime_composition=M303RegimeComposition.GENERAL,
                roi_enrolled=False,
                oss_enrolled=False,
                group_member_enrolled=False,
                group_dominant_entity_enrolled=False,
                intracommunity_operations_exceed_50000_eur=False,
                sii_enrolled=False,
                redeme_enrolled=False,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            ),
            elections=FilingElectionFacts(
                result_disposition=ResultDisposition.NEGATIVA,
                payment=PaymentElection.INGRESO,
                refund=RefundElection.COMPENSAR,
                prior_domiciliation=PriorDomiciliationElection.KEEP,
            ),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )

    assert not output.exists()
    assert not output.with_suffix(output.suffix + ".tmp").exists()
