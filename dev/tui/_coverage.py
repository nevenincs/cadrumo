"""Derive TUI interface coverage from source structure and the live fixture registry.

There is no review-status catalogue here. The source inventory discovers
interfaces, the harness reports what each executable surface paints, and this
module joins those two live facts. A concrete leaf class absent from the join is
unrendered; a class extended by another interface is structural substrate.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._inventory import Interface


class CoverageError(RuntimeError):
    """The fixture registry disagrees with the source inventory."""


def check(
    interfaces: tuple[Interface, ...],
    surfaces: tuple[str, ...],
    *,
    rendered_table: Mapping[str, tuple[str, ...]],
) -> None:
    """Refuse registry entries that name no live surface or interface."""
    known_interfaces = {interface.qualname for interface in interfaces}
    known_surfaces = set(surfaces)
    problems = [
        f"coverage names unknown surface {surface!r}"
        for surface in rendered_table
        if surface not in known_surfaces
    ]
    problems.extend(
        f"coverage maps {surface!r} to unknown interface {qualname!r}"
        for surface, qualnames in rendered_table.items()
        for qualname in qualnames
        if qualname not in known_interfaces
    )
    if problems:
        raise CoverageError("; ".join(problems))


def rendered_by(
    qualname: str,
    surfaces: tuple[str, ...],
    *,
    rendered_table: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    """Return the executable surfaces whose registry names ``qualname``."""
    return tuple(surface for surface in surfaces if qualname in rendered_table.get(surface, ()))


def unrendered(
    interfaces: tuple[Interface, ...],
    surfaces: tuple[str, ...],
    *,
    rendered_table: Mapping[str, tuple[str, ...]],
) -> tuple[Interface, ...]:
    """Return concrete leaf interfaces no executable surface paints."""
    check(interfaces, surfaces, rendered_table=rendered_table)
    return tuple(
        interface
        for interface in interfaces
        if not interface.is_base
        and not rendered_by(interface.qualname, surfaces, rendered_table=rendered_table)
    )


def notes(
    interfaces: tuple[Interface, ...],
    surfaces: tuple[str, ...],
    *,
    rendered_table: Mapping[str, tuple[str, ...]],
) -> dict[str, str]:
    """Describe only the structural result derived for each interface."""
    check(interfaces, surfaces, rendered_table=rendered_table)
    return {
        interface.qualname: (
            "structural base"
            if interface.is_base
            else "rendered"
            if rendered_by(interface.qualname, surfaces, rendered_table=rendered_table)
            else "not rendered"
        )
        for interface in interfaces
    }


__all__ = ["CoverageError", "check", "notes", "rendered_by", "unrendered"]
