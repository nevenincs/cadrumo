"""Localized key descriptions that keep every binding a screen inherited.

A Textual screen's runtime binding table starts as a shallow copy of the
table its class hierarchy merged, so it already carries the keys
``Screen`` itself binds -- ``tab`` and ``shift+tab`` for focus movement,
``ctrl+c`` for copy -- alongside the keys the subclass declared.  Those
are the keyboard affordances every screen is supposed to get for free.

Replacing that table wholesale to attach translated descriptions silently
takes them away: the surface keeps the keys it named and loses the ones it
never had to name, so focus stops moving on a page whose focus chain is
perfectly healthy.  Re-describing the entries in place cannot, which is
what this module does.

The entry for a key is REPLACED by assignment rather than edited in place.
The instance's table shares the very lists the class table holds, so
mutating one re-describes that key for every screen of that class the
process opens; putting a new list in this instance's table cannot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from textual.binding import Binding, BindingsMap
from textual.dom import DOMNode

__all__ = ["localize_key_descriptions"]


def localize_key_descriptions(node: DOMNode, descriptions: Mapping[str, str]) -> None:
    """Re-describe ``node``'s already-bound actions in the operator's language.

    ``descriptions`` maps an action name to its footer text.  A description
    describes the action rather than the key, so two keys invoking one
    action are described once and stay in step.

    Keys the node did not ask about keep whatever description they carry,
    which is how the inherited bindings survive.  An action named here that
    nothing on this node binds raises: the mapping exists to translate a
    binding that is offered, so an action matching none of them is a typo
    or a binding that was removed, and both are worth failing on rather
    than silently translating nothing.
    """
    # Textual exposes no public re-description path: ``bind`` and ``BindingsMap.merge``
    # both APPEND, so either would offer a key once more on every call. The
    # dynamic reach is annotated so the map keeps its real type.
    bindings: BindingsMap = getattr(node, "_bindings")  # noqa: B009
    table = bindings.key_to_bindings
    described: set[str] = set()
    for key, bound in list(table.items()):
        if not any(binding.action in descriptions for binding in bound):
            continue
        table[key] = [
            _described(binding, descriptions[binding.action]) if binding.action in descriptions else binding
            for binding in bound
        ]
        described.update(binding.action for binding in bound if binding.action in descriptions)
    unbound = sorted(set(descriptions) - described)
    if unbound:
        message = f"no key on {type(node).__name__} binds: {', '.join(unbound)}"
        raise LookupError(message)
    node.refresh_bindings()


def _described(binding: Binding, description: str) -> Binding:
    """Attach ``description`` and let it decide whether the footer shows the key.

    Textual bakes ``show`` down to ``description and show`` when it merges a
    class's bindings, so a key declared with an empty description -- which is
    how a screen defers its wording to the operator's language -- arrives here
    already hidden.  Carrying that ``show`` forward would bind the key and
    leave it invisible, which is the reachability it exists to provide.  The
    same rule Textual applies decides it here: described keys show, and a
    caller wanting one bound and silent passes an empty description.
    """
    return replace(binding, description=description, show=bool(description))
