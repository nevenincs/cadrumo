"""Relative links in the educational documentation resolve to a page.

The Diataxis educational docs (``docs/explanation``, ``docs/how-to``) and the
developer-facing architecture overview (``docs/architecture``) link to sibling
pages by relative path. Each link must reach a file that exists, or a page the
build-time CLI reference generator owns: ``docs/cli`` is not checked in, so a
link into it is checked against the generator's real output rendered into an
isolated docs root.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT, UTF_8

from ..cli_reference import generate_cli_reference_in_subprocess

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_EDU_DIRS = ("docs/explanation", "docs/how-to", "docs/architecture")
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _edu_docs() -> list[Path]:
    docs: list[Path] = []
    for directory in _EDU_DIRS:
        docs.extend(scan_directory(REPO_ROOT / directory, pattern="*.md", recursive=True))
    return docs


@cache
def _generated_cli_reference_links() -> frozenset[str]:
    """Return the paths the build-time CLI reference generator owns.

    The generator renders into an isolated temporary docs root so this gate
    checks the current output contract without mutating the worktree.
    """
    with TemporaryDirectory(prefix="cadrumo-doc-link-check-") as temporary_root:
        return frozenset(generate_cli_reference_in_subprocess(Path(temporary_root)))


def test_relative_links_resolve() -> None:
    """Every relative markdown link in the educational docs resolves to an existing page."""
    docs = _edu_docs()
    assert docs, "no educational docs found under docs/{explanation,how-to,architecture}/"
    generated_cli_links = _generated_cli_reference_links()
    assert generated_cli_links, "the CLI reference generator rendered no pages"
    broken: list[str] = []
    for doc in docs:
        text = doc.read_text(encoding=UTF_8)
        for match in _LINK_RE.finditer(text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, anchor = target.partition("#")
            if not path_part:
                # A real in-page anchor (#section) is fine; an empty target
                # ("" or "#") is a dead placeholder myst rejects.
                if not anchor:
                    broken.append(f"{doc.relative_to(REPO_ROOT)}: {target or '(empty)'}")
                continue
            resolved = (doc.parent / path_part).resolve()
            # Must resolve to a FILE (a documented page), not a bare directory:
            # myst cannot cross-reference a directory link such as ``../cli/``.
            if resolved.is_file():
                continue
            try:
                generated_target = resolved.relative_to((REPO_ROOT / "docs").resolve()).as_posix()
            except ValueError:
                generated_target = ""
            if generated_target not in generated_cli_links:
                broken.append(f"{doc.relative_to(REPO_ROOT)}: {target}")
    assert not broken, "educational docs have unresolved relative links:\n" + "\n".join(broken)
