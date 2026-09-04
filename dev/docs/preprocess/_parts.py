"""Shared part-splitting and multi-part sidecar writing for extractors.

A source document can extract to more text than the ``vaultspec-rag``
walker's 10 MB file cap (``_MAX_FILE_SIZE``) allows in one ``.extracted.md``
sidecar - a multi-hundred-page manual is the canonical case. This module
holds the budget-aware unit splitter and the multi-part sidecar writer so
every format extractor (workbooks, PDFs) splits identically and a single
oversized source yields several committed sidecar pairs, each under the cap,
rather than one walker-skipped sidecar.

A single-part document keeps the bare ``<file>.extracted.md`` naming; a
multi-part document suffixes each part (``<file>.part-2.extracted.md``) so
the parts never collide, and stamps a ``part-N`` anchor on every unit so a
downstream resolver can trace a hit back to its part.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ..._paths import UTF_8
from .schema import PreprocessOutput, PreprocessUnit
from .sidecar import write_sidecar

_UTF_8: Final[str] = UTF_8

#: Indexable text sidecars must stay under the walker's 10 MB file cap. A
#: source whose full rendering would exceed this budget is split across
#: multiple per-unit-group sidecars. The budget sits a comfortable margin
#: below 10 MB so UTF-8 bytes (wider than the character count for accented
#: Spanish text) never cross the hard cap.
TEXT_BUDGET_BYTES = 8 * 1024 * 1024


def split_units_by_budget(
    units: list[PreprocessUnit],
    *,
    budget_bytes: int = TEXT_BUDGET_BYTES,
) -> list[list[PreprocessUnit]]:
    """Group units so each group's rendered text stays under the byte budget.

    Each group becomes one sidecar pair. A single unit larger than the budget
    on its own still forms its own group (it is never dropped); the walker's
    own oversized-file skip is the backstop, which the caller reports.

    Args:
        units: The extracted units in document order.
        budget_bytes: Maximum total UTF-8 text bytes per group.

    Returns:
        A list of unit groups, preserving order. Always at least one group
        (an empty list of units yields one empty group).
    """
    groups: list[list[PreprocessUnit]] = []
    current: list[PreprocessUnit] = []
    current_bytes = 0
    for unit in units:
        unit_bytes = len(unit.text.encode(_UTF_8))
        if current and current_bytes + unit_bytes > budget_bytes:
            groups.append(current)
            current = []
            current_bytes = 0
        current.append(unit)
        current_bytes += unit_bytes
    if current:
        groups.append(current)
    return groups or [[]]


def part_stand_in_path(source: Path, index: int, total: int) -> Path:
    """Return the naming stand-in path for one part's sidecar pair.

    Single-part sources write sidecars named directly from the source
    (``<file>.extracted.md``). Multi-part sources suffix the part so the
    groups never collide (``<file>.part-2.extracted.md``). The returned path
    is a naming stand-in handed to :func:`write_part_sidecars`; no file is
    created at the stand-in path itself.

    Args:
        source: The origin file.
        index: Zero-based part index.
        total: Total number of parts.

    Returns:
        The stand-in path whose name seeds the sidecar pair.
    """
    if total == 1:
        return source
    return source.with_name(f"{source.name}.part-{index + 1}")


def write_part_sidecars(
    source: Path,
    outputs: list[PreprocessOutput],
) -> list[Path]:
    """Write the sidecar pair(s) for one source's extracted records.

    Args:
        source: The origin file the sidecars sit beside.
        outputs: One :class:`PreprocessOutput` per part (already
            budget-split and anchor-stamped by the caller).

    Returns:
        The list of ``*.extracted.md`` text-sidecar paths written, in part
        order.
    """
    written: list[Path] = []
    total = len(outputs)
    for index, output in enumerate(outputs):
        stand_in = part_stand_in_path(source, index, total)
        text_path, _ = write_sidecar(stand_in, output)
        written.append(text_path)
    return written


def stamp_part_anchors(
    groups: list[list[PreprocessUnit]],
) -> list[list[PreprocessUnit]]:
    """Stamp a ``part-N`` anchor on every unit when there is more than one part.

    Single-part documents are returned unchanged (no anchor needed). For
    multi-part documents each unit gains ``anchor = "part-N"`` so a hit
    resolves to its part.

    Args:
        groups: The budget-split unit groups.

    Returns:
        The groups, anchor-stamped when multi-part.
    """
    if len(groups) <= 1:
        return groups
    return [
        [unit.model_copy(update={"anchor": f"part-{index + 1}"}) for unit in group]
        for index, group in enumerate(groups)
    ]
