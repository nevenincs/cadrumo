"""Immutable, evidence-grounded IVA deduction-fact classification."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from ...core import (
    STRICT_FROZEN_CONFIG,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
)
from ._errors import IvaValidationError
from ._flow import IvaFlowDirection
from ._schema import IvaCategory, IvaRateKind


class IvaDeductionClassificationProvenance(BaseModel):
    """Immutable evidence pointer for one explicitly classified deduction fact."""

    model_config = STRICT_FROZEN_CONFIG

    authority: IvaDeductionEvidenceAuthority
    source_locator: str = Field(min_length=1, max_length=512)
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


_DOMESTIC_DEDUCTION_CATEGORIES = frozenset(
    {
        IvaCategory.DOMESTIC_GENERAL,
        IvaCategory.DOMESTIC_REDUCED,
        IvaCategory.DOMESTIC_SUPER_REDUCED,
        IvaCategory.DOMESTIC_ZERO,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
    }
)
_INTRA_EU_DEDUCTION_CATEGORIES = frozenset(
    {
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
    }
)
_REQUIRED_AUTHORITY = {
    IvaDeductionFactKind.DOMESTIC_CURRENT: IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
    IvaDeductionFactKind.DOMESTIC_INVESTMENT: IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
    IvaDeductionFactKind.IMPORT_CURRENT: IvaDeductionEvidenceAuthority.CUSTOMS_DECLARATION,
    IvaDeductionFactKind.IMPORT_INVESTMENT: IvaDeductionEvidenceAuthority.CUSTOMS_DECLARATION,
    IvaDeductionFactKind.INTRA_EU_CURRENT: IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
    IvaDeductionFactKind.INTRA_EU_INVESTMENT: IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
    IvaDeductionFactKind.REAGP_COMPENSATION: IvaDeductionEvidenceAuthority.REAGP_RECEIPT,
    IvaDeductionFactKind.RECTIFICATION: IvaDeductionEvidenceAuthority.RECTIFICATION_EVIDENCE,
    IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION: IvaDeductionEvidenceAuthority.BIENES_INVERSION_REGISTER,
}


def validate_iva_deduction_fact(
    *,
    kind: IvaDeductionFactKind,
    provenance: IvaDeductionClassificationProvenance,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    base_amount: Decimal,
    iva_amount: Decimal,
    investment_asset_id: str | None,
    rectifies_ledger_id: str | None,
) -> None:
    """Refuse every deduction classification combination lacking legal authority."""
    required_authority = _REQUIRED_AUTHORITY[kind]
    if provenance.authority is not required_authority:
        raise IvaValidationError(
            f"deduction kind {kind.value!r} requires {required_authority.value!r} evidence, "
            f"not {provenance.authority.value!r}"
        )
    if kind is IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION:
        raise IvaValidationError("investment_goods_regularisation is emitted only by the bienes-inversion owner")
    if kind.is_investment_acquisition:
        if investment_asset_id is None:
            raise IvaValidationError(f"deduction kind {kind.value!r} requires investment_asset_id")
    elif investment_asset_id is not None:
        raise IvaValidationError(f"non-investment deduction kind {kind.value!r} cannot carry investment_asset_id")
    if kind is IvaDeductionFactKind.RECTIFICATION:
        if rectifies_ledger_id is None:
            raise IvaValidationError("rectification requires rectifies_ledger_id")
        if base_amount == Decimal("0") or iva_amount == Decimal("0"):
            raise IvaValidationError("rectification base_amount and iva_amount must both be signed non-zero evidence")
        rectification_flows = {
            IvaCategory.DOMESTIC_GENERAL: IvaFlowDirection.SOPORTADO,
            IvaCategory.DOMESTIC_REDUCED: IvaFlowDirection.SOPORTADO,
            IvaCategory.DOMESTIC_SUPER_REDUCED: IvaFlowDirection.SOPORTADO,
            IvaCategory.DOMESTIC_REVERSE_CHARGE: IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            IvaCategory.IMPORT_THIRD_COUNTRY: IvaFlowDirection.SOPORTADO,
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE: IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE: IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        }
        required_flow = rectification_flows.get(category)
        if required_flow is None or flow_direction is not required_flow:
            raise IvaValidationError("rectification category and input IVA flow are not a closed legal pair")
        if rate_kind is IvaRateKind.EXEMPT:
            raise IvaValidationError("rectification of a deductible cuota cannot use the exempt rate tier")
        return
    if rectifies_ledger_id is not None:
        raise IvaValidationError(f"deduction kind {kind.value!r} cannot carry rectifies_ledger_id")
    if base_amount < Decimal("0") or iva_amount < Decimal("0"):
        raise IvaValidationError("only rectification may carry signed negative IVA evidence")
    if kind in {IvaDeductionFactKind.DOMESTIC_CURRENT, IvaDeductionFactKind.DOMESTIC_INVESTMENT}:
        if category not in _DOMESTIC_DEDUCTION_CATEGORIES or flow_direction not in {
            IvaFlowDirection.SOPORTADO,
            IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        }:
            raise IvaValidationError(
                "domestic deduction kind requires a domestic input or recipient reverse-charge fact",
            )
    elif kind in {IvaDeductionFactKind.IMPORT_CURRENT, IvaDeductionFactKind.IMPORT_INVESTMENT}:
        if category is not IvaCategory.IMPORT_THIRD_COUNTRY or flow_direction is not IvaFlowDirection.SOPORTADO:
            raise IvaValidationError("import deduction kind requires an import soportado fact")
    elif kind in {IvaDeductionFactKind.INTRA_EU_CURRENT, IvaDeductionFactKind.INTRA_EU_INVESTMENT}:
        if (
            category not in _INTRA_EU_DEDUCTION_CATEGORIES
            or flow_direction is not IvaFlowDirection.INVERSION_SUJETO_PASIVO
        ):
            raise IvaValidationError("intra-EU deduction kind requires an intra-EU recipient reverse-charge fact")
    elif kind is IvaDeductionFactKind.REAGP_COMPENSATION:
        if category is not IvaCategory.REAGP_COMPENSATION:
            raise IvaValidationError("REAGP compensation requires its closed compensation category")
        if flow_direction is not IvaFlowDirection.SOPORTADO or rate_kind is not IvaRateKind.EXEMPT:
            raise IvaValidationError("REAGP compensation requires a soportado exempt compensation fact")


__all__ = ["IvaDeductionClassificationProvenance", "validate_iva_deduction_fact"]
