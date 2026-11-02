"""Parse activity-asset statements from the Ledger TUI inputs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import ValidationError

from ....application.actividad_asset.operation_dtos import ActivityAssetDisposalSnapshot
from ....application.actividad_asset.request_restoration import restoring
from ....application.operations.public_scalar import PublicDecimal
from ....core.decimal.coercion import coerce_finite_european_decimal
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.parsing.dates import require_iso8601_date
from ....domain.renta.actividad_asset.disposal import ActivityAssetDisposalReason, PriorFreeDepreciationRegime
from ....domain.renta.actividad_asset.election import ActivityAssetAmortizationElection, AmortizationMethod
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetBasis, ActivityAssetRevision


class InputRefusedError(CadrumoError):
    """An entry the operator can correct, already worded for the screen in the interface language."""


def stated_date(text: str) -> date:
    """Read a day written as ``YYYY-MM-DD``, or say how to write it."""
    try:
        return require_iso8601_date(text)
    except ValueError:
        raise InputRefusedError(tr("tui.ledger.activity_asset.errors.date_invalid")) from None


def stated_amount(text: str) -> PublicDecimal:
    """Read an amount, or say how to write it."""
    try:
        return PublicDecimal(decimal=text)
    except ValidationError:
        raise InputRefusedError(tr("tui.ledger.activity_asset.errors.amount_invalid")) from None


def stated_choice[Choice: StrEnum](choices: type[Choice], text: str) -> Choice:
    """Read one member of a closed set, or list the members."""
    try:
        return choices(text)
    except ValueError:
        raise InputRefusedError(
            tr("tui.ledger.activity_asset.errors.choice_invalid", options=", ".join(member.value for member in choices))
        ) from None


def stated_disposal(read_value: Callable[[str], str]) -> ActivityAssetDisposalSnapshot:
    """Read the baja's inputs; the operation judges the reason and the amounts."""
    market_value = read_value("asset-disposal-market-value")
    prior_regime = read_value("asset-disposal-prior-regime")
    later_affectation = read_value("asset-disposal-later-affectation")
    return ActivityAssetDisposalSnapshot(
        disposal_date=stated_date(read_value("asset-disposal-date")),
        reason=stated_choice(ActivityAssetDisposalReason, read_value("asset-disposal-reason")),
        proceeds=stated_amount(read_value("asset-disposal-proceeds") or "0.00"),
        transmission_costs=stated_amount(read_value("asset-disposal-costs") or "0.00"),
        market_value=stated_amount(market_value) if market_value else None,
        prior_free_depreciation_regime=stated_choice(PriorFreeDepreciationRegime, prior_regime)
        if prior_regime
        else None,
        later_affectation_on=stated_date(later_affectation) if later_affectation else None,
    )


def stated_revision(read_value: Callable[[str], str], revision_json: str) -> ActivityAssetRevision:
    """Read the revision, with each typed fact the operator stated in place of the one it carries."""
    try:
        revision = ActivityAssetRevision.model_validate_json(revision_json)
    except ValidationError:
        raise InputRefusedError(
            tr("tui.ledger.activity_asset.errors.json_invalid", field=tr("tui.ledger.activity_asset.revision"))
        ) from None
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
        updates["in_service_date"] = stated_date(in_service)
    if method:
        election = dict(revision.amortization)
        election["method"] = stated_choice(AmortizationMethod, method)
        updates["amortization"] = restoring(lambda: ActivityAssetAmortizationElection.model_validate(election))
    if not updates:
        return revision
    return ActivityAssetRevision.model_validate({**dict(revision), **updates})


def _fact_amount(read_value: Callable[[str], str], input_id: str) -> Decimal | None:
    """Read a stated amount; an empty field is no statement, and an ambiguous number is refused."""
    text = read_value(input_id)
    if not text:
        return None
    amount = coerce_finite_european_decimal(text)
    if amount is None:
        raise InputRefusedError(tr("tui.ledger.activity_asset.errors.amount_invalid"))
    return amount


__all__ = [
    "InputRefusedError",
    "stated_amount",
    "stated_choice",
    "stated_date",
    "stated_disposal",
    "stated_revision",
]
