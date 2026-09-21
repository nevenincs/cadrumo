"""Strict JSON result envelopes for the activity-asset command family.

The application facts remain their own domain models.  These root schemas
preserve their already-canonical JSON shapes at the operator boundary while
preventing an untyped application result from bypassing the CLI output gate.
"""

from __future__ import annotations

from pydantic import JsonValue

from ...core.json_contract import OutputRootSchema, OutputSchema


class ActivityAssetHistoryPayload(OutputRootSchema[dict[str, JsonValue]]):
    """Encrypted-history create and correction result."""


class ActivityAssetInspectionPayload(OutputSchema):
    """One immutable asset revision chain."""

    asset_id: str
    revisions: list[dict[str, JsonValue]]


class ActivityAssetForecastPayload(OutputRootSchema[dict[str, JsonValue]]):
    """One non-consuming, authority-backed schedule forecast."""


class ActivityAssetClaimPayload(OutputRootSchema[dict[str, JsonValue]]):
    """One explicit claim record or idempotent replay result."""


class ActivityAssetFilingHandoffPayload(OutputRootSchema[dict[str, JsonValue]]):
    """Non-consuming M130/M100 claim projections."""


__all__ = [
    "ActivityAssetClaimPayload",
    "ActivityAssetFilingHandoffPayload",
    "ActivityAssetForecastPayload",
    "ActivityAssetHistoryPayload",
    "ActivityAssetInspectionPayload",
]
