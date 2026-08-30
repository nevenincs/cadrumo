"""Strict application records for machine-resolvable action outcomes."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import (
    ActionArgumentResolution,
    PreconditionActionIdentity,
    PreconditionEvidence,
    PreconditionOutcomeInvariant,
)
from ...core.operator_action_enums import ActionArgumentStatus


class ConditionEvidence(PreconditionEvidence):
    """Typed facts supporting a failed condition from one authority."""


class ActionReference(PreconditionActionIdentity):
    """Stable action identity; catalogue resolution is owned by a later layer."""


class ActionArgumentBinding(ActionArgumentResolution):
    """One recovery-action argument and the verdict data that can supply it."""


class PreconditionVerdict(
    PreconditionOutcomeInvariant[ConditionEvidence, ActionReference, ActionArgumentBinding],
):
    """Application-owned outcome for one failed precondition.

    The record identifies the rejected condition and evidence, then carries
    exactly one actionable recovery reference or an explicit closed
    no-recovery outcome.  It neither resolves an action catalogue nor embeds
    presentation text or an executable command.
    """


class DeclaredNextAction(BaseModel):
    """One catalogue action a producer names as the forward step after success.

    This is the success-path counterpart of :class:`PreconditionVerdict` and is
    deliberately a separate record: nothing failed, so there is no rejected
    condition, no evidence, no conditionality axis and no closed no-recovery
    outcome to state.  What remains is the stable action identity plus the
    concrete arguments the producer can already supply from its own outcome.

    The record carries no command string, no CLI path and no presentation text.
    Catalogue lookup, live-command resolution and required-input coverage stay
    with the operator-surface projection, which refuses a declaration whose
    target cannot supply every live required input - so a producer can never
    make an unexecutable step look executable.

    Producers across packages share this one record rather than each defining a
    local "next command" carrier, which is how divergent command prose entered
    the tree in the first place.
    """

    model_config = _STRICT_FROZEN

    action: ActionReference
    argument_bindings: tuple[ActionArgumentBinding, ...] = ()

    @field_validator("argument_bindings")
    @classmethod
    def _require_concrete_unique_arguments(
        cls,
        value: tuple[ActionArgumentBinding, ...],
    ) -> tuple[ActionArgumentBinding, ...]:
        """Refuse a duplicated or unresolved argument on a forward action."""
        names = tuple(item.argument_name for item in value)
        if len(set(names)) != len(names):
            raise ValueError("declared next-action argument names must be unique")
        if any(item.status is not ActionArgumentStatus.RESOLVED for item in value):
            raise ValueError("declared next actions require fully resolved argument bindings")
        return tuple(sorted(value, key=lambda item: item.argument_name))


__all__ = [
    "ActionArgumentBinding",
    "ActionReference",
    "ConditionEvidence",
    "DeclaredNextAction",
    "PreconditionVerdict",
]
