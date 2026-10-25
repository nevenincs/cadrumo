"""The closed set of setup items every surface names, in setup order.

The native component engine owns each item's state, plan and setup. Python
surfaces only render what the engine reports, so they need what an item is
called and which recovery action sets it up: the declarations here. The set
is closed, so a new outside dependency cannot appear on one surface only.
"""

from __future__ import annotations

from typing import Final

from .dependency_contracts import DependencyItemDeclaration, DependencyItemKind

__all__ = ["BROWSER_DECLARATION", "LOCAL_AI_DECLARATION", "dependency_item_declarations"]

BROWSER_DECLARATION: Final = DependencyItemDeclaration(
    item_id=DependencyItemKind.BROWSER.value,
    kind=DependencyItemKind.BROWSER,
    display_key="provisioning.dependency.browser.name",
    recovery_action_id="operator.provision.browser",
)

LOCAL_AI_DECLARATION: Final = DependencyItemDeclaration(
    item_id=DependencyItemKind.LOCAL_AI.value,
    kind=DependencyItemKind.LOCAL_AI,
    display_key="provisioning.dependency.local_ai.name",
    recovery_action_id="operator.provision.local_ai",
)


def dependency_item_declarations() -> tuple[DependencyItemDeclaration, ...]:
    """Return every setup item in setup order: the browser, then the local AI."""
    return (BROWSER_DECLARATION, LOCAL_AI_DECLARATION)
