"""Applicable Modelo 303 prorrata rows fail before target creation."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import (
    Modelo,
    PaymentElection,
    Period,
    PriorDomiciliationElection,
    ProrrataRegisterRegime,
    RefundElection,
    ResultDisposition,
)
from ....domain.deadlines import ModeloIVAProfile
from ....domain.filing import FilingExportError
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
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
from ..runtime import ModeloOperatorProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_applicable_prorrata_without_all_five_rows_refuses_before_layout_or_target(tmp_path: Path) -> None:
    """The typed register gate runs before the withdrawn M303 layout can mask it."""
    period = Period.from_year_and_code(2025, "4T")
    provider = build_runtime_schema_provider(filing_year=2025, period=period, modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Prorrata row refusal proof"),
        inputs={
            "07": Decimal("0"),
            "iva.soportado.interiores": Decimal("0"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
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
    register = ProrrataRegister(
        entries=(ProrrataRegisterEntry(ejercicio=2025, regime=ProrrataRegisterRegime.GENERAL),),
    )
    output = tmp_path / "modelo-303-prorrata-row-refusal.txt"

    with pytest.raises(FilingExportError, match="per-activity prorrata rows are incomplete"):
        export_draft(
            draft,
            output_path=output,
            producer_snapshot=producer_snapshot,
            schema_provider=provider,
            prorrata_register=register,
        )

    assert not output.exists()
