"""A linked purchase invoice is screened inside the slice its ledger row declared.

The invoice IVA screen re-apportions each screened input with the same resolver
the ledger path uses. A sectorised register refuses an input that names no sector,
and prorrata especial routes an input by its art. 106 classification, so an
observation that dropped those two fields from its linked ledger authority was
either refused outright or compared at the wrong percentage. The observation now
carries both from the authority.

Expected values are hand-computed from the invoice's own 21 % cuota of 21.00.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import IvaRate
from ....domain.invoices.models import Invoice
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.prorrata import InputClassification
from ....domain.iva.schema import InvoiceKind, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ..errors import AggregationValidationError
from ..iva_ledger import IvaLedgerProrrataApportionment, IvaLedgerSectorApportionment
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from ..modelo_bindings_invoice_iva import invoice_line_iva_observation

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_DAY = date(_YEAR, 3, 15)
_CUOTA_BINDING = "modelo-303-iva-soportado-interiores-cuota"


def _pinned_operation() -> PinnedAuthorityOperation:
    scoped = governed_facts_in_scope()
    assert isinstance(scoped, PinnedAuthorityOperation)
    return scoped


def _received_invoice() -> Invoice:
    return Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": InvoiceKind.RECEIVED.value,
            "invoice_number": "F-2026-0101",
            "issued_at": _DAY.isoformat(),
            "counterparty_name": "Proveedor Ejemplo SL",
            "counterparty_tax_id": "ESB00015016",
            "counterparty_country": "ES",
            "base_total": "100.00",
            "iva_total": "21.00",
            "grand_total": "121.00",
            "currency": "EUR",
            "payment_status": "PENDING",
            "lines": [
                {
                    "description": "Suministro",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "subtotal": "100.00",
                    "iva_rate": IvaRate.from_registry("RATE_21").value,
                    "iva_amount": "21.00",
                },
            ],
        },
    )


def _authority(
    *,
    sector_id: str | None,
    classification: InputClassification | None,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id="transaction:linked-purchase",
        transaction_date=_DAY,
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow_direction=IvaFlowDirection.from_registry("soportado"),
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator="invoice:linked-purchase",
            evidence_digest="b" * 64,
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
        input_classification=classification,
        prorrata_sector_id=sector_id,
    )


def _screen_observation(authority: IvaLedgerObservation) -> IvaLedgerObservation:
    invoice = _received_invoice()
    line = invoice.lines[0]
    base = invoice.line_amount_eur(line.subtotal)
    cuota = invoice.line_amount_eur(line.iva_amount)
    assert base is not None
    assert cuota is not None
    observation = invoice_line_iva_observation(
        invoice=invoice,
        line=line,
        line_index=0,
        devengo_date=_DAY,
        recargo_amount=Decimal("0"),
        base_amount_eur=base,
        iva_amount_eur=cuota,
        deduction_authority=authority,
        operation=_pinned_operation(),
    )
    assert observation is not None
    return observation


def _sectorised(*, sector_regime: str, sector_percentage: str) -> IvaLedgerProrrataApportionment:
    return IvaLedgerProrrataApportionment(
        percentage=Decimal("50"),
        provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
        sector_apportionments=(
            IvaLedgerSectorApportionment(
                sector_id="comercio",
                percentage=Decimal(sector_percentage),
                regime=ProrrataRegisterRegime.from_registry(sector_regime),
            ),
        ),
    )


def _cuota(observation: IvaLedgerObservation, apportionment: IvaLedgerProrrataApportionment) -> Decimal:
    revision = published_snapshot("303", filing_year=_YEAR, period="1T").revision
    values = resolve_iva_ledger_binding_values(
        revision,
        (observation,),
        prorrata_apportionment=apportionment,
        operation=_pinned_operation(),
    )
    return values[_CUOTA_BINDING]


def test_the_observation_carries_classification_and_sector_from_its_authority() -> None:
    classification = InputClassification.from_registry("exclusively_deductible")
    observation = _screen_observation(_authority(sector_id="comercio", classification=classification))

    assert observation.prorrata_sector_id == "comercio"
    assert observation.input_classification == classification


def test_an_unclassified_authority_stays_unclassified_on_the_observation() -> None:
    observation = _screen_observation(_authority(sector_id=None, classification=None))

    assert observation.prorrata_sector_id is None
    assert observation.input_classification is None


def test_a_linked_purchase_compares_within_its_general_sector_percentage() -> None:
    observation = _screen_observation(_authority(sector_id="comercio", classification=None))

    # 21.00 cuota x 90 % sector percentage.
    assert _cuota(observation, _sectorised(sector_regime="general", sector_percentage="90")) == Decimal("18.90")


def test_a_linked_purchase_compares_within_its_especial_sector_classification() -> None:
    apportionment = _sectorised(sector_regime="especial", sector_percentage="20")
    full = _screen_observation(
        _authority(sector_id="comercio", classification=InputClassification.from_registry("exclusively_deductible"))
    )
    common = _screen_observation(
        _authority(sector_id="comercio", classification=InputClassification.from_registry("common"))
    )

    # Regla 1.a deducts the full 21.00; regla 3.a applies the sector's 20 %: 4.20.
    assert _cuota(full, apportionment) == Decimal("21.00")
    assert _cuota(common, apportionment) == Decimal("4.20")


def test_an_observation_stripped_of_its_sector_is_still_refused_by_a_sectorised_register() -> None:
    observation = _screen_observation(_authority(sector_id="comercio", classification=None))
    stripped = observation.model_copy(update={"prorrata_sector_id": None})

    with pytest.raises(
        AggregationValidationError,
        match=r"aggregation\.iva_ledger\.errors\.sectorized_input_missing_sector_identity",
    ):
        _cuota(stripped, _sectorised(sector_regime="general", sector_percentage="90"))
