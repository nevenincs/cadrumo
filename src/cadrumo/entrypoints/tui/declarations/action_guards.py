"""One home for the Declarations workspace's injected-action checks.

The route factory and the workspace controller each validated the same three
read actions against the same canonical command keys, in two copies that were
byte-identical and therefore looked safe. The Ledger workspace carried exactly
that shape until its two copies drifted — the factory refused a non-canonical
review action while the controller checked nothing — and every caller building
the controller directly skipped the refusal. This consolidation is the same
remedy applied before the same divergence happens here.

What the guard prevents is not a crash. An action wired to another command
gives the workspace an affordance labelled for one operation that dispatches
another, so an operator reading their declarations could run a different
application door than the one the screen names.
"""

from __future__ import annotations

from typing import Final

from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference

#: Injected action attribute -> the command key it must resolve to. All three
#: are mandatory: the Declarations workspace offers no partial read surface, so
#: unlike the Ledger guard there is no "absent means not offered" state here.
REQUIRED_DECLARATIONS_TARGETS: Final[tuple[tuple[str, str], ...]] = (
    ("work_action", "modelo.work.list"),
    ("revisions_action", "modelo.work.revisions"),
    ("filing_action", "modelo.filing_record.list"),
)

_REFUSAL: Final[str] = "injected Declarations read action resolves to another application door"


def require_canonical_declarations_actions(
    *,
    work_action: ActionReference,
    revisions_action: ActionReference,
    filing_action: ActionReference,
) -> None:
    """Refuse an injected read action that does not resolve to its canonical command.

    Args:
        work_action: The work-unit list action.
        revisions_action: The work-unit revisions action.
        filing_action: The filing-record list action.

    Raises:
        ValueError: If any supplied action resolves to a different command.
    """
    supplied = {
        "work_action": work_action,
        "revisions_action": revisions_action,
        "filing_action": filing_action,
    }
    for attribute, command_key in REQUIRED_DECLARATIONS_TARGETS:
        if lookup_action(supplied[attribute].action_id).target_command_key != command_key:
            raise ValueError(_REFUSAL)


__all__ = ["REQUIRED_DECLARATIONS_TARGETS", "require_canonical_declarations_actions"]
