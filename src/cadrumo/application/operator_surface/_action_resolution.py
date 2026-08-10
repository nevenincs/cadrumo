"""Resolve declared operator actions into fully materialised notice actions.

The application action catalogue owns stable action identities and the sources
that may provide their arguments.  The reconciled operator surface owns the
live command target and its required S05 inputs.  This module joins those two
authorities before projecting a next action onto a successful notice.
"""

from __future__ import annotations

from ...core import ActionArgumentStatus
from ...core.json_contract import (
    ResolvedActionArgument,
    ResolvedActionReference,
    ResolvedNoticeAction,
)
from ..operator_actions import ActionCatalogue, ActionReference
from ._manifest import OperatorSurfaceReconciliation, ResolvedCatalogueAction


def resolve_catalogue_action(
    *,
    action: ActionReference,
    catalogue: ActionCatalogue,
    reconciliation: OperatorSurfaceReconciliation,
) -> ResolvedCatalogueAction:
    """Resolve one declared action against its reconciled live command target."""
    declaration = catalogue.lookup(action.action_id)
    targets = tuple(
        leaf for leaf in reconciliation.leaves if leaf.live_leaf.subject_leaf_key == declaration.target_command_key
    )
    if len(targets) != 1:
        raise ValueError(
            f"operator action target must resolve exactly once: {declaration.action_id} -> "
            f"{declaration.target_command_key}",
        )
    return ResolvedCatalogueAction(declaration=declaration, target_leaf=targets[0])


def resolve_notice_action(
    *,
    action: ActionReference,
    argument_bindings: tuple[ResolvedActionArgument, ...],
    catalogue: ActionCatalogue,
    reconciliation: OperatorSurfaceReconciliation,
) -> ResolvedNoticeAction:
    """Build a success-notice action only when all required inputs are concrete.

    The resolver never serialises a partial action.  A producer value must map
    to exactly one catalogue source specification, retain that specification's
    provenance, and cover every required name declared by the live input
    schema.  Optional declared arguments may be omitted, but undeclared or
    unresolved producer arguments always refuse.
    """
    resolved_catalogue_action = resolve_catalogue_action(
        action=action,
        catalogue=catalogue,
        reconciliation=reconciliation,
    )
    declaration = resolved_catalogue_action.declaration
    input_schema = resolved_catalogue_action.target_leaf.input_schema
    assert input_schema is not None

    argument_names = tuple(argument.argument_name for argument in argument_bindings)
    if len(set(argument_names)) != len(argument_names):
        raise ValueError("notice action argument names must be unique")
    if any(argument.status is not ActionArgumentStatus.RESOLVED for argument in argument_bindings):
        raise ValueError("success notice actions cannot carry unresolved argument bindings")

    for argument in argument_bindings:
        specifications = tuple(
            specification
            for specification in declaration.argument_specifications
            if specification.argument_name == argument.argument_name
        )
        if not specifications:
            raise ValueError(
                f"notice action argument is not declared by the catalogue: {argument.argument_name}",
            )
        assert argument.source is not None
        assert argument.source_key is not None
        matching_specifications = tuple(
            specification
            for specification in specifications
            if argument.source.value == specification.source.value
            and argument.source_key == specification.source_key
            and argument.source_evidence_id == specification.source_evidence_id
        )
        if len(matching_specifications) != 1:
            raise ValueError(
                f"notice action argument provenance does not match the catalogue: {argument.argument_name}",
            )

    missing_required_names = sorted(set(input_schema.required_input_names) - set(argument_names))
    if missing_required_names:
        raise ValueError(
            f"success notice action is missing required input bindings for "
            f"{declaration.target_command_key}: {', '.join(missing_required_names)}",
        )

    return ResolvedNoticeAction(
        action=ResolvedActionReference(
            action_id=declaration.action_id,
            target_command_key=declaration.target_command_key,
        ),
        argument_bindings=argument_bindings,
    )


__all__ = [
    "resolve_catalogue_action",
    "resolve_notice_action",
]
