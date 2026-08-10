"""Strict application records for machine-resolvable action outcomes."""

from __future__ import annotations

from ...core import (
    ActionArgumentResolution,
    PreconditionActionIdentity,
    PreconditionEvidence,
    PreconditionOutcomeInvariant,
)


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


__all__ = [
    "ActionArgumentBinding",
    "ActionReference",
    "ConditionEvidence",
    "PreconditionVerdict",
]
