"""Where each ledger readiness reason is put right, for every frontend that leads a person to the fix."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from .preflight import LedgerPreflightIssueReason as Reason
from .staged_check_contracts import StageFieldName

READINESS_REASON_FIELDS: Final[Mapping[Reason, StageFieldName]] = MappingProxyType(
    {
        Reason.MISSING_CATEGORY: "category_id",
        Reason.MISSING_TAXABLE_BASE: "taxable_base",
        Reason.MISSING_IVA_AMOUNT: "iva_amount",
        Reason.MISSING_IVA_RATE: "iva_rate",
        Reason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE: "counterparty_identification_state",
        Reason.MISSING_PROPORTIONALITY_REFERENCE: "business_pct",
        Reason.INADMISSIBLE_DEDUCTION_CLASSIFICATION: "business_classification",
        Reason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION: "iva_category",
        Reason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION: "iva_category",
        Reason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT: "iva_category",
        Reason.ANOMALY_NON_DECLARABLE_IVA_CATEGORY: "iva_category",
        Reason.ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA: "iva_category",
    }
)
"""The one field a reason names, on the movement it was found on; a reason with no entry has no such field."""

IVA_DERIVABLE_REASONS: Final[frozenset[Reason]] = frozenset(
    {Reason.MISSING_TAXABLE_BASE, Reason.MISSING_IVA_AMOUNT, Reason.MISSING_IVA_RATE}
)
"""The reasons ``derive_iva_substrate`` answers: it works out the rate, base and amount from a category."""


__all__ = ["IVA_DERIVABLE_REASONS", "READINESS_REASON_FIELDS"]
