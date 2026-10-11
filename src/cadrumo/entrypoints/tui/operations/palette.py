"""Offer every registered operation in the command palette.

A hit only navigates: choosing one opens the Operations destination on that
operation's request form, where the person enters and submits the request.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import override

from textual.command import Hit, Hits, Provider

from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..navigation import TuiFocusIdentityV1, TuiNavigationTargetV1
from ..search import TuiSearchHostV1
from .catalogue import OperationCatalogueEntryV1, OperationCatalogueSourceV1
from .destination import OPERATION_FOCUS_KEY, OPERATIONS_DESTINATION, OperationsDestinationV1


def operation_navigation_target(entry: OperationCatalogueEntryV1) -> TuiNavigationTargetV1:
    """Return the navigation target that opens the destination on ``entry``."""
    return TuiNavigationTargetV1(
        destination=OPERATIONS_DESTINATION,
        focus=TuiFocusIdentityV1(
            destination=OPERATIONS_DESTINATION,
            semantic_key=OPERATION_FOCUS_KEY,
            restore_token=entry.focus_token,
        ),
    )


def _offered_source(host: TuiSearchHostV1) -> OperationCatalogueSourceV1 | None:
    """Return the catalogue door of the admitted Operations destination, when it is offered."""
    try:
        route = host.destination_catalogue.resolve(OPERATIONS_DESTINATION)
    except CadrumoError:
        return None
    factory = route.factory
    return factory.source if isinstance(factory, OperationsDestinationV1) else None


class WorkbenchOperationProviderV1(Provider):
    """Match a typed query against every registered operation's identity and description."""

    @override
    async def search(self, query: str) -> Hits:
        """Yield the registered operations the query matches."""
        host = self.app
        if not isinstance(host, TuiSearchHostV1):
            return
        source = _offered_source(host)
        if source is None:
            return
        try:
            catalogue = await asyncio.to_thread(source.load)
        except Exception:  # a registry that cannot compose offers nothing; the destination says why
            return
        matcher = self.matcher(query)
        for entry in catalogue.entries:
            text = entry.definition_id if not entry.summary else f"{entry.definition_id}  {entry.summary}"
            if (score := matcher.match(text)) > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(text),
                    command=_navigation_command(host.navigate_to, operation_navigation_target(entry)),
                    text=text,
                    help=tr("tui.operations.palette.help"),
                )


def _navigation_command(
    navigate_to: Callable[[TuiNavigationTargetV1], None], target: TuiNavigationTargetV1
) -> Callable[[], None]:
    def navigate() -> None:
        navigate_to(target)

    return navigate


__all__ = ["WorkbenchOperationProviderV1", "operation_navigation_target"]
