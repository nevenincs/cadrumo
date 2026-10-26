"""Which reviewable element a rendered surface shows, and in which state.

A full render writes well over a thousand frames, but most of them are the
same element seen again: one screen in each of its states, at every viewport,
under both appearances. A reviewer judges the element -- does the ledger
overview hold up empty, stale and unavailable, narrow and wide, dark and
light -- so notes and sign-offs are kept per element, and the frames are the
evidence gathered under it.

The harness registries compose every surface name from typed parts, and this
module reads the parts back:

- a workbench fixture is ``<surface>--<scenario>``, the fixture's own
  ``fixture_id``: the element is the surface, the state its scenario;
- a sequence page is ``seq-<sequence>--<page>``: the element is the page, and
  the documentation sequence whose declaration it shows is the state;
- any other surface is a screen with a single state, named by itself.

The review server reads names off the run directory while a render is still
writing it, so it cannot import those registries -- they build the TUI, and a
peer's half-finished edit would take the server down with them. This package's
tests hold the parse to the live registries instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Final

from dev._paths import UTF_8

STATE_SEPARATOR: Final[str] = "--"
SEQUENCE_PREFIX: Final[str] = "seq-"

FIXTURE_STATE_ORDER: Final[tuple[str, ...]] = (
    "ready",
    "empty",
    "stale",
    "unavailable",
    "blocked",
    "refusal",
    "failure",
)
"""The workbench fixture scenarios in the order the fixture registry declares
them, from the ordinary state to the failing ones. Only presentation order
depends on it; the join to the registry's vocabulary is asserted by this
package's tests, so a new scenario cannot be left out unnoticed."""


class ElementFamily(StrEnum):
    """How an element's states are built, which decides how its surface names read."""

    FIXTURE = "fixture"
    """A production surface over an in-memory fixture, one scenario per state."""

    SEQUENCE = "sequence"
    """A Modelo page over a declaration a documentation sequence built, one sequence per state."""

    SCREEN = "screen"
    """A surface with a single state."""


@dataclass(frozen=True)
class SurfaceParts:
    """The element a surface shows and the state it shows it in."""

    family: ElementFamily
    name: str
    """The element's own name: the fixture surface, the sequence page, or the screen."""
    state: str | None
    """The state this surface shows; ``None`` for a single-state screen."""

    @property
    def element(self) -> str:
        """The element's key, unique across families; notes and sign-offs are filed under it."""
        return element_key(self.family, self.name)


def element_key(family: ElementFamily, name: str) -> str:
    """The key an element is filed under: its family and name, which never contain the colon."""
    return f"{family}:{name}"


def parse_surface(surface: str) -> SurfaceParts:
    """Read a surface name back into its element and state.

    Split at the last separator: sequence ids and page names use single
    hyphens, and a fixture's surface id may too, but none contains the
    separator itself.
    """
    head, separator, tail = surface.rpartition(STATE_SEPARATOR)
    if not separator or not head or not tail:
        return SurfaceParts(family=ElementFamily.SCREEN, name=surface, state=None)
    if head.startswith(SEQUENCE_PREFIX) and len(head) > len(SEQUENCE_PREFIX):
        return SurfaceParts(family=ElementFamily.SEQUENCE, name=tail, state=head.removeprefix(SEQUENCE_PREFIX))
    return SurfaceParts(family=ElementFamily.FIXTURE, name=head, state=tail)


def state_order(family: ElementFamily, state: str | None) -> tuple[int, str]:
    """Where a state sorts within its element: fixture scenarios by the registry, the rest by name."""
    if state is None:
        return 0, ""
    if family is ElementFamily.FIXTURE and state in FIXTURE_STATE_ORDER:
        return FIXTURE_STATE_ORDER.index(state), state
    return len(FIXTURE_STATE_ORDER), state


def element_digest(frames: Mapping[str, str]) -> str:
    """One digest for every image an element holds, by frame key.

    It moves when any frame is re-rendered, added or removed, so a sign-off
    or note anchored to it stops describing the element the moment any of
    its pixels do.
    """
    lines = "".join(f"{key}\t{digest}\n" for key, digest in sorted(frames.items()))
    return sha256(lines.encode(UTF_8)).hexdigest()


__all__ = [
    "FIXTURE_STATE_ORDER",
    "SEQUENCE_PREFIX",
    "STATE_SEPARATOR",
    "ElementFamily",
    "SurfaceParts",
    "element_digest",
    "element_key",
    "parse_surface",
    "state_order",
]
