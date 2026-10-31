"""Parse activity-asset statements from the Ledger TUI inputs."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from pydantic import ValidationError

from ....application.actividad_asset.operation_dtos import ActivityAssetDisposalSnapshot
from ....application.operations.public_scalar import PublicDecimal
from ....core.decimal.coercion import coerce_finite_european_decimal
from ....core.parsing.dates import require_iso8601_date
from ....domain.renta.actividad_asset.disposal import ActivityAssetDisposalReason, PriorFreeDepreciationRegime
from ....domain.renta.actividad_asset.election import ActivityAssetAmortizationElection, AmortizationMethod
from ....domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetBasis, ActivityAssetRevision


def stated_disposal(read_value: Callable[[str], str]) -> ActivityAssetDisposalSnapshot:
    """Read the baja's inputs; the operation judges the reason and the amounts."""
    market_value = read_value("asset-disposal-market-value")
    prior_regime = read_value("asset-disposal-prior-regime")
    later_affectation = read_value("asset-disposal-later-affectation")
    return ActivityAssetDisposalSnapshot(
        disposal_date=require_iso8601_date(read_value("asset-disposal-date")),
        reason=ActivityAssetDisposalReason(read_value("asset-disposal-reason")),
        proceeds=PublicDecimal(decimal=read_value("asset-disposal-proceeds") or "0.00"),
        transmission_costs=PublicDecimal(decimal=read_value("asset-disposal-costs") or "0.00"),
        market_value=PublicDecimal(decimal=market_value) if market_value else None,
        prior_free_depreciation_regime=PriorFreeDepreciationRegime(prior_regime) if prior_regime else None,
        later_affectation_on=require_iso8601_date(later_affectation) if later_affectation else None,
    )


def stated_revision(read_value: Callable[[str], str], revision_json: str) -> ActivityAssetRevision:
    """Read the revision, with each typed fact the operator stated in place of the one it carries."""
    revision = ActivityAssetRevision.model_validate_json(revision_json)
    price = _fact_amount(read_value, "asset-price")
    non_deductible_iva = _fact_amount(read_value, "asset-non-deductible-iva")
    in_service = read_value("asset-in-service-date")
    method = read_value("asset-method")
    updates: dict[str, object] = {}
    if price is not None or non_deductible_iva is not None:
        basis = dict(revision.basis)
        if price is not None:
            basis["basis_amount"] = price
        if non_deductible_iva is not None:
            basis["non_deductible_iva"] = non_deductible_iva
        updates["basis"] = ActivityAssetBasis.model_validate(basis)
    if in_service:
        updates["in_service_date"] = require_iso8601_date(in_service)
    if method:
        election = dict(revision.amortization)
        election["method"] = AmortizationMethod(method)
        updates["amortization"] = _stated_election(election)
    if not updates:
        return revision
    return ActivityAssetRevision.model_validate({**dict(revision), **updates})


def _stated_election(election: dict[str, object]) -> ActivityAssetAmortizationElection:
    """Keep a single registered election refusal available to the TUI renderer."""
    try:
        return ActivityAssetAmortizationElection.model_validate(election)
    except ValidationError as exc:
        details = exc.errors(include_url=False)
        if len(details) == 1:
            context = details[0].get("ctx", {})
            wrapped = context.get("error")
            cause = wrapped.__cause__ if isinstance(wrapped, ValueError) else None
            if isinstance(cause, ActividadAssetValidationError):
                raise cause from exc
        raise


def _fact_amount(read_value: Callable[[str], str], input_id: str) -> Decimal | None:
    """Read a stated amount; an empty field is no statement, and an ambiguous number is refused."""
    text = read_value(input_id)
    if not text:
        return None
    amount = coerce_finite_european_decimal(text)
    if amount is None:
        raise ValueError(f"{input_id} is not an unambiguous amount")
    return amount


__all__ = ["stated_disposal", "stated_revision"]
