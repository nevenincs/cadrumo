"""The incomplete M303 exonerado-390 unit refuses before byte emission."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import (
    Modelo,
    PaymentElection,
    Period,
    PriorDomiciliationElection,
    RefundElection,
    ResultDisposition,
)
from ....domain.deadlines import ModeloIVAProfile
from ....domain.submission import ModeloDraftStatus
from .. import (
    FilingElectionFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_draft,
    build_filing_producer_snapshot,
    build_runtime_schema_provider,
    export_draft,
)
from .._export import FilingExportError
from ..runtime import ModeloOperatorProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ENDPOINTS = frozenset(
    {"79", "80", "81", "83", "84", "86", "88", "89", "90", "91", "92", "93", "94", "95", "96", "97", "98", "99", "107", "125", "126", "127", "128"}
)


def test_exonerado_numeric_payload_refuses_before_target_while_atomic_unit_is_incomplete(tmp_path: Path) -> None:
    """All numbered endpoints cannot bypass the missing flag/nonnumbered producers."""
    period = Period.from_year_and_code(2025, "4T")
    provider = build_runtime_schema_provider(filing_year=2025, period=period, modelos=("303",))
    inputs = {
        "07": Decimal("0"),
        "iva.soportado.interiores": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        **{endpoint: Decimal("0") for endpoint in _ENDPOINTS},
    }
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Exonerado refusal proof"),
        inputs=inputs,
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    producer_snapshot = build_filing_producer_snapshot(
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
            roi_enrolled=False,
            oss_enrolled=False,
            group_member_enrolled=False,
            group_dominant_entity_enrolled=False,
            intracommunity_operations_exceed_50000_eur=False,
            sii_enrolled=False,
            redeme_enrolled=False,
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
    )
    output = tmp_path / "modelo-303-exonerado.txt"

    with pytest.raises(FilingExportError, match="explicit applicability envelope"):
        export_draft(
            draft,
            output_path=output,
            producer_snapshot=producer_snapshot,
            schema_provider=provider,
        )

    assert not output.exists()
