"""No module mints a cache under the user's home directory.

Every persistent cache the development tooling keeps is derived output of one
checkout: registry pickles, validation verdicts, extracted record designs,
corpus text, runtime wheels, packaging proofs. Seven modules each resolved
``Path.home() / ".cadrumo" / <name>`` independently, so the output of every
worktree on the machine accumulated in one hidden tree no checkout owned.
Nothing rebuilt it, nothing swept it, deleting a worktree did not shrink it,
and it reached tens of thousands of files before anyone looked inside.

Two properties keep that from coming back. No module spells ``.cadrumo`` as a
path segment at all -- the name is retired, not relocated. And no module builds
a path from ``Path.home()`` unless it is named here with the reason it must:
the home directory is where an EXTERNAL tool keeps its own state, never where
this project keeps its own. The repository-scoped default lives in
``dev/cache_root.py``, which needs no home directory to find it.

The corpus is enumerated from the current source tree, so a module added
tomorrow is covered by existing.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The trees that carry this project's own code.
_SCANNED_TREES: Final[tuple[str, ...]] = ("src", "dev")

#: This file, which must quote the retired name in order to forbid it.
_THIS_FILE: Final[str] = "dev/tests/test_no_home_directory_cache_paths.py"

#: Files that may SPELL the retired name, and why. Quoting a forbidden string is
#: not resurrecting it when the quote is what proves it is gone.
_QUOTES_THE_RETIRED_NAME: Final[dict[str, str]] = {
    _THIS_FILE: "forbids the name, and cannot forbid what it may not write",
    "src/cadrumo/core/tests/test_logging_private_helpers.py": (
        "asserts the redaction removes the name from log output, which needs a sample containing it"
    ),
}

#: The retired cache name, spelled as a quoted path segment.
_RETIRED_SEGMENT: Final[re.Pattern[str]] = re.compile(r"""["']\.cadrumo["']|~/\.cadrumo""")

#: Modules that may build a path from the home directory, and why. Each names
#: state owned by something OUTSIDE this project, which is the only reason the
#: home directory is the right place to look.
_HOME_IS_CORRECT: Final[dict[str, str]] = {
    "src/cadrumo/application/provisioning_browser.py": (
        "Playwright's own browser cache, whose location Playwright defines and this project only reads"
    ),
    "src/cadrumo/application/provisioning_host.py": (
        "where each platform's official Ollama installer places the runtime binary, which that "
        "installer chooses and this project only looks for"
    ),
    "src/cadrumo/core/config_state_root.py": (
        "captures the user's home as one typed input to platform state-root resolution, not as a cache location"
    ),
    "dev/env/temp_reaper.py": "Claude Code's session transcript root, written by the tool this module observes",
}

#: Modules that name the home directory in order to REMOVE it from output, and
#: why. Kept apart from `_HOME_IS_CORRECT` because the claims are opposites: that
#: list means "this external tool's state lives there", and a redaction helper is
#: asserting the reverse -- that the path must never leave this machine. Listing
#: a redactor there would record a reason that is not its reason.
_HOME_IS_REDACTED: Final[dict[str, str]] = {
    "src/cadrumo/core/logging.py": "derives every spelling of the home directory so log output can be scrubbed of it",
    "src/cadrumo/core/tests/test_logging_private_helpers.py": (
        "exercises that scrubbing, so it must build the paths the redaction is meant to remove"
    ),
}


@cache
def _python_sources() -> tuple[str, ...]:
    """Return every Python file below the scanned trees, as repo-relative POSIX paths."""
    return tuple(path for path in repository_files(under=_SCANNED_TREES) if path.endswith(".py"))


def _home_call_lines(source: str) -> tuple[int, ...]:
    """Return the line of every ``Path.home()`` call in ``source``.

    Parsed rather than matched, so prose in a docstring that merely NAMES the
    call is not mistaken for a module that makes it.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "home":
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "Path":
            lines.append(node.lineno)
    return tuple(lines)


def _scan(paths: tuple[str, ...], root: Path = REPO_ROOT) -> tuple[list[str], list[str], int]:
    """Return retired-name offenders, unlisted home-path offenders, and the count examined."""
    retired: list[str] = []
    homed: list[str] = []
    examined = 0
    for relative in paths:
        try:
            source = (root / relative).read_text(encoding=UTF_8)
        except (OSError, UnicodeDecodeError):
            continue
        examined += 1
        if relative not in _QUOTES_THE_RETIRED_NAME:
            retired.extend(
                f"{relative}:{index}"
                for index, line in enumerate(source.splitlines(), 1)
                if _RETIRED_SEGMENT.search(line)
            )
        if relative in _HOME_IS_CORRECT or relative in _HOME_IS_REDACTED or relative == _THIS_FILE:
            continue
        homed.extend(f"{relative}:{line}" for line in _home_call_lines(source))
    return retired, homed, examined


def test_no_module_spells_the_retired_home_cache_name() -> None:
    """The name is retired, so a new spelling of it is a cache resurrected, not relocated."""
    retired, _, examined = _scan(_python_sources())

    assert examined > 100, "no Python source was discovered; this gate is asserting nothing"
    assert retired == [], (
        "these lines spell the retired home-directory cache name; development caches "
        "resolve through dev.cache_root.dev_cache_dir instead:\n  " + "\n  ".join(retired)
    )


def test_no_unlisted_module_builds_a_path_from_the_home_directory() -> None:
    """A home-directory path is an external tool's location or it is a mistake."""
    _, homed, examined = _scan(_python_sources())

    assert examined > 100, "no Python source was discovered; this gate is asserting nothing"
    assert homed == [], (
        "these call sites build a path from the user's home directory without being "
        "listed as external-tool state in this gate:\n  " + "\n  ".join(homed)
    )


def test_every_listed_home_path_module_still_exists() -> None:
    """A stale entry is an exemption nothing needs and nobody would notice granting."""
    sources = set(_python_sources())
    listed = {**_HOME_IS_CORRECT, **_HOME_IS_REDACTED}
    missing = sorted(relative for relative in listed if relative not in sources)

    assert _HOME_IS_CORRECT, "the allowlist is empty; this gate is asserting nothing"
    assert missing == [], f"these allowlisted modules no longer exist: {missing}"

    still_calling = sorted(
        relative for relative in listed if not _home_call_lines((REPO_ROOT / relative).read_text(encoding=UTF_8))
    )
    assert still_calling == [], (
        f"these modules no longer build a home-directory path, so their exemption is stale: {still_calling}"
    )

    # The same discipline for the other exemption family: a file excused from the
    # retired-name rule that no longer writes the name is an exemption nothing
    # needs, and it would silently cover a real resurrection later.
    quoting = sorted(relative for relative in _QUOTES_THE_RETIRED_NAME if relative not in sources)
    assert quoting == [], f"these retired-name exemptions name files that no longer exist: {quoting}"

    silent = sorted(
        relative
        for relative in _QUOTES_THE_RETIRED_NAME
        if not _RETIRED_SEGMENT.search((REPO_ROOT / relative).read_text(encoding=UTF_8))
    )
    assert silent == [], f"these files no longer spell the retired name, so their exemption is stale: {silent}"


def test_a_new_home_cache_is_reported(tmp_path: Path) -> None:
    """Teeth, against an isolated file rather than the tree being protected."""
    offender = tmp_path / "leaks.py"
    offender.write_text('store = Path.home() / ".cadrumo" / "new-cache"\n', encoding=UTF_8)

    retired, homed, examined = _scan(("leaks.py",), root=tmp_path)

    assert examined == 1
    assert retired == ["leaks.py:1"]
    assert homed == ["leaks.py:1"]


def test_a_home_path_under_another_name_is_still_reported(tmp_path: Path) -> None:
    """Renaming the directory is not the fix; leaving the home directory is."""
    offender = tmp_path / "renamed.py"
    offender.write_text('store = Path.home() / ".cadrumo-caches"\n', encoding=UTF_8)

    retired, homed, _ = _scan(("renamed.py",), root=tmp_path)

    assert retired == []
    assert homed == ["renamed.py:1"]


def test_prose_naming_the_call_is_not_an_offence(tmp_path: Path) -> None:
    """The rule is about resolving a home path, not about mentioning one."""
    documented = tmp_path / "prose.py"
    documented.write_text('"""A note about Path.home() and what it returns."""\n', encoding=UTF_8)

    retired, homed, _ = _scan(("prose.py",), root=tmp_path)

    assert retired == []
    assert homed == []
