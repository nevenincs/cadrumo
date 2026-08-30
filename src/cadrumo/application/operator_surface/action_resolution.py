"""Resolve declared operator actions into fully materialised notice actions.

The application action catalogue owns stable action identities and the sources
that may provide their arguments.  The reconciled operator surface owns the
live command target and its required verb inputs.  This module joins those two
authorities before projecting a next action onto a successful notice.
"""

from __future__ import annotations

from ...core import ActionArgumentStatus
from ...core.json_contract import (
    ResolvedActionArgument,
    ResolvedActionReference,
    ResolvedNoticeAction,
)
from ..operator_actions import ActionArgumentBindingSpecification, ActionCatalogue, ActionReference
from .manifest import OperatorSurfaceReconciliation, ResolvedCatalogueAction


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

    argument_names = _validated_notice_bindings(argument_bindings)
    _validate_notice_binding_provenance(argument_bindings, declaration.argument_specifications)
    missing_required_names = _missing_required_notice_inputs(input_schema.required_input_names, argument_names)
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


def _validated_notice_bindings(bindings: tuple[ResolvedActionArgument, ...]) -> tuple[str, ...]:
    names = tuple(argument.argument_name for argument in bindings)
    if len(set(names)) != len(names):
        raise ValueError("notice action argument names must be unique")
    if any(argument.status is not ActionArgumentStatus.RESOLVED for argument in bindings):
        raise ValueError("success notice actions cannot carry unresolved argument bindings")
    return names


def _validate_notice_binding_provenance(
    bindings: tuple[ResolvedActionArgument, ...],
    specifications: tuple[ActionArgumentBindingSpecification, ...],
) -> None:
    for argument in bindings:
        _validate_notice_argument_provenance(argument, specifications)


def _validate_notice_argument_provenance(
    argument: ResolvedActionArgument,
    specifications: tuple[ActionArgumentBindingSpecification, ...],
) -> None:
    declared = _declared_notice_argument_specifications(argument, specifications)
    if not declared:
        raise ValueError(f"notice action argument is not declared by the catalogue: {argument.argument_name}")
    matching = tuple(
        specification for specification in declared if _notice_argument_matches_specification(argument, specification)
    )
    if len(matching) != 1:
        raise ValueError(f"notice action argument provenance does not match the catalogue: {argument.argument_name}")


def _declared_notice_argument_specifications(
    argument: ResolvedActionArgument,
    specifications: tuple[ActionArgumentBindingSpecification, ...],
) -> tuple[ActionArgumentBindingSpecification, ...]:
    return tuple(
        specification for specification in specifications if specification.argument_name == argument.argument_name
    )


def _notice_argument_matches_specification(
    argument: ResolvedActionArgument,
    specification: ActionArgumentBindingSpecification,
) -> bool:
    return (
        argument.source is not None
        and argument.source_key is not None
        and argument.source.value == specification.source.value
        and argument.source_key == specification.source_key
        and argument.source_evidence_id == specification.source_evidence_id
    )


def _missing_required_notice_inputs(required: tuple[str, ...], names: tuple[str, ...]) -> list[str]:
    return sorted(set(required) - set(names))


__all__ = [
    "resolve_catalogue_action",
    "resolve_notice_action",
]
