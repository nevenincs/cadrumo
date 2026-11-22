"""A rectification that reduces an earlier deduction reaches casillas 40/41 with its sign.

LIVA art. 114.Uno makes the rectification of deductions OBLIGATORY where it
means a reduction: "La rectificación de las deducciones sera obligatoria cuando
implique una minoracion del importe inicialmente deducido." Art. 114.Dos.2.o's
last paragraph fixes the period and leaves no election for it: "cuando la
rectificacion tenga su origen en un error fundado de derecho o en las restantes
causas del articulo 80 de esta Ley debera efectuarse en la declaracion-liquidacion
correspondiente al periodo impositivo en que el sujeto pasivo reciba el documento
justificativo del derecho a deducir en el que se rectifiquen las cuotas
inicialmente soportadas". RIVA (RD 1624/1992) art. 24.2.b.2.o says the same in the
recipient's words: "en la declaracion-liquidacion correspondiente al periodo en
que se hayan recibido las facturas rectificativas de las operaciones, el citado
destinatario debera hacer constar el importe total de las cuotas rectificadas
como minoracion de las cuotas deducidas".

The box and its sign come from the Modelo 303 instructions for casillas 40 and 41
(bundled `_data/corpus/aeat_official/instructions/modelo_303/files/
modelo-303-instrucciones-20261106.html`): "Se hara constar el importe de la base
imponible y de las cuotas deducibles rectificadas, regularizadas en las
autoliquidaciones del ejercicio. ... Si el resultado de la rectificacion implica
una minoracion de las deducciones, se consignara con signo negativo."

The registry already carries that box: the 2022 edition binds casillas 40 and 41
to `modelo-303-iva-rectificacion-deducciones-*`, whose selectors read
`deduction_fact_kinds = ["rectification"]` off the ledger IVA aggregation, and
`validate_iva_deduction_fact` already states that only a rectification may carry
signed negative IVA evidence. Nothing produced that sign: the row's cuota reached
the observation as the stored magnitude, so a supplier's refund of a cuota already
deducted RAISED the deduction it is obliged to reduce. The ledger keeps economic
direction in `direction` rather than in the sign of the tax substrate, so the sign
belongs on the projection, which is what these tests drive.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.iva.deduction_facts import (
    IvaDeductionClassificationProvenance,
    rectification_settlement_flow,
)
from ....domain.iva.flow import received_flow_direction
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..iva_ledger import IvaLedgerAggregation, aggregate_iva_ledger_observations
from .ledger_transaction_support import iva_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_ON_DATE = date(_YEAR, 2, 10)
_PROFILE_ID = "rectification-minoracion"
_DOMESTIC_GENERAL = IvaCategory("domestic_general")
_RECTIFICATION = "rectification"
_CORRECTED_ROW_ID = "purchase-being-corrected"


def _aggregate(*transactions: Transaction, operation: PinnedAuthorityOperation) -> IvaLedgerAggregation:
    return aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(transactions),
        period=_PERIOD,
        ledger_profile_id=_PROFILE_ID,
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_PROFILE_ID,
        operation=operation,
    )


def _rectification_provenance(provider_id: str) -> IvaDeductionClassificationProvenance:
    """The authority fact 0085 requires of a rectification: its own rectifying document."""
    return IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.from_registry("rectification_evidence"),
        source_locator=f"rectificativa:{provider_id}",
        evidence_digest="b" * 64,
    )


def _rectification_row(
    provider_id: str,
    *,
    direction: TransactionDirection,
    category: IvaCategory = _DOMESTIC_GENERAL,
    taxable_base: Decimal = Decimal("100.00"),
    iva_amount: Decimal = Decimal("21.00"),
    gross: Decimal | None = None,
) -> Transaction:
    """One ledger row declaring that it rectifies an earlier domestic deduction.

    The row's cash direction is the only fact that says which way the
    rectification goes: a refund reaches the taxpayer's account (``INCOMING``)
    and reduces the earlier deduction, an additional cuota leaves it
    (``OUTGOING``) and raises it. The stored substrate stays a magnitude either
    way, as every ledger row's does.
    """
    row = iva_transaction(
        provider_id,
        direction=direction,
        amount=taxable_base + iva_amount if gross is None else gross,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        booked_date=_ON_DATE,
        iva_category=category,
    )
    return Transaction.model_validate(
        row.model_dump()
        | {
            "deduction_fact_kind": IvaDeductionFactKind.from_registry(_RECTIFICATION),
            "deduction_provenance": _rectification_provenance(provider_id).model_dump(),
            "rectifies_ledger_id": _CORRECTED_ROW_ID,
        },
    )


def test_the_registry_reads_casillas_40_and_41_off_the_rectification_deduction_kind(
    *, operation: PinnedAuthorityOperation
) -> None:
    """Anchor: without these bindings the signed observation would reach no box.

    If the 303 edition stops selecting the rectification kind for the
    rectificacion-de-deducciones boxes, the sign assertions below prove nothing
    about casillas 40 and 41, so the binding is asserted rather than assumed.
    """
    revision = operation.revision_for_context("303", filing_year=_PERIOD.filing_year, period=_PERIOD.code)
    selected = {
        binding.id: binding.provider
        for binding in revision.bindings
        if binding.id.startswith("modelo-303-iva-rectificacion-deducciones-")
    }

    assert selected, "the 303 edition declares no rectificacion-de-deducciones binding"
    for binding_id, provider in selected.items():
        kinds = getattr(provider, "deduction_fact_kinds", None)
        assert kinds is not None, f"{binding_id} does not select on the deduction kind"
        assert [kind.value for kind in kinds] == [_RECTIFICATION], binding_id


def test_a_refunded_cuota_already_deducted_reduces_the_deduction(*, operation: PinnedAuthorityOperation) -> None:
    """The obligatory minoracion: a refund of a cuota already deducted is negative evidence."""
    result = _aggregate(
        _rectification_row("supplier-refund", direction=TransactionDirection.INCOMING),
        operation=operation,
    )

    refusals = [f"{issue.reason.value}: {issue.detail}" for issue in result.issues]
    assert refusals == [], f"the obligatory minoracion was refused: {refusals}"
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.deduction_fact_kind == IvaDeductionFactKind.from_registry(_RECTIFICATION)
    assert observation.flow_direction == received_flow_direction(effective_date=_ON_DATE)
    assert observation.rectifies_ledger_id == _CORRECTED_ROW_ID
    assert observation.base_amount == Decimal("-100.00"), f"base {observation.base_amount}"
    assert observation.iva_amount == Decimal("-21.00"), f"cuota {observation.iva_amount}"


def test_an_additional_cuota_borne_raises_the_deduction(*, operation: PinnedAuthorityOperation) -> None:
    """Control, the other direction: art. 114.Dos.1.o's increment stays positive."""
    result = _aggregate(
        _rectification_row("supplier-charges-more", direction=TransactionDirection.OUTGOING),
        operation=operation,
    )

    assert [issue.reason.value for issue in result.issues] == []
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.deduction_fact_kind == IvaDeductionFactKind.from_registry(_RECTIFICATION)
    assert observation.flow_direction == received_flow_direction(effective_date=_ON_DATE)
    assert observation.base_amount == Decimal("100.00")
    assert observation.iva_amount == Decimal("21.00")


def test_a_reverse_charge_rectification_settles_on_the_side_the_registry_declares(
    *, operation: PinnedAuthorityOperation
) -> None:
    """The settlement side is read per category, not fixed at soportado.

    Fact 0085 declares ``rectification_flow.domestic_reverse_charge`` as
    inversion del sujeto pasivo, which is the part of casillas 40/41 the
    reverse-charge binding reads. A rule that assumed soportado would put this
    row in the wrong third of the box, so the declared side is asserted.
    """
    result = _aggregate(
        _rectification_row(
            "reverse-charge-refund",
            direction=TransactionDirection.INCOMING,
            category=IvaCategory("domestic_reverse_charge"),
            # On a self-assessed acquisition the supplier repercutes no cuota,
            # so the cash the row records is the base alone.
            gross=Decimal("100.00"),
        ),
        operation=operation,
    )

    refusals = [f"{issue.reason.value}: {issue.detail}" for issue in result.issues]
    assert refusals == [], f"the reverse-charge minoracion was refused: {refusals}"
    assert len(result.observations) == 1
    observation = result.observations[0]
    declared = rectification_settlement_flow(category=IvaCategory("domestic_reverse_charge"), effective_date=_ON_DATE)
    assert declared is not None
    assert declared != received_flow_direction(effective_date=_ON_DATE)
    assert observation.flow_direction == declared
    assert observation.base_amount == Decimal("-100.00")
    assert observation.iva_amount == Decimal("-21.00")


def test_an_ordinary_purchase_is_unchanged(*, operation: PinnedAuthorityOperation) -> None:
    """Control: a row declaring no rectification keeps the ordinary current deduction, positive."""
    result = _aggregate(
        iva_transaction(
            "ordinary-purchase",
            direction=TransactionDirection.OUTGOING,
            amount=Decimal("121.00"),
            taxable_base=Decimal("100.00"),
            iva_amount=Decimal("21.00"),
            booked_date=_ON_DATE,
            iva_category=_DOMESTIC_GENERAL,
        ),
        operation=operation,
    )

    assert [issue.reason.value for issue in result.issues] == []
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.deduction_fact_kind == IvaDeductionFactKind.from_registry("domestic_current")
    assert observation.rectifies_ledger_id is None
    assert observation.base_amount == Decimal("100.00")
    assert observation.iva_amount == Decimal("21.00")
