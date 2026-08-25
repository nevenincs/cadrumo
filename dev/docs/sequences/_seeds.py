""":seed: recipe loading and inlining for ``cli-sequence`` directives.

A seed recipe is a reusable fragment of ``@setup`` frames stored at
``docs/_sequences/seeds/<name>.seq`` -- "create the profile, import the standard
quarter" declared once and inlined before a sequence's own frames by the
``:seed: <name>`` directive option. Seeding is *executed CLI truth*: a seed line
runs and golden-gates like any frame, it merely renders collapsed.

A seed recipe may contain ONLY ``@setup`` frames (with their ``@capture`` /
``@expect`` annotations). A visible command frame or a ``@result`` frame in a
recipe is refused -- the terminal verification frame is always the sequence's own,
and a shared fragment must stay collapsed setup. A missing recipe is an
instructive problem, not a crash, so the parser accumulates it with the rest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ..._paths import REPO_ROOT, UTF_8
from ._parser import _FrameBuilder, parse_frame_lines
from ._schema import FrameKind

__all__ = ["SEED_SUFFIX", "default_seeds_root", "load_seed_frames"]

#: File extension of a committed seed recipe.
SEED_SUFFIX: str = ".seq"
_UTF_8: Final[str] = UTF_8


def default_seeds_root() -> Path:
    """Return the committed ``docs/_sequences/seeds/`` recipe directory.

    Resolved relative to this module so the engine finds recipes regardless of
    the process working directory.
    """
    repo_root = REPO_ROOT
    return repo_root / "docs" / "_sequences" / "seeds"


def load_seed_frames(
    name: str,
    *,
    seeds_root: Path | None = None,
) -> tuple[list[_FrameBuilder], list[str]]:
    """Load and parse the ``@setup`` frames of a named seed recipe.

    Reads ``<seeds_root>/<name>.seq``, parses it with the shared frame-line pass,
    and enforces the seed-only constraint (every frame must be ``@setup``). The
    returned frame builders are labelled ``source="seed:<name>"`` so a fault in a
    recipe is located in the recipe, not the consuming directive.

    Args:
        name: The recipe name (the ``:seed:`` option value).
        seeds_root: The recipe directory; defaults to :func:`default_seeds_root`.

    Returns:
        A ``(builders, problems)`` pair. ``builders`` are the recipe's setup
        frames in order; ``problems`` names a missing recipe, an unreadable file,
        or any grammar / seed-only violation.
    """
    root = seeds_root if seeds_root is not None else default_seeds_root()
    recipe_path = root / f"{name}{SEED_SUFFIX}"
    source = f"seed:{name}"

    if not recipe_path.is_file():
        return [], [f"{source}: recipe not found at {recipe_path}"]

    try:
        text = recipe_path.read_text(encoding=_UTF_8)
    except OSError as exc:
        return [], [f"{source}: cannot read recipe at {recipe_path} ({exc})"]

    builders, problems = parse_frame_lines(text, source=source)
    for builder in builders:
        if builder.kind is not FrameKind.SETUP:
            problems.append(
                f"seed:{name} line {builder.line_number}: a seed recipe may contain only @setup frames, "
                f"found a {builder.kind.value} frame ({builder.command_line!r})",
            )
    return builders, problems
