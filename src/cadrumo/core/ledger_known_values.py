"""The closed set of values a profile's records can offer a person typing."""

from __future__ import annotations

from enum import StrEnum


class LedgerKnownValueKind(StrEnum):
    """One family of text the ledger, its invoices and its assets already state."""

    COUNTERPARTY = "counterparty"
    DESCRIPTION = "description"
    GROUP_LABEL = "group_label"
    M210_PAYER = "m210_payer"
    M210_ASSET = "m210_asset"
    ASSET_REFERENCE = "asset_reference"
