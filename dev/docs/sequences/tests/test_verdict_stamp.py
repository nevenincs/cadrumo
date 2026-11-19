"""``check --stamp``: a clean unscoped run leaves a dated stamp and a depfile of the inputs its verdicts read.

These drive the real ``main`` in-process over a real one-sequence docs tree:
the sequence executes, the corpus is keyed under the published authority, and
the real ``write_depfile`` writes the depfile.
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV
from dev.paths import REPO_ROOT

from ..checks import refresh_sequences
from ..cli import main
from ..verdict_cache import FORCE_ENV
from .verdict_tree_support import PROFILE_PREREQUISITE, write

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/stamp-case"
_SEQUENCE = "stamp-case"
_CONTRACT = "@result aeat --format json config profile list\n@expect exit_code == 0\n"
_PAGE_TEXT = (
    f"# Stamp\n\nProse. {PROFILE_PREREQUISITE}\n```{{cli-sequence}} {_SEQUENCE}\n:verify: Listing succeeds.\n```\n"
)
_PRODUCT_FILE = REPO_ROOT / "src" / "cadrumo" / "__init__.py"


@pytest.fixture(scope="module")
def pristine(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("stamp-source")
    docs, goldens = root / "docs", root / "goldens"
    write(docs / f"{_PAGE}.md", _PAGE_TEXT)
    write(docs / "_sequences" / "contracts" / _PAGE / f"{_SEQUENCE}.seq", _CONTRACT)
    _written, problems, _advisories = refresh_sequences(docs_root=docs, goldens_root=goldens)
    assert problems == ()
    return docs, goldens


@pytest.fixture
def case(pristine: tuple[Path, Path], tmp_path: Path) -> Iterator[tuple[Path, Path, Path]]:
    docs, goldens = tmp_path / "docs", tmp_path / "goldens"
    shutil.copytree(pristine[0], docs)
    shutil.copytree(pristine[1], goldens)
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "cache")), scoped_env_var(FORCE_ENV, None):
        yield docs, goldens, tmp_path / "out" / "cli-sequences.stamp"


def _arguments(docs: Path, goldens: Path, stamp: Path) -> list[str]:
    return ["check", "--docs-root", str(docs), "--goldens-root", str(goldens), "--stamp", str(stamp)]


def _depfile_paths(depfile: Path) -> tuple[str, set[str]]:
    """Parse Makefile syntax into the target and the dependency set, undoing the escapes."""
    lines = depfile.read_text(encoding="utf-8").splitlines()

    def unescape(token: str) -> str:
        return token.removesuffix(" \\").strip().replace("\\ ", " ").replace("\\#", "#").replace("$$", "$")

    first = unescape(lines[0])
    assert first.endswith(":"), lines[0]
    return first.removesuffix(":"), {unescape(line) for line in lines[1:] if line.strip()}


def test_a_clean_run_writes_a_stamp_dated_to_the_run_start_and_a_depfile_of_its_inputs(
    case: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    docs, goldens, stamp = case
    before_ns = time.time_ns()

    exit_code = main(_arguments(docs, goldens, stamp))

    after_ns = time.time_ns()
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert len(stamp.read_text(encoding="utf-8").strip()) == 64

    modified = stamp.stat().st_mtime_ns
    assert before_ns <= modified <= after_ns
    assert after_ns - modified >= 500_000_000, "the stamp must carry the start of the run, not its end"

    target, dependencies = _depfile_paths(stamp.with_name(f"{stamp.name}.d"))
    assert target == stamp.resolve().as_posix()
    assert docs.resolve().as_posix() in dependencies
    assert (docs / "_sequences" / "contracts" / _PAGE / f"{_SEQUENCE}.seq").resolve().as_posix() in dependencies
    assert (goldens / _PAGE / f"{_SEQUENCE}.json").resolve().as_posix() in dependencies
    assert _PRODUCT_FILE.resolve().as_posix() in dependencies
    assert bundled_authority_descriptor_path().resolve().as_posix() in dependencies


def test_a_failing_run_removes_a_stale_stamp_and_writes_none(
    case: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    docs, goldens, stamp = case
    golden = goldens / _PAGE / f"{_SEQUENCE}.json"
    text = golden.read_text(encoding="utf-8")
    assert '"status": "success"' in text
    golden.write_text(text.replace('"status": "success"', '"status": "warning"'), encoding="utf-8")
    write(stamp, "stale\n")

    exit_code = main(_arguments(docs, goldens, stamp))

    assert exit_code == 1
    assert "frame 0" in capsys.readouterr().err
    assert not stamp.exists()
    assert not stamp.with_name(f"{stamp.name}.d").exists()


@pytest.mark.parametrize("scope", [["--page", _PAGE], ["--sequence", _SEQUENCE], ["--timeout", "60"]])
def test_a_stamp_with_a_scoped_or_subprocess_run_is_refused_without_running(
    case: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str], scope: list[str]
) -> None:
    docs, goldens, stamp = case
    write(stamp, "stale\n")

    exit_code = main([*_arguments(docs, goldens, stamp), *scope])

    assert exit_code == 2
    assert "--stamp" in capsys.readouterr().err
    assert stamp.read_text(encoding="utf-8") == "stale\n", "a refused invocation must not touch the stamp"
    assert not stamp.with_name(f"{stamp.name}.d").exists()


def test_a_stamp_with_the_coherence_tier_is_refused(
    case: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    docs, goldens, stamp = case
    assert main([*_arguments(docs, goldens, stamp), "--coherence"]) == 2
    assert "--stamp" in capsys.readouterr().err
    assert not stamp.exists()
