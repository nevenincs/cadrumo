"""A structural error in the declared work-form layout."""

from __future__ import annotations

from typing import override

from ...core.errors.hierarchy import InternalInvariantError
from ..operator_actions.invariant_verdicts import internal_invariant_verdict
from ..operator_actions.models import PreconditionVerdict


class ModeloWorkFormLayoutError(InternalInvariantError):
    """A declared layout does not account for every casilla exactly once.

    The layout is registry-authored, so no command of the operator repairs it:
    the refusal carries the terminal verdict of that invariant at class level.
    """

    @property
    @override
    def terminal_precondition_verdict(self) -> PreconditionVerdict:
        """Expose the terminal verdict of the work-form layout invariant."""
        carried = super().terminal_precondition_verdict
        if isinstance(carried, PreconditionVerdict):
            return carried
        return internal_invariant_verdict("work_form.layout_accounts_every_casilla")
