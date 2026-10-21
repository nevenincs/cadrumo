"""Bind profile and tax value disclosure to the projection an action releases."""

from __future__ import annotations

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, DisclosureCategory, DisclosurePermission

from ..user_profile.access_errors import ProfileAccessRefusedError
from .access_resolution import OperationAccessContext

_PROJECTION_ACTIONS = frozenset({AccessAction.RESULT, AccessAction.REVIEW, AccessAction.RESPOND})


def profile_and_tax_value_projection_disclosures(
    context: OperationAccessContext,
    otherwise: frozenset[DisclosurePermission],
    /,
) -> frozenset[DisclosurePermission]:
    """Permit profile and tax values only to the result or review projection the action releases.

    Any other action keeps ``otherwise``. A releasing action whose contract
    declares no such projection is refused as unavailable.
    """
    if context.action not in _PROJECTION_ACTIONS:
        return otherwise
    schema = (
        context.contract.result_schema
        if context.action is AccessAction.RESULT
        else context.contract.review_projection_schema
    )
    if schema is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return frozenset(
        DisclosurePermission(destination_id=context.destination_id, projection_id=schema.schema_id, category=category)
        for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
    )
