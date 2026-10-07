"""The one strict compile that carries every published language.

There was one nitpicky ``-n -W`` build per translation target here, each in its
own module so pytest-xdist could spread three multi-minute builds over three
workers. The documentation is now compiled once for every language
(:func:`dev.docs.compile_once.compile_language_roots`), so the gate is one
compile: a warning in any language's prose, in any language's translated
reference, fails the one build that reads them all, and there is no longer a
per-language module set that a new translation target could silently fall out
of.

What the retired modules refused, this keeps: a warning or error under ``-n -W``
with the catalogues read, and a language that is published but built by nobody
-- which is now read off the compile's own stored form rather than off a
hand-authored list of module files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

from ..i18n import SITE_ROOT_LANGUAGES
from ._sphinx_build_harness import SUBPROCESS_TIMEOUT_S, gate_build_env, gate_build_jobs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs, pytest.mark.timeout(1800)]


def test_the_one_strict_compile_is_nitpicky_clean_in_every_language(tmp_path: Path) -> None:
    """The one ``-n -W`` compile of every language succeeds and writes every root.

    Args:
        tmp_path: Pytest-provided isolated output directory.
    """
    html_root, build_root = tmp_path / "html", tmp_path / "build"
    # The stored form is the roots' own intermediate, removed once they are
    # composed from it, so the gate that reads what the compile carried asks
    # for it to be kept.
    stored = build_root / "compiled-text"
    result = run_command(
        [
            sys.executable,
            "-m",
            "dev.docs.compile_once",
            "--html-root",
            str(html_root),
            "--build-root",
            str(build_root),
            "--stored",
            str(stored),
            "--flavor",
            "desktop",
            "--strict",
            "--jobs",
            gate_build_jobs(),
        ],
        cwd=REPO_ROOT,
        environment=gate_build_env(tmp_path),
        timeout_seconds=SUBPROCESS_TIMEOUT_S,
    )

    assert result.returncode == 0, (
        "the one nitpicky compile reported warnings or errors:\n"
        + (result.stdout or "")[-6000:]
        + (result.stderr or "")[-6000:]
    )
    # The published set is the OutputLanguage closed set, and the compile's own
    # stored form declares what it carried: a language the product publishes but
    # the compile left out would otherwise be merely absent from the output.
    carried = json.loads((stored / "layout.json").read_text(encoding="utf-8"))
    assert carried["languages"] == list(SITE_ROOT_LANGUAGES), (
        f"the compile carried {carried['languages']}, and the product publishes {list(SITE_ROOT_LANGUAGES)}"
    )
    absent = [language for language in SITE_ROOT_LANGUAGES if not (html_root / language / "index.html").is_file()]
    assert not absent, f"the compile wrote no entry page for {absent} under {html_root}"
