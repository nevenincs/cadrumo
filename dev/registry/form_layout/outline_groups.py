"""Navigation outlines a reviewer declares over a generated layout's sections.

A generated layout is navigated by its pages. Where those pages are containers
of the design rather than parts a filer recognises (Renta's dictionaries split
one return into a results container and a data-entry container), a reviewer
groups the revision's sections by subject in ``outline_groups.toml``. The
generator copies the outline onto the revision's layout, where the layout's own
validator refuses one that invents, repeats or leaves out a section.

An outline names each section as ``page/section`` by the layout's own ids, so
an outline written for one revision applies to no other: section ids are
positional in a design and can mean different parts in another edition.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

from cadrumo.core.toml import load_toml
from cadrumo.domain.calculations.registry.schema_form_layouts import FormOutlineGroup, FormOutlineSection

from .page_sections import form_heading_key

__all__ = [
    "OUTLINE_GROUPS",
    "OutlineGroupRefusedError",
    "OutlineGroups",
    "read_outline_groups",
]

OUTLINE_GROUPS: Final[Path] = Path(__file__).with_name("outline_groups.toml")


class OutlineGroupRefusedError(ValueError):
    """An outline declaration that cannot be read as one outline per revision."""


@dataclass(frozen=True, slots=True)
class OutlineGroups:
    """Every declared outline, keyed by ``(modelo, revision)``."""

    outlines: Mapping[tuple[str, str], tuple[FormOutlineGroup, ...]]

    def for_revision(self, modelo: str, revision: str) -> tuple[FormOutlineGroup, ...]:
        """The outline declared for one revision's layout, or none."""
        return self.outlines.get((modelo, revision), ())


def _section(modelo: str, revision: str, value: object) -> FormOutlineSection:
    if not isinstance(value, str) or value.count("/") != 1:
        raise OutlineGroupRefusedError(f"{modelo} {revision}: outline section {value!r} is not 'page/section'")
    page_id, section_id = value.split("/")
    return FormOutlineSection(page_id=page_id, section_id=section_id)


def _group(modelo: str, revision: str, entry: object) -> FormOutlineGroup:
    if not isinstance(entry, Mapping):
        raise OutlineGroupRefusedError(f"{modelo} {revision}: outline group {entry!r} is not a table")
    group_id = entry.get("id")
    sections = entry.get("sections")
    if not isinstance(group_id, str) or not isinstance(sections, list):
        raise OutlineGroupRefusedError(f"{modelo} {revision}: outline group {entry!r} needs an id and sections")
    return FormOutlineGroup(
        id=group_id,
        heading_key=form_heading_key(modelo, "outline", group_id),
        sections=tuple(_section(modelo, revision, item) for item in sections),
    )


@cache
def read_outline_groups(path: Path = OUTLINE_GROUPS) -> OutlineGroups:
    """Return the outlines recorded at ``path``; a missing file declares none."""
    if not path.is_file():
        return OutlineGroups({})
    with path.open("rb") as handle:
        document = load_toml(handle)
    entries = document.get("outlines", [])
    if not isinstance(entries, list):
        raise OutlineGroupRefusedError(f"{path.name}: 'outlines' is not an array of tables")
    outlines: dict[tuple[str, str], tuple[FormOutlineGroup, ...]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise OutlineGroupRefusedError(f"{path.name}: outline {entry!r} is not a table")
        modelo, revision, groups = entry.get("modelo"), entry.get("revision"), entry.get("groups")
        if not isinstance(modelo, str) or not isinstance(revision, str) or not isinstance(groups, list):
            raise OutlineGroupRefusedError(f"{path.name}: outline {entry!r} needs a modelo, a revision and groups")
        if (modelo, revision) in outlines:
            raise OutlineGroupRefusedError(f"{path.name}: {modelo} {revision} declares two outlines")
        outlines[(modelo, revision)] = tuple(_group(modelo, revision, group) for group in groups)
    return OutlineGroups(outlines)
