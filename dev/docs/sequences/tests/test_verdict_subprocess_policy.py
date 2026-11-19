"""The page-sharded subprocess check starts children only for pages that still need execution.

Verdicts are keyed and recorded through the real verdict cache over a synthetic
docs tree, with the corpus hashed over a synthetic repository (so a concurrent
writer in the real checkout cannot move a key mid-test). The child launcher is
replaced by a recorder of the command lines it would have run, because the
contract under test is which children the parent starts and with which options;
nothing here executes a sequence.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV

from .. import checks
from ..checks import (
    EXECUTE_ALL_OPTION,
    _pages_needing_execution,
    _scoped_check_command,
    check_sequences_in_subprocess,
    discover_sequences,
)
from ..verdict_cache import FORCE_ENV, SequenceVerdicts
from .verdict_tree_support import ALPHA, BETA, SyntheticTree, build_tree

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SyntheticTree]:
    synthetic = build_tree(tmp_path / "repo")

    def synthetic_verdicts(
        *, docs_root: Path, goldens_root: Path | None, contracts_root: Path | None = None
    ) -> SequenceVerdicts:
        return SequenceVerdicts(
            docs_root=docs_root,
            goldens_root=goldens_root,
            contracts_root=contracts_root,
            authority_identity="fixture-generation",
            repo_root=synthetic.repo,
        )

    monkeypatch.setattr(checks, "published_sequence_verdicts", synthetic_verdicts)
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "cache")), scoped_env_var(FORCE_ENV, None):
        yield synthetic


@pytest.fixture
def children(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record every child command line instead of launching it."""
    commands: list[list[str]] = []

    def record(command: list[str], *, timeout: float | None) -> tuple[str, ...]:
        commands.append(command)
        return ()

    monkeypatch.setattr(checks, "_run_check_child", record)
    return commands


def _record_pages(tree: SyntheticTree, *pages: str) -> None:
    """Record a clean verdict for every sequence on ``pages``."""
    verdicts = tree.verdicts("fixture-generation")
    for item in tree.discovered().values():
        if item.page in pages:
            verdicts.record_clean(item, key=verdicts.key(item))


def _pages_of(commands: list[list[str]]) -> list[str]:
    return sorted(command[command.index("--page") + 1] for command in commands)


def test_pages_needing_execution_drops_a_fully_recorded_page_and_reports_its_reuse(
    tree: SyntheticTree, capsys: pytest.CaptureFixture[str]
) -> None:
    _record_pages(tree, ALPHA)
    discovered, problems = discover_sequences(docs_root=tree.docs)
    assert problems == ()

    remaining = _pages_needing_execution(discovered, [ALPHA, BETA], docs_root=tree.docs, goldens_root=tree.sequences)

    assert remaining == [BETA]
    reported = capsys.readouterr().out.splitlines()
    assert sorted(line.split(":")[0] for line in reported) == [f"{ALPHA}/a-one", f"{ALPHA}/a-two"]
    assert all("reused clean verdict" in line for line in reported)


def test_a_page_with_one_unrecorded_sequence_still_starts_its_child(
    tree: SyntheticTree, capsys: pytest.CaptureFixture[str]
) -> None:
    verdicts = tree.verdicts("fixture-generation")
    only = tree.discovered()[(ALPHA, "a-one")]
    verdicts.record_clean(only, key=verdicts.key(only))
    discovered, _ = discover_sequences(docs_root=tree.docs)

    remaining = _pages_needing_execution(discovered, [ALPHA, BETA], docs_root=tree.docs, goldens_root=tree.sequences)

    assert remaining == [ALPHA, BETA]
    assert capsys.readouterr().out == "", "a page that executes reports its reuse from its own child"


def test_a_fully_recorded_corpus_starts_no_child(tree: SyntheticTree, children: list[list[str]]) -> None:
    _record_pages(tree, ALPHA, BETA)

    assert check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2) == ()

    assert children == []


def test_only_the_unrecorded_page_starts_a_child_without_the_execute_all_option(
    tree: SyntheticTree, children: list[list[str]]
) -> None:
    _record_pages(tree, ALPHA)

    check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2)

    assert _pages_of(children) == [BETA]
    assert EXECUTE_ALL_OPTION not in children[0]


def test_declining_reuse_starts_every_page_child_with_execute_all(
    tree: SyntheticTree, children: list[list[str]]
) -> None:
    _record_pages(tree, ALPHA, BETA)

    check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2, reuse_verdicts=False)

    assert _pages_of(children) == [ALPHA, BETA]
    assert all(EXECUTE_ALL_OPTION in command for command in children)


def test_the_force_switch_reaches_the_children_as_the_execute_all_option(
    tree: SyntheticTree, children: list[list[str]]
) -> None:
    _record_pages(tree, ALPHA, BETA)

    with scoped_env_var(FORCE_ENV, "1"):
        check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2)

    assert _pages_of(children) == [ALPHA, BETA]
    assert all(EXECUTE_ALL_OPTION in command for command in children)


@pytest.mark.parametrize(
    ("page", "sequence_id"), [(None, None), (ALPHA, None), (None, "a-one")], ids=["serial", "page", "sequence"]
)
def test_a_serial_or_scoped_child_is_told_to_execute_all_only_when_reuse_is_declined(
    tree: SyntheticTree, children: list[list[str]], page: str | None, sequence_id: str | None
) -> None:
    for reuse in (True, False):
        check_sequences_in_subprocess(
            docs_root=tree.docs,
            goldens_root=tree.sequences,
            page=page,
            sequence_id=sequence_id,
            reuse_verdicts=reuse,
        )

    reusing, executing = children
    assert EXECUTE_ALL_OPTION not in reusing
    assert EXECUTE_ALL_OPTION in executing


def test_the_coherence_tier_never_receives_the_execute_all_option(tmp_path: Path) -> None:
    command = _scoped_check_command(
        page=ALPHA, docs_root=tmp_path, goldens_root=None, coherence=True, reuse_verdicts=False
    )
    assert "--coherence" in command
    assert EXECUTE_ALL_OPTION not in command
    golden = _scoped_check_command(
        page=ALPHA, docs_root=tmp_path, goldens_root=None, coherence=False, reuse_verdicts=False
    )
    assert EXECUTE_ALL_OPTION in golden
