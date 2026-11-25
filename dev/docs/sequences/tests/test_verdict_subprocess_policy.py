"""The sharded subprocess check starts children only for units that still need execution.

Verdicts are keyed and recorded through the real verdict cache over a synthetic
docs tree, with the corpus hashed over a synthetic repository (so a concurrent
writer in the real checkout cannot move a key mid-test). Records are written
under the environment the check children run with, because the children are
what record in a real run. The child launcher is replaced by a recorder of the
command lines it would have run, because the contract under test is which
children the parent starts and with which options; nothing here executes a
sequence.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV

from .. import checks
from ..checks import (
    EXECUTE_ALL_OPTION,
    _golden_units_needing_execution,
    _scoped_check_command,
    check_page_coherence_in_subprocess,
    check_sequences_in_subprocess,
    discover_sequences,
    english_pinned_environment,
    sequence_pool_jobs,
)
from ..errors import SequenceEngineError
from ..verdict_cache import FORCE_ENV, SEQUENCE_JOBS_ENV, SequenceVerdicts
from .verdict_tree_support import ALPHA, BETA, SyntheticTree, build_tree, write

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_EVERY_SEQUENCE = {(ALPHA, "a-one"), (ALPHA, "a-two"), (BETA, "b-one")}


@dataclass
class _Authority:
    """The published authority generation the synthetic corpus is keyed under; a test may republish it."""

    generation: str = "fixture-generation"


@pytest.fixture
def authority() -> _Authority:
    return _Authority()


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, authority: _Authority) -> Iterator[SyntheticTree]:
    synthetic = build_tree(tmp_path / "repo")

    def synthetic_verdicts(
        *,
        docs_root: Path,
        goldens_root: Path | None,
        contracts_root: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> SequenceVerdicts:
        return SequenceVerdicts(
            docs_root=docs_root,
            goldens_root=goldens_root,
            contracts_root=contracts_root,
            authority_identity=authority.generation,
            repo_root=synthetic.repo,
            environment=environment,
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


def _child_verdicts(tree: SyntheticTree, authority: _Authority) -> SequenceVerdicts:
    """Open the verdict cache as a check child does: under the environment its parent gives it."""
    return SequenceVerdicts(
        docs_root=tree.docs,
        goldens_root=tree.sequences,
        authority_identity=authority.generation,
        repo_root=tree.repo,
        environment=english_pinned_environment(),
    )


def _record_pages(tree: SyntheticTree, authority: _Authority, *pages: str) -> None:
    """Record a clean verdict for every sequence on ``pages``, as their check children would."""
    verdicts = _child_verdicts(tree, authority)
    for item in tree.discovered().values():
        if item.page in pages:
            verdicts.record_clean(item, key=verdicts.key(item), observation=tree.observe("src/cadrumo/cli.py"))


def _sequences_of(tree: SyntheticTree, commands: list[list[str]]) -> Counter[tuple[str, str]]:
    """Count how many children address each sequence: a page child addresses every sequence on its page."""
    by_page: dict[str, list[tuple[str, str]]] = {}
    for page, sequence_id in tree.discovered():
        by_page.setdefault(page, []).append((page, sequence_id))
    owner = {sequence_id: (page, sequence_id) for page, sequence_id in tree.discovered()}
    addressed: Counter[tuple[str, str]] = Counter()
    for command in commands:
        if "--page" in command:
            addressed.update(by_page[command[command.index("--page") + 1]])
        else:
            addressed[owner[command[command.index("--sequence") + 1]]] += 1
    return addressed


def _pages_of(tree: SyntheticTree, commands: list[list[str]]) -> list[str]:
    return sorted({page for page, _ in _sequences_of(tree, commands)})


def test_units_needing_execution_drop_a_fully_recorded_page_and_report_its_reuse(
    tree: SyntheticTree, authority: _Authority, capsys: pytest.CaptureFixture[str]
) -> None:
    _record_pages(tree, authority, ALPHA)
    discovered, problems = discover_sequences(docs_root=tree.docs)
    assert problems == ()

    remaining = _golden_units_needing_execution(
        discovered, jobs=2, docs_root=tree.docs, goldens_root=tree.sequences, reuse=True
    )

    assert [unit.page for unit in remaining] == [BETA]
    reported = capsys.readouterr().out.splitlines()
    assert sorted(line.split(":")[0] for line in reported) == [f"{ALPHA}/a-one", f"{ALPHA}/a-two"]
    assert all("reused clean verdict" in line for line in reported)


def test_a_page_with_one_unrecorded_sequence_still_starts_its_child(
    tree: SyntheticTree, authority: _Authority, capsys: pytest.CaptureFixture[str]
) -> None:
    verdicts = _child_verdicts(tree, authority)
    only = tree.discovered()[(ALPHA, "a-one")]
    verdicts.record_clean(only, key=verdicts.key(only), observation=tree.observe())
    discovered, _ = discover_sequences(docs_root=tree.docs)

    remaining = _golden_units_needing_execution(
        discovered, jobs=2, docs_root=tree.docs, goldens_root=tree.sequences, reuse=True
    )

    assert sorted(unit.page for unit in remaining) == [ALPHA, BETA]
    assert capsys.readouterr().out == "", "a page that executes reports its reuse from its own child"


def test_a_fully_recorded_corpus_starts_no_child(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]]
) -> None:
    _record_pages(tree, authority, ALPHA, BETA)

    assert check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2) == ()

    assert children == []


def test_the_parent_reuses_what_a_child_recorded_whatever_product_settings_the_parent_carries(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The children run with the parent's product settings removed, so the parent keys under theirs.

    The records are written from inside the children's own environment, the way
    a real child writes them; the parent then carries a product setting no child
    sees, as a test process bridged from an operator's environment file does.
    """
    child_environment = english_pinned_environment()
    with monkeypatch.context() as inside_child:
        for name in list(os.environ):
            inside_child.delenv(name)
        for name, value in child_environment.items():
            inside_child.setenv(name, value)
        verdicts = SequenceVerdicts(
            docs_root=tree.docs,
            goldens_root=tree.sequences,
            authority_identity=authority.generation,
            repo_root=tree.repo,
        )
        for item in tree.discovered().values():
            verdicts.record_clean(item, key=verdicts.key(item), observation=tree.observe())

    with scoped_env_var("CADRUMO_LOG_LEVEL", "DEBUG"), scoped_env_var("CADRUMO_OUTPUT_LANGUAGE", "hu"):
        assert check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2) == ()

    assert children == []


def test_children_are_told_the_record_directory_the_parent_reads(tmp_path: Path) -> None:
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "relocated")):
        assert english_pinned_environment()[DEV_CACHE_ROOT_ENV] == str(tmp_path / "relocated")


def test_a_child_left_to_its_default_cache_resolves_it_under_its_own_storage_root(tmp_path: Path) -> None:
    """The parent's scratch storage root is not passed on, so neither is a cache root derived from it."""
    with scoped_env_var(DEV_CACHE_ROOT_ENV, None), scoped_env_var("CADRUMO_STORAGE_ROOT", str(tmp_path / "scratch")):
        pinned = Path(english_pinned_environment()[DEV_CACHE_ROOT_ENV])
    assert not pinned.is_relative_to(tmp_path / "scratch")


@pytest.mark.parametrize("edit", ["golden", "observed-read", "authority-generation"])
def test_a_changed_input_starts_the_child_of_the_sequences_it_keys(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]], edit: str
) -> None:
    """Positive controls: each recorded verdict stops standing in once one of its inputs moves."""
    _record_pages(tree, authority, ALPHA, BETA)
    if edit == "golden":
        write(tree.golden(BETA, "b-one"), '{"frames": ["moved"], "id": "b-one"}\n')
        expected = [BETA]
    elif edit == "observed-read":
        write(tree.repo / "src/cadrumo/cli.py", "print('cli changed')\n")
        expected = [ALPHA, BETA]
    else:
        authority.generation = "fixture-generation-republished"
        expected = [ALPHA, BETA]

    check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2)

    assert _pages_of(tree, children) == expected


def test_only_the_unrecorded_page_starts_a_child_without_the_execute_all_option(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]]
) -> None:
    _record_pages(tree, authority, ALPHA)

    check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2)

    assert _pages_of(tree, children) == [BETA]
    assert EXECUTE_ALL_OPTION not in children[0]


def test_declining_reuse_starts_every_page_child_with_execute_all(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]]
) -> None:
    _record_pages(tree, authority, ALPHA, BETA)

    check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2, reuse_verdicts=False)

    assert _pages_of(tree, children) == [ALPHA, BETA]
    assert all(EXECUTE_ALL_OPTION in command for command in children)


def test_the_force_switch_reaches_the_children_as_the_execute_all_option(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]]
) -> None:
    _record_pages(tree, authority, ALPHA, BETA)

    with scoped_env_var(FORCE_ENV, "1"):
        check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2)

    assert _pages_of(tree, children) == [ALPHA, BETA]
    assert all(EXECUTE_ALL_OPTION in command for command in children)


@pytest.mark.parametrize("jobs", [1, 2, 3, 8])
def test_every_executed_sequence_is_addressed_by_exactly_one_child(
    tree: SyntheticTree, children: list[list[str]], jobs: int
) -> None:
    check_sequences_in_subprocess(
        docs_root=tree.docs, goldens_root=tree.sequences, jobs=max(2, jobs), reuse_verdicts=False
    )

    addressed = _sequences_of(tree, children)
    assert set(addressed) == _EVERY_SEQUENCE
    assert set(addressed.values()) == {1}


def test_a_page_heavier_than_its_share_of_the_pool_splits_into_one_child_per_sequence(
    tree: SyntheticTree, children: list[list[str]]
) -> None:
    check_sequences_in_subprocess(docs_root=tree.docs, goldens_root=tree.sequences, jobs=2, reuse_verdicts=False)

    sequence_children = sorted(
        command[command.index("--sequence") + 1] for command in children if "--sequence" in command
    )
    page_children = sorted(command[command.index("--page") + 1] for command in children if "--page" in command)
    assert sequence_children == ["a-one", "a-two"]
    assert page_children == [BETA]
    assert all(EXECUTE_ALL_OPTION in command for command in children)
    assert all(command[command.index("--goldens-root") + 1] == str(tree.sequences) for command in children)


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


def test_the_coherence_tier_cannot_address_one_sequence(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="page-scoped"):
        _scoped_check_command(page=ALPHA, sequence_id="a-one", docs_root=tmp_path, goldens_root=None, coherence=True)


def _record_coherent_pages(tree: SyntheticTree, authority: _Authority, *pages: str) -> None:
    """Record a clean page-coherence verdict for ``pages``, as their coherence children would."""
    verdicts = SequenceVerdicts(
        docs_root=tree.docs,
        goldens_root=None,
        authority_identity=authority.generation,
        repo_root=tree.repo,
        environment=english_pinned_environment(),
    )
    discovered = list(tree.discovered().values())
    for page in pages:
        items = [item for item in discovered if item.page == page]
        verdicts.record_clean_coherence(
            page, items, key=verdicts.coherence_key(page, items), observation=tree.observe("src/cadrumo/cli.py")
        )


def _coherence_pages(commands: list[list[str]]) -> list[str]:
    assert all("--coherence" in command for command in commands)
    return sorted(command[command.index("--page") + 1] for command in commands)


def test_a_coherent_recorded_page_starts_no_coherence_child(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    _record_coherent_pages(tree, authority, ALPHA)

    assert check_page_coherence_in_subprocess(docs_root=tree.docs, jobs=2) == ()

    assert _coherence_pages(children) == [BETA]
    assert capsys.readouterr().out.startswith(f"{ALPHA} (page coherence): reused clean verdict")


def test_a_sequence_verdict_never_stands_in_for_a_page_coherence_verdict(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]]
) -> None:
    _record_pages(tree, authority, ALPHA, BETA)

    check_page_coherence_in_subprocess(docs_root=tree.docs, jobs=2)

    assert _coherence_pages(children) == [ALPHA, BETA]


@pytest.mark.parametrize("edit", ["contract", "observed-read", "authority-generation", "force"])
def test_a_changed_input_reruns_the_coherence_of_the_pages_it_keys(
    tree: SyntheticTree, authority: _Authority, children: list[list[str]], edit: str
) -> None:
    """Positive controls for page reuse: the key or the observed product moves, or reuse is forced off."""
    _record_coherent_pages(tree, authority, ALPHA, BETA)
    if edit == "contract":
        contract = tree.contract(ALPHA, "a-two")
        write(contract, contract.read_text(encoding="utf-8") + "@expect exit_code == 0\n")
        expected = [ALPHA]
    elif edit == "observed-read":
        write(tree.repo / "src/cadrumo/cli.py", "print('cli changed')\n")
        expected = [ALPHA, BETA]
    elif edit == "authority-generation":
        authority.generation = "fixture-generation-republished"
        expected = [ALPHA, BETA]
    else:
        expected = [ALPHA, BETA]

    with scoped_env_var(FORCE_ENV, "1" if edit == "force" else None):
        check_page_coherence_in_subprocess(docs_root=tree.docs, jobs=2)

    assert _coherence_pages(children) == expected


@pytest.mark.parametrize(("value", "expected"), [(None, 8), ("", 8), ("12", 12), (" 3 ", 3)])
def test_the_caller_sizes_the_check_pool(value: str | None, expected: int) -> None:
    with scoped_env_var(SEQUENCE_JOBS_ENV, value):
        assert sequence_pool_jobs() == expected


@pytest.mark.parametrize("value", ["0", "-2", "many", "2.5"])
def test_a_pool_size_that_is_not_a_positive_whole_number_is_refused(value: str) -> None:
    with scoped_env_var(SEQUENCE_JOBS_ENV, value), pytest.raises(SequenceEngineError, match=SEQUENCE_JOBS_ENV):
        sequence_pool_jobs()


def test_the_pool_size_never_reaches_a_child(tmp_path: Path) -> None:
    with scoped_env_var(SEQUENCE_JOBS_ENV, "12"):
        assert SEQUENCE_JOBS_ENV not in english_pinned_environment()
