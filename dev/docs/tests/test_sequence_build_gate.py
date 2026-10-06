"""Build-mode guard for the ``cli-tree.json`` projection emit.

The ``cli-tree.json`` projection is a walk of the live ``aeat`` command tree — it
derives from the CLI surface, never from a docs page — so an incremental
docs-only changed-page build cannot change it and must not pay the projection's
subprocess cost. These tests pin :func:`should_emit_cli_tree`'s decision across
every build mode and prove :func:`emit_cli_tree` leaves an existing artifact
untouched on an incremental build (the skip path spawns no projection
subprocess, so a sentinel that a real rebuild would overwrite survives).

They mirror the sibling ``_should_generate_cli_reference`` guard's build-mode
shape (full/absent/forced regenerate, incremental skip) with two dedicated env
seams (``CADRUMO_DOCS_FORCE_CLI_TREE`` / ``CADRUMO_DOCS_SKIP_CLI_TREE``).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from sphinx.application import Sphinx
from sphinx.errors import SphinxError

from cadrumo.core.config import override_settings
from cadrumo.core.directory_scan import scan_directory
from cadrumo.tests.env_scope import scoped_env_var
from dev._paths import REPO_ROOT

from ..cli_tree import default_cli_tree_path
from ..sequence_build_gate import (
    check_sequence_goldens,
    emit_cli_tree,
    should_check_sequences,
    should_emit_cli_tree,
)
from ..sequences.authority_currency import PUBLISH_AUTHORITY_REMEDY

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT

#: A captured package version in a golden. Value-shaped, not a bare number:
#: it must match the product banner form so an unrelated numeric in captured
#: output can never be mistaken for a version.
_VERSION_LITERAL_RE = re.compile(r"CADRUMO \d+\.\d+\.\d+")


def _artifact(root: Path) -> Path:
    """Return the projection destination under a source tree root."""
    return default_cli_tree_path(root)


def test_full_build_regenerates(tmp_path: Path) -> None:
    """A full/update build (no specific sources) always regenerates."""
    assert should_emit_cli_tree(_artifact(tmp_path), specific_sources=None) is True


def test_incremental_with_existing_artifact_skips(tmp_path: Path) -> None:
    """An incremental changed-page build whose artifact exists is skipped."""
    output = _artifact(tmp_path)
    output.parent.mkdir(parents=True)
    output.write_text("{}", encoding="utf-8")
    assert should_emit_cli_tree(output, specific_sources=[tmp_path / "index.md"]) is False


def test_incremental_without_artifact_regenerates(tmp_path: Path) -> None:
    """An incremental build with no artifact yet must build it once."""
    output = _artifact(tmp_path)
    assert not output.is_file()
    assert should_emit_cli_tree(output, specific_sources=[tmp_path / "index.md"]) is True


def test_force_env_overrides_incremental_skip(tmp_path: Path) -> None:
    """``CADRUMO_DOCS_FORCE_CLI_TREE`` regenerates even on an incremental build."""
    output = _artifact(tmp_path)
    output.parent.mkdir(parents=True)
    output.write_text("{}", encoding="utf-8")
    with scoped_env_var("CADRUMO_DOCS_FORCE_CLI_TREE", "1"):
        assert should_emit_cli_tree(output, specific_sources=[tmp_path / "index.md"]) is True


def test_skip_env_overrides_full_build(tmp_path: Path) -> None:
    """``CADRUMO_DOCS_SKIP_CLI_TREE`` suppresses the projection unconditionally."""
    with scoped_env_var("CADRUMO_DOCS_SKIP_CLI_TREE", "1"):
        assert should_emit_cli_tree(_artifact(tmp_path), specific_sources=None) is False


def test_emit_skips_incremental_build_leaving_artifact_untouched(tmp_path: Path) -> None:
    """``emit_cli_tree`` on an incremental build leaves the existing artifact as-is.

    A real regeneration would overwrite the sentinel with the serialised tree;
    its survival proves the guard short-circuited before the projection
    subprocess ran (no 4.9s cost on a docs-only changed-page build).
    """
    output = _artifact(tmp_path)
    output.parent.mkdir(parents=True)
    sentinel = "SENTINEL-not-a-real-cli-tree"
    output.write_text(sentinel, encoding="utf-8")

    # emit_cli_tree reads only ``app.srcdir``; a stand-in carrier suffices to
    # exercise the guard's early return without materialising a full Sphinx app.
    app = cast(Sphinx, SimpleNamespace(srcdir=str(tmp_path)))
    emit_cli_tree(app, specific_sources=[tmp_path / "index.md"])

    assert output.read_text(encoding="utf-8") == sentinel


def test_sequence_check_runs_by_default() -> None:
    """With no opt-out set, every build runs the golden check."""
    assert should_check_sequences() is True


def test_sequence_check_skip_env_suppresses_the_check(tmp_path: Path) -> None:
    """``CADRUMO_DOCS_SKIP_SEQUENCE_CHECK`` short-circuits before any execution.

    The stand-in app's ``srcdir`` points at an EMPTY directory: an unskipped
    check would spawn the engine subprocess against it and, at minimum, pay
    seconds of interpreter/app import — while the skip path must return before
    reading ``srcdir`` at all. The guard decision is pinned here; the
    divergence-reds proof for the UNSKIPPED hook lives in
    ``test_sequence_goldens.TestBothSurfacesRedOnDivergence``.
    """
    with scoped_env_var("CADRUMO_DOCS_SKIP_SEQUENCE_CHECK", "1"):
        assert should_check_sequences() is False
        app = cast(Sphinx, SimpleNamespace(srcdir=str(tmp_path / "never-read"), config=SimpleNamespace()))
        check_sequence_goldens(app, pages=None)


def test_skipped_sequence_check_needs_no_engine_import() -> None:
    """A rendering-only pass must not load the engine it explicitly skips."""
    script = (
        "import sys\n"
        "from types import SimpleNamespace\n"
        "sys.modules['dev.docs.sequences.checks'] = None\n"
        "from dev.docs.sequence_build_gate import check_sequence_goldens\n"
        "check_sequence_goldens(SimpleNamespace(), pages=None)\n"
    )
    with scoped_env_var("CADRUMO_DOCS_SKIP_SEQUENCE_CHECK", "1"):
        result = subprocess.run(  # noqa: S603 - trusted interpreter and literal regression fixture.
            [sys.executable, "-c", script],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    assert result.returncode == 0, result.stderr


def test_an_unpublished_authority_fails_the_build_before_any_verdict_is_reused(tmp_path: Path) -> None:
    """The gate refuses a non-current authority ahead of the verdict cache.

    A clean verdict recorded under an earlier generation would otherwise pass the
    build without executing anything. The refusal must fire first, name the
    republish command, and never reach the pages tree.
    """
    app = cast(Sphinx, SimpleNamespace(srcdir=str(tmp_path / "never-read"), config=SimpleNamespace()))
    with override_settings(cadrumo_authority_root=tmp_path / "unpublished"), pytest.raises(SphinxError) as refusal:
        check_sequence_goldens(app, pages=None)
    assert PUBLISH_AUTHORITY_REMEDY in str(refusal.value)
    assert not (tmp_path / "never-read").exists()


@pytest.mark.parametrize("problems", [[], ["strict sequence failure"]])
def test_full_gate_bounds_actual_page_workers_and_keeps_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problems: list[str]
) -> None:
    from ..sequences import authority_currency, checks, verdict_cache

    app = cast(
        Sphinx,
        SimpleNamespace(
            srcdir=str(tmp_path), config=SimpleNamespace(cadrumo_sequences_goldens_root=tmp_path / "goldens")
        ),
    )
    observed: list[tuple[Path, Path | None, int]] = []
    currency_checks: list[bool] = []

    def execute(*, docs_root: Path, goldens_root: Path | None, jobs: int) -> list[str]:
        assert currency_checks == [True]
        observed.append((docs_root, goldens_root, jobs))
        return problems

    monkeypatch.delenv("CADRUMO_DOCS_SKIP_SEQUENCE_CHECK", raising=False)
    monkeypatch.setattr(authority_currency, "require_current_authority", lambda: currency_checks.append(True))
    monkeypatch.setattr(verdict_cache, "published_verdict_key", lambda **_kwargs: "fixture-key")
    monkeypatch.setattr(verdict_cache, "check_reusing_verdict", lambda _key, run: (run(), None))
    monkeypatch.setattr(checks, "check_sequences_in_subprocess", execute)
    if problems:
        with pytest.raises(SphinxError, match="strict sequence failure"):
            check_sequence_goldens(app)
    else:
        check_sequence_goldens(app)
    assert observed == [(tmp_path, tmp_path / "goldens", 2)]


def test_no_golden_carries_a_version_literal() -> None:
    """A committed golden must not hardcode a package version.

    Docs are rendered FROM these goldens, so a captured ``CADRUMO 0.2.1`` is a
    hardcoded version in user-facing documentation. It rots at the next release
    and silently disagrees with the build the reader actually has -- which is
    exactly what happened: two goldens froze 0.2.1, the version declaration was
    later reset, and the docs build then failed on a divergence whose suggested
    remedy would have baked the stale number back in.

    The version is normalised to a token when a golden is stored and resolved
    back to the running version when the page is rendered, so the reader sees a
    real version that is derived rather than frozen.
    """
    goldens = scan_directory(_REPO_ROOT / "docs" / "_sequences", pattern="*.json", recursive=True)
    assert goldens, "no sequence goldens were found; this gate would pass over an empty corpus"

    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}: {match.group(0)}"
        for path in goldens
        for match in _VERSION_LITERAL_RE.finditer(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        "sequence golden(s) carry a hardcoded package version. Docs render from these files, so the "
        "literal becomes a stale version in user-facing prose at the next release. Re-record with "
        f"`python -m dev.docs.sequences refresh --page <page>` so the version normalises to a token: {offenders}"
    )


def test_the_version_literal_detector_discriminates() -> None:
    """Anti-tautology: the pattern catches a real capture and spares the token."""
    assert _VERSION_LITERAL_RE.findall('"text": "CADRUMO 0.2.1\n"') == ["CADRUMO 0.2.1"]
    assert _VERSION_LITERAL_RE.findall('"text": "CADRUMO 10.20.30\n"') == ["CADRUMO 10.20.30"]
    assert _VERSION_LITERAL_RE.findall('"text": "CADRUMO <version>\n"') == []
