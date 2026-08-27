"""One-shot: retire the prose grade markers now that the typed field carries the grade.

A revision's authority grade was once declared twice: as a leading
``# Applicability grade: ...`` comment and, later, as the typed
``authority_grade`` field. Two declarations of the same fact can disagree, and
only one of them is machine-read, so the prose is the one that goes.

The program refuses to delete a marker whose prose disagrees with the typed
field. A disagreement is a finding about the corpus, not something a cleanup
pass gets to resolve by picking the machine-readable side: the prose may be the
one that is right.

Only a marker that OPENS its own comment block is retired. Modelo 122 is why:
its grade phrase sits mid-paragraph inside a block that also carries the orden
citations, a note that the diseño is bundled but unmapped, and the reasoning for
carrying no calendar deadline windows. Retiring that block would delete
grounding to remove a redundancy. A mid-block marker is reported for manual
adjudication instead, because only a reader can separate the sentence from the
prose around it.

The reviewer stamp further down each file ("agent: applicability-grade review
...") is provenance about who reviewed what, not a second declaration of the
grade, and deleting it would destroy the review trail this corpus depends on.

One-shot by design: it is idempotent, and once the marker set is empty it does
nothing on every subsequent run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REGISTRY_MODELOS_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
)

#: The leading prose marker, anchored to the start of a comment line so the
#: reviewer stamp -- which mentions the same words mid-sentence -- cannot match.
MARKER_PATTERN = re.compile(r"^#\s*(Applicability|Scheduling)[- ]grade\s*:", re.IGNORECASE)
TYPED_PATTERN = re.compile(r'^\s*authority_grade\s*=\s*"([a-z_]+)"', re.MULTILINE)


class MarkerDisagreementError(RuntimeError):
    """A prose marker and the typed grade disagree; a cleanup may not decide which wins."""


@dataclass(frozen=True, slots=True)
class MarkerFile:
    """One revision manifest still carrying a prose grade marker."""

    path: Path
    declared: str
    typed: str | None


def _marker_block_bounds(lines: list[str], start: int) -> int:
    """Return the exclusive end of the comment block beginning at ``start``.

    The marker's own sentence usually wraps across several comment lines. The
    block ends at the first line that is not a comment, so a blank line or the
    first key ends it and nothing below is touched.
    """
    end = start + 1
    while end < len(lines) and lines[end].lstrip().startswith("#"):
        end += 1
    return end


def find_mid_block_markers(root: Path | None = None) -> tuple[Path, ...]:
    """Return manifests whose grade phrase is embedded in a wider prose block.

    These are deliberately NOT retired. Their comment block carries grounding
    the corpus needs, and only a reader can lift the grade sentence out of it.
    """
    target = root if root is not None else REGISTRY_MODELOS_ROOT
    found: list[Path] = []
    for path in sorted(target.rglob("revision.toml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        index = next((i for i, line in enumerate(lines) if MARKER_PATTERN.match(line)), None)
        if index is not None and index > 0 and lines[index - 1].lstrip().startswith("#"):
            found.append(path)
    return tuple(found)


def find_marker_files(root: Path | None = None) -> tuple[MarkerFile, ...]:
    """Find every revision manifest whose grade marker OPENS its comment block."""
    target = root if root is not None else REGISTRY_MODELOS_ROOT
    found: list[MarkerFile] = []
    for path in sorted(target.rglob("revision.toml")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        index = next((i for i, line in enumerate(lines) if MARKER_PATTERN.match(line)), None)
        if index is None:
            continue
        if index > 0 and lines[index - 1].lstrip().startswith("#"):
            # Mid-block: the grade phrase shares a block with grounding prose.
            continue
        match = MARKER_PATTERN.match(lines[index])
        typed = TYPED_PATTERN.search(text)
        found.append(
            MarkerFile(path=path, declared=match.group(1).casefold(), typed=typed.group(1) if typed else None),
        )
    return tuple(found)


def retire_markers(root: Path | None = None, *, apply: bool = False) -> tuple[str, ...]:
    """Retire every prose grade marker whose typed field agrees with it.

    Args:
        root: Registry modelos root. Defaults to the bundled tree.
        apply: Write the edits. When ``False`` the files are left untouched and
            the planned edits are returned, so the change can be read before it
            is made.

    Returns:
        One line per retired (or plannable) marker.

    Raises:
        MarkerDisagreementError: When a marker's prose and the typed grade
            disagree, or the typed field is absent. Either way the grade would
            be decided by this program rather than by a reviewer.
    """
    actions: list[str] = []
    for marker in find_marker_files(root):
        if marker.typed is None:
            message = f"{marker.path}: prose declares {marker.declared!r} but no typed authority_grade is present"
            raise MarkerDisagreementError(message)
        if not marker.typed.casefold().startswith(marker.declared[:5]):
            message = (
                f"{marker.path}: prose declares {marker.declared!r} but the typed grade is "
                f"{marker.typed!r}; a cleanup may not choose between them"
            )
            raise MarkerDisagreementError(message)
        lines = marker.path.read_text(encoding="utf-8").splitlines(keepends=True)
        start = next(index for index, line in enumerate(lines) if MARKER_PATTERN.match(line))
        end = _marker_block_bounds([line.rstrip("\n") for line in lines], start)
        actions.append(
            f"{marker.path}: retire prose marker lines {start + 1}-{end} (typed grade {marker.typed!r} kept)",
        )
        if apply:
            del lines[start:end]
            marker.path.write_text("".join(lines), encoding="utf-8")
    return tuple(actions)


def main() -> int:
    """Retire the markers, printing what was done."""
    import sys

    apply = "--apply" in sys.argv
    actions = retire_markers(apply=apply)
    for action in actions:
        print(("retired " if apply else "would retire ") + action)
    print(f"{len(actions)} marker(s) {'retired' if apply else 'pending'}")
    for path in find_mid_block_markers():
        print(f"MANUAL: {path}: grade phrase is embedded in a grounding block; lift it out by hand")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MARKER_PATTERN",
    "MarkerDisagreementError",
    "MarkerFile",
    "find_marker_files",
    "find_mid_block_markers",
    "retire_markers",
]
