"""Immutable, evidence-grounded IVA deduction-fact classification."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from ...core import (
    STRICT_FROZEN_CONFIG,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
)
from ...core.identity import ContentDigest
from ._flow import IvaFlowDirection, is_deducible_flow
from ._schema import IvaCategory, IvaRateKind
from .errors import IvaValidationError


class IvaDeductionClassificationProvenance(BaseModel):
    """Immutable evidence pointer for one explicitly classified deduction fact."""

    model_config = STRICT_FROZEN_CONFIG

    authority: IvaDeductionEvidenceAuthority
    source_locator: str = Field(min_length=1, max_length=512)
    evidence_digest: ContentDigest


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

_DOMESTIC_DEDUCTION_KINDS = frozenset(
    {IvaDeductionFactKind.DOMESTIC_CURRENT, IvaDeductionFactKind.DOMESTIC_INVESTMENT},
)
_IMPORT_DEDUCTION_KINDS = frozenset(
    {IvaDeductionFactKind.IMPORT_CURRENT, IvaDeductionFactKind.IMPORT_INVESTMENT},
)
_INTRA_EU_DEDUCTION_KINDS = frozenset(
    {IvaDeductionFactKind.INTRA_EU_CURRENT, IvaDeductionFactKind.INTRA_EU_INVESTMENT},
)


def required_deduction_evidence_authority(kind: IvaDeductionFactKind) -> IvaDeductionEvidenceAuthority:
    """Return the one evidence authority that can establish ``kind``.

    Exposes the mapping :func:`validate_iva_deduction_fact` already enforces, so
    a caller deciding whether it is ABLE to build a provenance for a kind reads
    the same table the refusal is derived from. Without this a caller must
    either duplicate the mapping or attempt a construction it knows will be
    rejected, and a duplicate would be free to drift.
    """
    return _REQUIRED_AUTHORITY[kind]


def _validate_required_authority(
    kind: IvaDeductionFactKind,
    provenance: IvaDeductionClassificationProvenance,
) -> None:
    required_authority = _REQUIRED_AUTHORITY[kind]
    if provenance.authority is not required_authority:
        raise IvaValidationError(
            f"deduction kind {kind.value!r} requires {required_authority.value!r} evidence, "
            f"not {provenance.authority.value!r}"
        )


def _validate_investment_asset_identity(kind: IvaDeductionFactKind, investment_asset_id: str | None) -> None:
    if kind.is_investment_acquisition:
        if investment_asset_id is None:
            raise IvaValidationError(f"deduction kind {kind.value!r} requires investment_asset_id")
    elif investment_asset_id is not None:
        raise IvaValidationError(f"non-investment deduction kind {kind.value!r} cannot carry investment_asset_id")


def _validate_rectification(
    *,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    base_amount: Decimal,
    iva_amount: Decimal,
    rectifies_ledger_id: str | None,
) -> None:
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


def _validate_non_rectification_identity(
    *,
    kind: IvaDeductionFactKind,
    base_amount: Decimal,
    iva_amount: Decimal,
    rectifies_ledger_id: str | None,
) -> None:
    if rectifies_ledger_id is not None:
        raise IvaValidationError(f"deduction kind {kind.value!r} cannot carry rectifies_ledger_id")
    if base_amount < Decimal("0") or iva_amount < Decimal("0"):
        raise IvaValidationError("only rectification may carry signed negative IVA evidence")


def _validate_non_rectification_category(
    *,
    kind: IvaDeductionFactKind,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
) -> None:
    if kind in _DOMESTIC_DEDUCTION_KINDS:
        _validate_domestic_deduction_category(category, flow_direction)
    elif kind in _IMPORT_DEDUCTION_KINDS:
        _validate_import_deduction_category(category, flow_direction)
    elif kind in _INTRA_EU_DEDUCTION_KINDS:
        _validate_intra_eu_deduction_category(category, flow_direction)
    elif kind is IvaDeductionFactKind.REAGP_COMPENSATION:
        _validate_reagp_compensation_category(category, rate_kind, flow_direction)


def _validate_domestic_deduction_category(category: IvaCategory, flow_direction: IvaFlowDirection) -> None:
    if category not in _DOMESTIC_DEDUCTION_CATEGORIES or not is_deducible_flow(flow_direction):
        raise IvaValidationError(
            "domestic deduction kind requires a domestic input or recipient reverse-charge fact",
        )


def _validate_import_deduction_category(category: IvaCategory, flow_direction: IvaFlowDirection) -> None:
    if category is not IvaCategory.IMPORT_THIRD_COUNTRY or flow_direction is not IvaFlowDirection.SOPORTADO:
        raise IvaValidationError("import deduction kind requires an import soportado fact")


def _validate_intra_eu_deduction_category(category: IvaCategory, flow_direction: IvaFlowDirection) -> None:
    if category not in _INTRA_EU_DEDUCTION_CATEGORIES or flow_direction is not IvaFlowDirection.INVERSION_SUJETO_PASIVO:
        raise IvaValidationError("intra-EU deduction kind requires an intra-EU recipient reverse-charge fact")


def _validate_reagp_compensation_category(
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
) -> None:
    if category is not IvaCategory.REAGP_COMPENSATION:
        raise IvaValidationError("REAGP compensation requires its closed compensation category")
    if flow_direction is not IvaFlowDirection.SOPORTADO or rate_kind is not IvaRateKind.EXEMPT:
        raise IvaValidationError("REAGP compensation requires a soportado exempt compensation fact")


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
    _validate_required_authority(kind, provenance)
    if kind is IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION:
        raise IvaValidationError("investment_goods_regularisation is emitted only by the bienes-inversion owner")
    _validate_investment_asset_identity(kind, investment_asset_id)
    if kind is IvaDeductionFactKind.RECTIFICATION:
        _validate_rectification(
            category=category,
            rate_kind=rate_kind,
            flow_direction=flow_direction,
            base_amount=base_amount,
            iva_amount=iva_amount,
            rectifies_ledger_id=rectifies_ledger_id,
        )
        return
    _validate_non_rectification_identity(
        kind=kind,
        base_amount=base_amount,
        iva_amount=iva_amount,
        rectifies_ledger_id=rectifies_ledger_id,
    )
    _validate_non_rectification_category(
        kind=kind,
        category=category,
        rate_kind=rate_kind,
        flow_direction=flow_direction,
    )


__all__ = ["IvaDeductionClassificationProvenance", "validate_iva_deduction_fact"]
