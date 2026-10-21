"""Registered disclosure schema inventory for generic scope admission."""

from __future__ import annotations

from .registry import OperationPublicContractSetV1


def registered_disclosure_projections(contracts: OperationPublicContractSetV1) -> frozenset[str]:
    """Return public result, review, and workspace-refresh schema IDs."""
    return frozenset(
        schema.schema_id
        for contract in contracts.definitions
        for schema in (
            contract.result_schema,
            contract.review_projection_schema,
            contract.workspace_refresh_target_schema,
        )
        if schema is not None
    )
