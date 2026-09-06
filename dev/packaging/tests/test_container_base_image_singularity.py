"""Gate: every Cadrumo container derives from ONE declared Linux base image.

The devcontainer development image (repository-root ``Dockerfile``) declares the
Linux base every container surface in this repository derives from. The
self-hosted runner containers are a different family
(``ghcr.io/actions/actions-runner``) and deliberately out of scope.

Surfaces once wrote the string ``python:3.13-slim`` out by hand, with a
Dockerfile comment claiming they "stay on one Linux base convention" and nothing
enforcing it. That is exactly the shape that rots: ``python:3.13-slim`` is a
MOVING tag, it rolled from Debian 12 (bookworm) to Debian 13 (trixie), and
trixie's 64-bit ``time_t`` transition renamed every ABI-bearing library the
Dockerfile installs to a ``t64`` suffix. Cache-cold builds broke while
cache-warm machines kept passing.

This gate holds the seam closed:

1. The ``Dockerfile`` is the single declaration point (``ARG PYTHON_BASE_IMAGE``).
2. No surface anywhere in the tree re-declares a bare ``python:3.13-*`` literal.
3. The declared tag pins the DISTRIBUTION, not merely the Python minor, so the
   Dockerfile's explicit apt package list cannot be invalidated by a silent
   base-image distro roll.

The second invariant is asserted by walking the tree rather than a named list of
surfaces. A fixed list cannot see a surface that has not been added to it, and
silently stops asserting anything about one that is deleted.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ...quality.unread_inputs import report_unread
from .._base_image import dockerfile_path, linux_base_image

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_REPO_ROOT = REPO_ROOT

# Distributions whose package names the Dockerfile's explicit apt list is
# written against. A base tag that does not pin one of these is a moving
# target and may re-break the apt layer without any change in this repository.
_PINNED_DISTRIBUTIONS = ("trixie", "bookworm")


def test_dockerfile_is_the_single_base_image_declaration() -> None:
    """The Dockerfile declares the base image and the resolver reads it back."""
    declared = linux_base_image()

    assert declared, "the Dockerfile must declare a non-empty PYTHON_BASE_IMAGE"
    assert dockerfile_path().is_file()
    # The FROM must consume the ARG rather than restate the image.
    dockerfile = dockerfile_path().read_text(encoding="utf-8")
    assert "FROM ${PYTHON_BASE_IMAGE}" in dockerfile, (
        "the base stage must build FROM the declared ARG, not from a repeated literal"
    )


def test_declared_base_pins_the_distribution() -> None:
    """The tag pins a Debian release, so the explicit apt list stays truthful."""
    declared = linux_base_image()

    assert any(distribution in declared for distribution in _PINNED_DISTRIBUTIONS), (
        f"{declared!r} does not pin a Debian release. `python:3.13-slim` is a moving tag: "
        "it rolled bookworm -> trixie and the trixie t64 library rename broke the "
        "Dockerfile's apt layer on every cache-cold build. Pin the distribution "
        f"(one of {_PINNED_DISTRIBUTIONS}) or update the apt package list with it."
    )


_BARE_LITERAL = re.compile(r"python:3\.13[-\w.]*")
_SKIPPED_DIRECTORIES = frozenset({".git", ".venv", "var", "dist", "node_modules", "__pycache__", ".vault"})

#: Below this the walk has stopped covering the tree. Live: 7,275 surfaces. A
#: floor rather than a pinned count, so adding or deleting files never edits it.
_MINIMUM_WALKED_SURFACES = 1000


def _declaring_surfaces() -> list[tuple[Path, Path]]:
    """Every file in the tree that could *declare* a container base image.

    Documentation is excluded by construction: a Markdown table naming the
    declared tag describes the declaration, and treating a description as a
    second declaration would make the gate unpassable without deleting the
    documentation that explains it.
    """
    surfaces: list[tuple[Path, Path]] = []
    for directory, subdirectories, filenames in os.walk(_REPO_ROOT):
        # Prune in place, so the walk never DESCENDS into a skipped tree. The
        # set is identical either way; the cost is not. Discarding these after
        # the walk still enumerates and stats every path inside them, and the
        # excluded trees are the enormous ones: 700,590 paths visited to reach
        # the 38,826 that are in scope.
        subdirectories[:] = [name for name in subdirectories if name not in _SKIPPED_DIRECTORIES]
        for filename in filenames:
            if not (
                filename.startswith("Dockerfile")
                or filename == "justfile"
                or filename.endswith((".py", ".yml", ".yaml"))
            ):
                continue
            candidate = Path(directory) / filename
            relative = candidate.relative_to(_REPO_ROOT)
            # A FILE carrying a skipped name is excluded too, exactly as the
            # membership test over the whole relative path used to do; pruning
            # above only reaches directories.
            if _SKIPPED_DIRECTORIES.intersection(relative.parts) or not candidate.is_file():
                continue
            surfaces.append((candidate, relative))
    return sorted(surfaces)


def _base_image_bindings(surface: Path) -> list[tuple[int, str]]:
    """Return each line of ``surface`` that BINDS the literal, not one that names it.

    In Python the difference is structural, so it is read from the AST: a bare
    tag is a redeclaration when it is assigned to a name, passed as a keyword
    argument, RETURNED, or standing as a parameter default, and merely a
    mention when it sits in a docstring or an assertion message. Elsewhere the
    file formats carry no such structure, so a comment prefix is the only
    available distinction.

    A helper that returns the tag and a parameter that defaults to it declare
    the value exactly as an assignment does; reading only assignments and
    keywords let those two spellings restate the base image invisibly.

    A POSITIONAL call argument is deliberately still a mention. The live
    instances of one are fixture SOURCE TEXT handed to a writer - the tag
    appears inside a quoted module this gate's own proofs plant - and treating
    those as declarations would make the gate flag the very fixtures that
    demonstrate it works.
    """
    try:
        text = surface.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as refusal:
        # An unreadable surface yields no bindings, which is indistinguishable
        # from one that derives the tag properly. The walk covers 7,275 surfaces
        # and every one reads today, so a failure here is worth naming rather
        # than absorbing into a clean result.
        report_unread(
            "base-image singularity walk",
            "this surface was not read, so a re-declared base image literal inside it would "
            "not appear in the offenders below",
            [f"{surface} ({type(refusal).__name__})"],
        )
        return []
    if not _BARE_LITERAL.search(text):
        return []
    lines = text.splitlines()
    if surface.suffix == ".py":
        tree = ast.parse(text)
        bound: list[ast.Constant] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign | ast.AnnAssign | ast.Return) and node.value is not None:
                bound.extend(_string_constants(node.value))
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                for default in [*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)]:
                    bound.extend(_string_constants(default))
            elif isinstance(node, ast.Call):
                for keyword in node.keywords:
                    bound.extend(_string_constants(keyword.value))
        return sorted(
            {(node.lineno, lines[node.lineno - 1].strip()) for node in bound if _BARE_LITERAL.search(str(node.value))}
        )
    offenders: list[tuple[int, str]] = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not _BARE_LITERAL.search(line) or stripped.startswith("#"):
            continue
        # The one sanctioned occurrence is the declaration itself.
        if surface.name.startswith("Dockerfile") and stripped.startswith("ARG PYTHON_BASE_IMAGE="):
            continue
        offenders.append((line_number, stripped))
    return offenders


def _string_constants(node: ast.expr) -> list[ast.Constant]:
    return [child for child in ast.walk(node) if isinstance(child, ast.Constant) and isinstance(child.value, str)]


def test_no_surface_restates_a_bare_python_base_literal() -> None:
    """No surface in the tree writes its own `python:3.13-*` literal.

    Walked rather than enumerated. The predecessor named three files, one of
    which was later deleted; from then on it asserted nothing about that surface
    and raised on the missing path instead of reporting a real offender. A walk
    cannot go stale in either direction: a surface added tomorrow is covered
    without editing a list, and one removed simply stops being visited.
    """
    surfaces = _declaring_surfaces()

    assert len(surfaces) > _MINIMUM_WALKED_SURFACES, (
        f"the walk found only {len(surfaces)} surface(s); below this it has stopped covering "
        "the tree and an empty offender list says nothing about whether the literal is restated"
    )

    offenders = [
        f"{relative}:{line_number}: {text}"
        for surface, relative in surfaces
        for line_number, text in _base_image_bindings(surface)
    ]

    assert not offenders, (
        "these lines re-declare the Linux base image instead of deriving it from "
        "`ARG PYTHON_BASE_IMAGE` in the repository-root Dockerfile:\n  " + "\n  ".join(offenders)
    )


def test_a_python_redeclaration_is_detected(tmp_path: Path) -> None:
    """The check has teeth: an argparse default carrying the tag is refused.

    Written to an isolated file rather than into the tree, so the proof runs in
    the same suite as the clean result it is meant to make meaningful.
    """
    surface = tmp_path / "restated.py"
    surface.write_text(
        'parser.add_argument("--image", default="python:3.13-slim-trixie")\n',
        encoding="utf-8",
    )

    assert [line for line, _ in _base_image_bindings(surface)] == [1]


def test_a_returned_tag_is_a_redeclaration(tmp_path: Path) -> None:
    """A helper handing back the tag declares it as surely as an assignment does.

    This is the shape that makes a second source of truth look like a utility:
    every caller derives the base image from the helper, and the helper derives
    it from nothing.
    """
    surface = tmp_path / "returned.py"
    surface.write_text(
        'def base_image() -> str:\n    return "python:3.13-slim-trixie"\n',
        encoding="utf-8",
    )

    assert [line for line, _ in _base_image_bindings(surface)] == [2]


def test_a_parameter_default_carrying_the_tag_is_a_redeclaration(tmp_path: Path) -> None:
    """A default is a declaration every caller that omits the argument inherits."""
    surface = tmp_path / "defaulted.py"
    surface.write_text(
        'def build(image: str = "python:3.13-slim-trixie") -> None:\n    ...\n',
        encoding="utf-8",
    )

    assert [line for line, _ in _base_image_bindings(surface)] == [1]


def test_prose_naming_the_tag_is_not_a_redeclaration(tmp_path: Path) -> None:
    """A docstring or an assertion message describes the base; it does not set it.

    Without this distinction the gate cannot pass while any file explains what
    the declared tag is, which is the pressure that gets a useful gate deleted.
    """
    surface = tmp_path / "described.py"
    surface.write_text(
        '"""The declared base is python:3.13-slim-trixie."""\n'
        "\n"
        "def check(value: str) -> None:\n"
        '    assert value, "expected python:3.13-slim-trixie"\n',
        encoding="utf-8",
    )

    assert _base_image_bindings(surface) == []
