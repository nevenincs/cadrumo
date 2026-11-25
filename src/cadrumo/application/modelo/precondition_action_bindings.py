"""Argument and alternative-action binding for modelo precondition verdicts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
)
from ..operator_actions.catalogue import lookup_action
from ..operator_actions.models import (
    ActionArgumentBinding,
    ActionReference,
    AlternativeRecoveryAction,
)
from ..operator_surface.models import ManifestActionProfile


@dataclass(frozen=True, slots=True)
class AlternativeActionArguments:
    """The facts one declared alternative action binds, and the arguments only the operator supplies."""

    action_id: str
    action_argument_values: Mapping[str, str | int | bool | Decimal]
    missing_action_arguments: tuple[str, ...] = ()


def recovery_conditionality(
    declared_action_id: str | None, missing_action_arguments: tuple[str, ...]
) -> ActionConditionality:
    """Derive conditionality from whether an action is declared and the operator still owes arguments."""
    if declared_action_id is None:
        return ActionConditionality.NOT_APPLICABLE
    if missing_action_arguments:
        return ActionConditionality.REQUIRES_ARGUMENTS
    return ActionConditionality.IMMEDIATE


def alternative_recovery_actions(
    profile: ManifestActionProfile,
    alternative_actions: tuple[AlternativeActionArguments, ...],
) -> tuple[AlternativeRecoveryAction, ...]:
    """Bind each declared alternative in its declared order, refusing any other set."""
    declared = tuple(item.action_id for item in profile.alternative_actions)
    if tuple(item.action_id for item in alternative_actions) != declared:
        raise ValueError("modelo precondition failure alternative actions contradict their declaration")
    return tuple(
        AlternativeRecoveryAction(
            action=ActionReference(action_id=item.action_id),
            argument_bindings=action_argument_bindings(
                item.action_id, item.action_argument_values, item.missing_action_arguments
            ),
            missing_argument_names=item.missing_action_arguments,
            conditionality=recovery_conditionality(item.action_id, item.missing_action_arguments),
        )
        for item in alternative_actions
    )


def action_argument_bindings(
    declared_action_id: str | None,
    action_argument_values: Mapping[str, str | int | bool | Decimal] | None,
    missing_action_arguments: tuple[str, ...],
) -> tuple[ActionArgumentBinding, ...]:
    """Bind resolved and missing arguments, requiring exact coverage of the catalogue declaration."""
    if declared_action_id is None:
        if missing_action_arguments:
            raise ValueError("modelo precondition failure without an action cannot name missing arguments")
        return ()
    declaration = lookup_action(declared_action_id)
    values = action_argument_values or {}
    missing = set(missing_action_arguments)
    declared_names = {item.argument_name for item in declaration.argument_specifications}
    if (
        len(missing) != len(missing_action_arguments)
        or missing & set(values)
        or set(values) | missing != declared_names
    ):
        raise ValueError("modelo action argument values must exactly match the catalogue declaration")
    return (
        *(
            ActionArgumentBinding(
                argument_name=name,
                status=ActionArgumentStatus.RESOLVED,
                value=value,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=name,
            )
            for name, value in values.items()
        ),
        *(
            ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING)
            for name in missing_action_arguments
        ),
    )
