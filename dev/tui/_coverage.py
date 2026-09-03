"""Which rendered surface puts which interface class on screen.

The inventory is derived by reading the source tree, and the surface list is
answered by the harness; neither knows about the other. This module is the
join, and it is the one hand-written table in the package -- because the fact
it records, "opening the registration surface paints RegistrationScreen", is a
statement about what the harness builds, and a development tool forbidden
from importing the TUI cannot observe that from outside.

What keeps a hand-written table honest is that it is checked, not trusted.
Every qualname here must exist in the AST inventory and every surface name
must exist in the harness listing, so a rename breaks the check rather than
quietly turning a covered interface into an uncovered one. Nothing here
excuses an interface from coverage: an interface absent from this table is
reported as NOT RENDERED, which is a gap to close rather than a state to
declare acceptable.
"""

from __future__ import annotations

from typing import Final

from ._inventory import Interface

RENDERED_BY: Final[dict[str, tuple[str, ...]]] = {
    "registration": (
        "cadrumo.entrypoints.tui.secret.registration.RegistrationScreen",
        "cadrumo.entrypoints.tui.secret.credentials.CredentialScreen",
    ),
    "login": (
        "cadrumo.entrypoints.tui.secret.login.LoginScreen",
        "cadrumo.entrypoints.tui.secret.credentials.CredentialScreen",
    ),
    "manager": ("cadrumo.entrypoints.tui.profile.overview.ProfileManagerScreen",),
    "status": ("cadrumo.entrypoints.tui.profile.status.StatusScreen",),
    "form": (
        "cadrumo.entrypoints.tui.components.form_screen.FormApp",
        "cadrumo.entrypoints.tui.components.form_screen.FormScreen",
    ),
    # The question view this surface opens on is a pane rather than a screen, so
    # it is not an interface in the inventory's vocabulary and cannot be named
    # here. One entry is the whole of what this surface paints.
    "modelo-work-wizard": ("cadrumo.entrypoints.tui.flows.app.FlowScreen",),
}
"""Surface name to the interface classes opening it paints.

Only the classes a surface paints at its OPENING frame are listed. A screen
reached by pressing a key -- the flow review screen, a confirm dialog, a
field-edit modal -- is genuinely not rendered by this run, and claiming it
here would make the coverage report lie in the one direction that matters.
"""

NOTES: Final[dict[str, str]] = {
    "cadrumo.entrypoints.tui.secret.credentials.CredentialScreen": (
        "generic base; painted through its subclasses rather than on its own"
    ),
}
"""Why a particular interface reads the way it does in the report.

A note explains a reading; it never suppresses one. An interface with a note
is still counted exactly as covered or uncovered as the table makes it.
"""


class CoverageError(RuntimeError):
    """The coverage table disagrees with the inventory or the harness."""


def check(interfaces: tuple[Interface, ...], surfaces: tuple[str, ...]) -> None:
    """Refuse a coverage table that has drifted from what actually exists.

    Run before a render rather than after, so a stale table is a refusal with
    a name in it instead of a report that quietly under-claims coverage.
    """
    known = {interface.qualname for interface in interfaces}
    problems = [f"coverage names unknown surface {surface!r}" for surface in RENDERED_BY if surface not in surfaces]
    problems.extend(
        f"coverage maps {surface!r} to unknown interface {qualname!r}"
        for surface, qualnames in RENDERED_BY.items()
        for qualname in qualnames
        if qualname not in known
    )
    problems.extend(f"note describes unknown interface {qualname!r}" for qualname in NOTES if qualname not in known)
    if problems:
        raise CoverageError("; ".join(problems))


def rendered_by(qualname: str, surfaces: tuple[str, ...]) -> tuple[str, ...]:
    """Which of ``surfaces`` paint the interface named ``qualname``."""
    return tuple(surface for surface in surfaces if qualname in RENDERED_BY.get(surface, ()))


__all__ = ["NOTES", "RENDERED_BY", "CoverageError", "check", "rendered_by"]
