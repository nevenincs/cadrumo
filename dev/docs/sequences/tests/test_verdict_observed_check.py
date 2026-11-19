"""``python -m dev.docs.sequences check`` records the product files its sequences read, and reuses them.

An audit hook can never be uninstalled, so the observed ``check`` runs in child
interpreters, exactly as the build runs it. The fixture tree holds two sequences
that list profiles through the installed runtime, so each execution starts a
profile worker as a separate process whose reads reach the record only through
its journal. The cache root is a temporary directory, the docs tree is a copy
of a real refresh, and the product the children read is this checkout.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from dev.cache_root import DEV_CACHE_ROOT_ENV
from dev.packaging.command_execution import run_command
from dev.paths import REPO_ROOT

from ..checks import refresh_sequences
from ..verdict_cache import FORCE_ENV
from .verdict_tree_support import PROFILE_PREREQUISITE, write

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/observed-check"
_SEQUENCES = ("observed-one", "observed-two")
_CONTRACTS = {
    "observed-one": "@result aeat --format json config profile list\n@expect exit_code == 0\n",
    # A profile-bound operation: the runtime serves it through a separate profile worker process.
    "observed-two": (
        "@result aeat --format json app modelo readiness --modelo 303 --year 2026 --period 1T\n"
        '@expect result.modelo == "303"\n'
        "@expect exit_code == 2\n"
    ),
}
_PAGE_TEXT = (
    f"# Observed check\n\nProse. {PROFILE_PREREQUISITE}\n"
    "```{cli-sequence} observed-one\n:verify: First listing succeeds.\n```\n\n"
    "```{cli-sequence} observed-two\n:verify: Second listing succeeds.\n```\n"
)
_TIMEOUT_SECONDS = 900.0

# Observe, spy on the journals the check folds in, then run the real command line entry.
_SPY_CHILD = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from dev.docs.sequences import dependency_observation as observation_module\n"
    "observation_module.observe_process(Path(sys.argv[1]))\n"
    "folded = []\n"
    "original = observation_module.Observation.merge_journal\n"
    "def spy(self, journal):\n"
    "    text = journal.read_text(encoding='utf-8', errors='surrogateescape')\n"
    "    folded.append([line.split('\\t', 2)[2] for line in text.splitlines() if line.startswith('F\\t')])\n"
    "    return original(self, journal)\n"
    "observation_module.Observation.merge_journal = spy\n"
    "from dev.docs.sequences.cli import main\n"
    "code = main(['check', '--docs-root', sys.argv[2], '--goldens-root', sys.argv[3]])\n"
    "print(json.dumps({'code': code, 'journals': folded}))\n"
)


@pytest.fixture(scope="module")
def pristine(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("observed-check-source")
    docs, goldens = root / "docs", root / "goldens"
    write(docs / f"{_PAGE}.md", _PAGE_TEXT)
    for sequence_id in _SEQUENCES:
        write(docs / "_sequences" / "contracts" / _PAGE / f"{sequence_id}.seq", _CONTRACTS[sequence_id])
    written, problems, _advisories = refresh_sequences(docs_root=docs, goldens_root=goldens)
    assert problems == ()
    assert len(written) == len(_SEQUENCES)
    return docs, goldens


@pytest.fixture
def case(pristine: tuple[Path, Path], tmp_path: Path) -> Iterator[tuple[Path, Path, Path]]:
    docs, goldens = tmp_path / "docs", tmp_path / "goldens"
    shutil.copytree(pristine[0], docs)
    shutil.copytree(pristine[1], goldens)
    yield docs, goldens, tmp_path / "cache"


def _environment(cache: Path) -> dict[str, str]:
    environment = {name: value for name, value in os.environ.items() if name != FORCE_ENV}
    environment[DEV_CACHE_ROOT_ENV] = str(cache)
    return environment


def _check(docs: Path, goldens: Path, cache: Path) -> tuple[int, str, str]:
    result = run_command(
        [sys.executable, "-m", "dev.docs.sequences", "check", "--docs-root", str(docs), "--goldens-root", str(goldens)],
        cwd=REPO_ROOT,
        environment=_environment(cache),
        timeout_seconds=_TIMEOUT_SECONDS,
    )
    return result.returncode, result.stdout, result.stderr


def _products(cache: Path) -> list[dict[str, object]]:
    products: list[dict[str, object]] = []
    for record in sorted(cache.rglob("*.json")):
        product = json.loads(record.read_text(encoding="utf-8"))["product"]
        assert isinstance(product, dict)
        products.append(product)
    return products


def test_the_first_run_records_the_observed_product_and_the_second_reuses_every_sequence(
    case: tuple[Path, Path, Path],
) -> None:
    docs, goldens, cache = case

    code, out, err = _check(docs, goldens, cache)
    assert code == 0, out + err
    assert "reused clean verdict" not in out, "nothing was recorded before the first run"
    products = _products(cache)
    assert len(products) == len(_SEQUENCES)
    for product in products:
        assert product["mode"] == "observed"
        files = product["files"]
        listings = product["listings"]
        assert isinstance(files, dict) and isinstance(listings, dict)
        assert any(name.startswith("src/cadrumo/") for name in files), "the CLI's own source must be observed"
        assert any(name.startswith("src/cadrumo_runtime/") for name in files), "the runtime's source must be observed"
        assert all((REPO_ROOT / name).is_file() for name in files)
        assert all((REPO_ROOT / name).is_dir() for name in listings)
        assert not any(name.split("/", 1)[0] in {".venv", ".tmp", "build", ".git", ".cache"} for name in files)

    code, out, err = _check(docs, goldens, cache)
    assert code == 0, out + err
    reused = [line for line in out.splitlines() if "reused clean verdict" in line]
    assert sorted(line.split(":")[0] for line in reused) == [f"{_PAGE}/{name}" for name in _SEQUENCES]
    assert all("observed product files unchanged" in line for line in reused)


def test_a_profile_worker_process_reads_reach_the_record_through_its_journal(case: tuple[Path, Path, Path]) -> None:
    """The workers that list profiles run apart from the check, yet what they read is in the sequence's record."""
    docs, goldens, cache = case
    result = run_command(
        [sys.executable, "-I", "-B", "-c", _SPY_CHILD, str(REPO_ROOT), str(docs), str(goldens)],
        cwd=REPO_ROOT,
        environment=_environment(cache),
        timeout_seconds=_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    assert summary["code"] == 0
    journals = summary["journals"]
    assert journals, "an executed sequence must leave at least one worker journal to harvest"
    repo = REPO_ROOT.resolve()
    worker_read = {
        Path(path).resolve().relative_to(repo).as_posix()
        for journal in journals
        for path in journal
        if Path(path).resolve().is_relative_to(repo)
    }
    assert worker_read, "the worker's journal names the checkout files it read"
    products = _products(cache)
    assert products and all(product["mode"] == "observed" for product in products)
    recorded: set[str] = set()
    for product in products:
        files = product["files"]
        assert isinstance(files, dict)
        recorded.update(files)
    assert worker_read <= recorded, sorted(worker_read - recorded)[:5]
