"""Admit a recargo de equivalencia on a purchase only for a retailer the profile places in that regime.

A supplier repercutes the recargo de equivalencia only on an entrega to a comerciante minorista
in the special regime (LIVA arts. 154 and 156), so a purchase bearing it belongs to a taxpayer
whose own IVA regime is the recargo de equivalencia. That regime is a registered fact of the
profile; the row's IVA category label never stands in for it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.iva_regime_vocabulary import (
    iva_regime_recargo_equivalencia_token,
    require_iva_regime,
)
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.errors import TransactionValidationError
from ...domain.user_profile.errors import ProfileNotFoundError
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import fact_value

_REGIME_FACT_PATH = "iva.regime"


def require_recargo_regime_for_purchase(
    *,
    bucket_id: str,
    direction: TransactionDirection,
    recargo_amount: Decimal | None,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse a purchase recargo unless the profile's own IVA regime is the recargo de equivalencia.

    Only a purchase bearing a positive recargo is judged, so the profile is read only then. A
    supplier's sale may carry the recargo it repercuted whatever its own regime.
    """
    if direction is not TransactionDirection.OUTGOING or recargo_amount is None or recargo_amount == 0:
        return
    expected = iva_regime_recargo_equivalencia_token(effective_date=effective_date, authority=operation)
    if _profile_iva_regime(bucket_id, effective_date=effective_date, operation=operation) != expected:
        raise TransactionValidationError(
            "recargo_amount on a purchase is charged only to a retailer in the recargo de equivalencia "
            f"(LIVA arts. 154 and 156); this profile's {_REGIME_FACT_PATH} is not {expected}"
        )


def _profile_iva_regime(bucket_id: str, *, effective_date: date, operation: PinnedAuthorityOperation) -> str | None:
    try:
        record = ProfileRecordRepository.for_current_session(
            bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        ).load(bucket_id)
    except ProfileNotFoundError:
        return None
    raw = fact_value(record, _REGIME_FACT_PATH)
    if raw is None or not raw.strip():
        return None
    return require_iva_regime(raw.strip().upper(), effective_date=effective_date, authority=operation)


__all__ = ["require_recargo_regime_for_purchase"]
