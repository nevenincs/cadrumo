"""Application-owned action outcome records."""

from __future__ import annotations

from ._catalogue import (
    OPERATOR_ACTION_CATALOGUE,
    ActionArgumentBindingSpecification,
    ActionCatalogue,
    ActionCatalogueEntry,
    build_action_catalogue,
    lookup_action,
    next_action,
)
from ._models import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    DeclaredNextAction,
    PreconditionVerdict,
)
from ._preconditions import (
    active_profile_pointer_repair_verdict,
    corrupt_active_profile_pointer_verdict,
    no_action_precondition_verdict,
)

__all__ = [
    "OPERATOR_ACTION_CATALOGUE",
    "ActionArgumentBinding",
    "ActionArgumentBindingSpecification",
    "ActionCatalogue",
    "ActionCatalogueEntry",
    "ActionReference",
    "ConditionEvidence",
    "DeclaredNextAction",
    "PreconditionVerdict",
    "active_profile_pointer_repair_verdict",
    "build_action_catalogue",
    "corrupt_active_profile_pointer_verdict",
    "lookup_action",
    "next_action",
    "no_action_precondition_verdict",
]
