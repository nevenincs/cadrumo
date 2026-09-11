"""Immutable, evidence-grounded IVA deduction-fact classification."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.identity.digest import ContentDigest
from ...core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ...core.models import STRICT_FROZEN_CONFIG
from .errors import IvaValidationError
from .flow import IvaFlowDirection
from .schema import IvaCategory, IvaRateKind


class IvaDeductionClassificationProvenance(BaseModel):
    """Immutable evidence pointer for one explicitly classified deduction fact."""

    model_config = STRICT_FROZEN_CONFIG

    authority: IvaDeductionEvidenceAuthority
    source_locator: str = Field(min_length=1, max_length=512)
    evidence_digest: ContentDigest


def _registry_iva_deduction_declarations() -> Mapping[str, str]:
    """Resolve the dated IVA deduction applicability catalogue."""
    from ...domain.calculations.registry.authority import bundled_authority
    from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
    from ...domain.calculations.registry.schema_base import DateAxis

    authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-deduction-applicability-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise IvaValidationError("IVA deduction applicability catalogue must resolve as a mapping fact")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def _required_declaration(declarations: Mapping[str, str], key: str) -> str:
    try:
        return declarations[key]
    except KeyError as exc:
        raise IvaValidationError(f"IVA deduction registry declaration is missing: {key}") from exc


def _declared_values(declarations: Mapping[str, str], key: str) -> frozenset[str]:
    return frozenset(value.strip() for value in _required_declaration(declarations, key).split(",") if value.strip())


def required_deduction_evidence_authority(kind: IvaDeductionFactKind) -> IvaDeductionEvidenceAuthority:
    """Return the one evidence authority that can establish ``kind``.

    Exposes the mapping :func:`validate_iva_deduction_fact` already enforces, so
    a caller deciding whether it is ABLE to build a provenance for a kind reads
    the same table the refusal is derived from. Without this a caller must
    either duplicate the mapping or attempt a construction it knows will be
    rejected, and a duplicate would be free to drift.
    """
    declarations = _registry_iva_deduction_declarations()
    authority_value = _required_declaration(declarations, f"kind.required_authority.{kind.value}")
    try:
        return IvaDeductionEvidenceAuthority(authority_value)
    except ValueError as exc:
        raise IvaValidationError(f"unknown IVA deduction evidence authority: {authority_value}") from exc


def _validate_required_authority(
    kind: IvaDeductionFactKind,
    provenance: IvaDeductionClassificationProvenance,
    declarations: Mapping[str, str],
) -> None:
    authority_value = _required_declaration(declarations, f"kind.required_authority.{kind.value}")
    try:
        required_authority = IvaDeductionEvidenceAuthority(authority_value)
    except ValueError as exc:
        raise IvaValidationError(f"unknown IVA deduction evidence authority: {authority_value}") from exc
    if provenance.authority is not required_authority:
        raise IvaValidationError(
            f"deduction kind {kind.value!r} requires {required_authority.value!r} evidence, "
            f"not {provenance.authority.value!r}"
        )


def _validate_investment_asset_identity(
    kind: IvaDeductionFactKind,
    investment_asset_id: str | None,
    declarations: Mapping[str, str],
) -> None:
    if kind.value in _declared_values(declarations, "kind.investment_acquisition"):
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
    declarations: Mapping[str, str],
) -> None:
    if rectifies_ledger_id is None:
        raise IvaValidationError("rectification requires rectifies_ledger_id")
    if base_amount == Decimal("0") or iva_amount == Decimal("0"):
        raise IvaValidationError("rectification base_amount and iva_amount must both be signed non-zero evidence")
    required_flow = _required_declaration(declarations, f"rectification_flow.{category.value}")
    if flow_direction.value != required_flow:
        raise IvaValidationError("rectification category and input IVA flow are not a closed legal pair")
    if rate_kind.value == _required_declaration(declarations, "rate.rectification_forbidden"):
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
    declarations: Mapping[str, str],
) -> None:
    kind_value = kind.value
    category_value = category.value
    flow_value = flow_direction.value
    if kind_value in _declared_values(declarations, "kind.domestic"):
        allowed_categories = _declared_values(declarations, "category.domestic")
        allowed_flows = _declared_values(declarations, "flow.domestic")
    elif kind_value in _declared_values(declarations, "kind.import"):
        allowed_categories = _declared_values(declarations, "category.import")
        allowed_flows = _declared_values(declarations, "flow.import")
    elif kind_value in _declared_values(declarations, "kind.intra_eu"):
        allowed_categories = _declared_values(declarations, "category.intra_eu")
        allowed_flows = _declared_values(declarations, "flow.intra_eu")
    elif kind_value in _declared_values(declarations, "kind.reagp"):
        allowed_categories = _declared_values(declarations, "category.reagp")
        allowed_flows = _declared_values(declarations, "flow.reagp")
        if rate_kind.value != _required_declaration(declarations, "rate.reagp"):
            raise IvaValidationError("registry-selected compensation rate is not admissible")
    else:
        return
    if category_value not in allowed_categories or flow_value not in allowed_flows:
        raise IvaValidationError("registry-selected deduction category and flow are not an admissible pair")


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
    declarations = _registry_iva_deduction_declarations()
    _validate_required_authority(kind, provenance, declarations)
    if kind.value in _declared_values(declarations, "kind.owner_only"):
        raise IvaValidationError("investment_goods_regularisation is emitted only by the bienes-inversion owner")
    _validate_investment_asset_identity(kind, investment_asset_id, declarations)
    if kind.value in _declared_values(declarations, "kind.rectification"):
        _validate_rectification(
            category=category,
            rate_kind=rate_kind,
            flow_direction=flow_direction,
            base_amount=base_amount,
            iva_amount=iva_amount,
            rectifies_ledger_id=rectifies_ledger_id,
            declarations=declarations,
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
        declarations=declarations,
    )


__all__ = ["IvaDeductionClassificationProvenance", "validate_iva_deduction_fact"]
