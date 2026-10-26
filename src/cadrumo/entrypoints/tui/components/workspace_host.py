"""The contract a root shell satisfies so a workspace can replace its own body.

A workspace destination is one screen pushed by the root, but the workspace
itself is several screens: an overview plus the internal areas its navigation
table lists.  Moving between those areas is the workspace's own concern, not
the root's -- the root admits destinations and owns the return journey, and
``navigation`` states that it must not import a concrete destination screen.

That leaves the workspace holding the knowledge (its controller and its pure
route resolver) and the root holding the capability (the screen stack).  This
module is the seam between them: the workspace resolves its own next body and
hands the finished screen to whatever host it is running under, and the host
swaps it without ever naming a workspace type.

The seam matters because there is more than one host.  Production runs under
the root shell; the development harness and the single-surface entry points
run under a one-screen host that has no stack to swap.  ``replace_workspace_body``
reports whether the swap happened so a screen under the simpler host degrades
to its existing standalone behaviour instead of failing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from textual.app import App
    from textual.screen import Screen


@runtime_checkable
class WorkspaceBodyHostV1(Protocol):
    """A host that can replace the active workspace body with another screen."""

    def replace_workspace_body(self, screen: Screen[None], /) -> None:
        """Mount ``screen`` in place of the workspace body currently shown."""


def replace_workspace_body(app: App[object], screen: Screen[None], /) -> bool:
    """Ask the running host to show ``screen`` as the workspace body.

    Returns ``True`` when a host accepted the swap and ``False`` when the
    running host does not offer one.  The boolean is the honest answer rather
    than a raised error: a screen opened standalone under the single-screen
    host has no body to replace, and that is a supported way to run a surface,
    not a defect.

    Args:
        app: The application the requesting screen is mounted under.
        screen: The already-resolved replacement body.

    Returns:
        Whether the host performed the replacement.
    """
    if not isinstance(app, WorkspaceBodyHostV1):
        return False
    app.replace_workspace_body(screen)
    return True


__all__ = ["WorkspaceBodyHostV1", "replace_workspace_body"]
