"""Resolve an application verdict into the recovery action an operator is shown.

A verdict names a catalogue action and binds its arguments. What an operator
is shown also names the command that action targets, by its canonical path.
This module is the one projection from the first to the second: it joins the
catalogue's declaration to the reconciled command leaf, refuses bindings that
contradict the declaration, and builds the wire record.

The command leaf is read through :class:`ActionTargetReconciliation`, because
the command surface belongs to the process that composes it. A process that
holds the command graph reconciles the leaf from the graph. A process that
does not reconciles it from the recorded action targets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ...core.json_contract import (
    ActionConditionEvidence,
    ResolvedActionArgument,
    ResolvedActionReference,
    ResolvedPreconditionAction,
)
from ...core.operator_action_enums import ActionArgumentStatus

if TYPE_CHECKING:
    from ..operator_actions.catalogue import ActionArgumentBindingSpecification
    from ..operator_actions.models import ActionArgumentBinding, PreconditionVerdict
    from .manifest import OperatorSurfaceReconciliation

__all__ = ["ActionTargetReconciliation", "resolve_precondition_action"]


class ActionTargetReconciliation(Protocol):
    """Reconcile the one command leaf that owns a command key."""

    def __call__(self, command_key: str, /) -> OperatorSurfaceReconciliation:
        """Return the reconciliation of that leaf alone.

        Raises:
            LookupError: No command owns ``command_key``.
        """
        ...


def resolve_precondition_action(
    verdict: PreconditionVerdict, *, target_reconciliation: ActionTargetReconciliation
) -> ResolvedPreconditionAction:
    """Schema-resolve one application verdict against the action catalogue and its target leaf.

    Both immediate refusal envelopes and persisted workflow history use this
    projection, so neither path can reconstruct recovery prose or disagree
    about missing bindings.
    """
    return ResolvedPreconditionAction(
        failed_condition_id=verdict.failed_condition_id,
        evidence=tuple(
            ActionConditionEvidence(
                condition_id=item.condition_id,
                evidence_id=item.evidence_id,
                provenance=item.provenance,
                values=item.values,
            )
            for item in verdict.evidence
        ),
        action=_resolve_action_reference(verdict, target_reconciliation),
        argument_bindings=tuple(
            ResolvedActionArgument(
                argument_name=item.argument_name,
                status=item.status,
                value=item.value,
                source=item.source,
                source_key=item.source_key,
                source_evidence_id=item.source_evidence_id,
            )
            for item in verdict.argument_bindings
        ),
        missing_argument_names=verdict.missing_argument_names,
        conditionality=verdict.conditionality,
        no_recovery_outcome=verdict.no_recovery_outcome,
    )


def _resolve_action_reference(
    verdict: PreconditionVerdict, target_reconciliation: ActionTargetReconciliation
) -> ResolvedActionReference | None:
    """Resolve the optional verdict recovery action against its reconciled target."""
    action = verdict.action
    if action is None:
        return None
    # The catalogue is loaded only when a verdict carries an action to resolve.
    from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
    from .action_resolution import resolve_catalogue_action

    resolution = resolve_catalogue_action(
        action=action,
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=target_reconciliation(OPERATOR_ACTION_CATALOGUE.lookup(action.action_id).target_command_key),
    )
    declaration = resolution.declaration
    if resolution.target_leaf.input_schema is None:
        raise ValueError(
            f"CLI policy action target has no live input schema: {declaration.target_command_key}",
        )
    _validate_action_bindings(
        action_id=action.action_id,
        specifications=declaration.argument_specifications,
        argument_bindings=verdict.argument_bindings,
    )
    return ResolvedActionReference(
        action_id=declaration.action_id,
        target_command_key=declaration.target_command_key,
        cli_path=resolution.target_leaf.live_leaf.canonical_cli_path,
    )


def _validate_action_bindings(
    *,
    action_id: str,
    specifications: tuple[ActionArgumentBindingSpecification, ...],
    argument_bindings: tuple[ActionArgumentBinding, ...],
) -> None:
    """Require verdict bindings to account for the declared action arguments."""
    specifications_by_name: dict[str, list[ActionArgumentBindingSpecification]] = {}
    for specification in specifications:
        specifications_by_name.setdefault(specification.argument_name, []).append(specification)
    observed_arguments = {item.argument_name: item for item in argument_bindings}
    if set(observed_arguments) != set(specifications_by_name):
        raise ValueError(f"CLI policy action arguments do not match catalogue declaration: {action_id}")
    for name, argument in observed_arguments.items():
        if argument.status is ActionArgumentStatus.MISSING:
            continue
        matching_specifications = tuple(
            specification
            for specification in specifications_by_name[name]
            if argument.source is specification.source
            and argument.source_key == specification.source_key
            and argument.source_evidence_id == specification.source_evidence_id
        )
        if len(matching_specifications) != 1:
            raise ValueError(f"CLI policy action argument source contradicts catalogue: {name}")
