"""Per-sequence verdict reuse through the real ``check_sequences`` engine path.

Sequences execute for real in fresh hermetic sandboxes against goldens a real
refresh produced. The only substitution is ``_TreePolicy.open``: it keys the
corpus over a small synthetic repository instead of hashing the whole checkout
for every case, so a run's verdict inputs are exactly the files each test edits.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, override

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.cache_root import DEV_CACHE_ROOT_ENV

from .. import checks
from ..checks import VerdictPolicy, check_sequences, discover_sequences, refresh_sequences
from ..verdict_cache import FORCE_ENV, SequenceVerdicts
from .verdict_tree_support import PROFILE_PREREQUISITE, SHARED_FILES, write

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/verdict-flow"
_FIRST, _SECOND = "flow-one", "flow-two"
_CONTRACT = "@result aeat --format json config profile list\n@expect exit_code == 0\n"
_PAGE_TEXT = (
    f"# Verdict flow\n\nProse. {PROFILE_PREREQUISITE}\n"
    f"```{{cli-sequence}} {_FIRST}\n:verify: First listing succeeds.\n```\n\n"
    f"```{{cli-sequence}} {_SECOND}\n:verify: Second listing succeeds.\n```\n"
)


@dataclass(frozen=True)
class _TreePolicy(VerdictPolicy):
    repo: Path = Path()

    @override
    def open(self, *, docs_root: Path | None, goldens_root: Path | None) -> SequenceVerdicts:
        assert docs_root is not None
        return SequenceVerdicts(
            docs_root=docs_root, goldens_root=goldens_root, authority_identity="fixture-generation", repo_root=self.repo
        )


@dataclass(frozen=True)
class _Case:
    repo: Path
    docs: Path
    goldens: Path
    cache: Path

    def golden(self, sequence_id: str) -> Path:
        return self.goldens / _PAGE / f"{sequence_id}.json"

    def policy(self, report: Callable[[str], None], *, reuse: bool = True) -> _TreePolicy:
        return _TreePolicy(reuse=reuse, report=report, repo=self.repo)

    def run(self, report: list[str], *, reuse: bool = True) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return check_sequences(
            docs_root=self.docs, goldens_root=self.goldens, verdicts=self.policy(report.append, reuse=reuse)
        )

    def recorded(self) -> list[Path]:
        return sorted(self.cache.glob("**/*.json")) if self.cache.exists() else []

    def reused(self, sequence_id: str) -> str | None:
        item = next(item for item in discover_sequences(docs_root=self.docs)[0] if item.sequence_id == sequence_id)
        return self.policy(print).open(docs_root=self.docs, goldens_root=self.goldens).reused(item)


def _drift(golden: Path) -> None:
    """Make a committed golden disagree with the live transcript, as a CLI behaviour change would."""
    text = golden.read_text(encoding="utf-8")
    assert '"status": "success"' in text
    golden.write_text(text.replace('"status": "success"', '"status": "warning"'), encoding="utf-8")


@pytest.fixture(scope="module")
def pristine(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """One docs tree and one real refresh shared (by copy) across the cases."""
    root = tmp_path_factory.mktemp("verdict-flow-source")
    docs, goldens = root / "docs", root / "goldens"
    write(docs / f"{_PAGE}.md", _PAGE_TEXT)
    for sequence_id in (_FIRST, _SECOND):
        write(docs / "_sequences" / "contracts" / _PAGE / f"{sequence_id}.seq", _CONTRACT)
    written, problems, _advisories = refresh_sequences(docs_root=docs, goldens_root=goldens)
    assert problems == ()
    assert len(written) == 2
    return docs, goldens


@pytest.fixture
def case(pristine: tuple[Path, Path], tmp_path: Path) -> Iterator[_Case]:
    docs, goldens = pristine
    live = _Case(repo=tmp_path / "repo", docs=tmp_path / "docs", goldens=tmp_path / "goldens", cache=tmp_path / "cache")
    shutil.copytree(docs, live.docs)
    shutil.copytree(goldens, live.goldens)
    for relative, text in SHARED_FILES.items():
        write(live.repo / relative, text)
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(live.cache)), scoped_env_var(FORCE_ENV, None):
        yield live


@contextmanager
def _counting_executions(hook: Callable[[int], None] | None = None) -> Generator[list[int]]:
    """Count real sandbox executions; ``hook`` runs before the n-th one starts (1-based)."""
    calls: list[int] = []
    original = checks.execute_in_fresh_sandbox

    def counted(sequence: Any) -> Any:
        calls.append(len(calls) + 1)
        if hook is not None:
            hook(len(calls))
        return original(sequence)

    patch = pytest.MonkeyPatch()
    patch.setattr(checks, "execute_in_fresh_sandbox", counted)
    try:
        yield calls
    finally:
        patch.undo()


def _reported_sequences(report: list[str]) -> list[str]:
    return sorted(line.split(":")[0] for line in report)


def test_a_second_run_reuses_every_sequence_and_executes_none(case: _Case) -> None:
    first_report: list[str] = []
    with _counting_executions() as calls:
        assert case.run(first_report)[0] == ()
    assert len(calls) == 2
    assert first_report == []
    assert len(case.recorded()) == 2

    second_report: list[str] = []
    with _counting_executions() as calls:
        assert case.run(second_report)[0] == ()
    assert calls == [], "a recorded sequence must not execute again"
    assert _reported_sequences(second_report) == [f"{_PAGE}/{_FIRST}", f"{_PAGE}/{_SECOND}"]
    assert all("reused clean verdict" in line for line in second_report)


def test_an_unobserved_run_re_executes_every_sequence_after_a_product_edit_between_runs(case: _Case) -> None:
    """Without an installed observer each record holds the whole product source, so any product edit ends reuse."""
    case.run([])
    write(case.repo / "src/cadrumo_client/transport.py", "# edited between the runs\n")

    report: list[str] = []
    with _counting_executions() as calls:
        assert case.run(report)[0] == ()
    assert len(calls) == 2
    assert report == []

    again: list[str] = []
    with _counting_executions() as calls:
        assert case.run(again)[0] == ()
    assert calls == [], "the records written for the edited product are served"
    assert all("whole product source unchanged" in line for line in again)


def test_execute_all_runs_every_sequence_and_still_records(case: _Case) -> None:
    case.run([])
    report: list[str] = []
    with _counting_executions() as calls:
        assert case.run(report, reuse=False)[0] == ()
    assert len(calls) == 2
    assert report == []
    assert len(case.recorded()) == 2


def test_the_force_switch_executes_everything_despite_recorded_verdicts(case: _Case) -> None:
    case.run([])
    report: list[str] = []
    with scoped_env_var(FORCE_ENV, "1"), _counting_executions() as calls:
        assert case.run(report)[0] == ()
    assert len(calls) == 2
    assert report == []


def test_a_diverging_sequence_is_never_recorded_and_executes_again_next_time(case: _Case) -> None:
    _drift(case.golden(_FIRST))

    with _counting_executions() as calls:
        problems, _ = case.run([])
    assert problems, "the drifted golden must fail the check"
    assert len(calls) == 2
    assert case.reused(_FIRST) is None
    assert case.reused(_SECOND) is not None, "the passing sibling keeps its record"
    assert len(case.recorded()) == 1

    report: list[str] = []
    with _counting_executions() as calls:
        problems, _ = case.run(report)
    assert problems
    assert len(calls) == 1, "only the diverging sequence re-executes"
    assert _reported_sequences(report) == [f"{_PAGE}/{_SECOND}"]
    assert len(case.recorded()) == 1


def test_a_failing_later_sequence_keeps_the_pass_recorded_before_it(case: _Case) -> None:
    _drift(case.golden(_SECOND))
    problems, _ = case.run([])
    assert problems
    assert case.reused(_FIRST) is not None
    assert case.reused(_SECOND) is None


def test_an_interrupted_run_keeps_the_sequence_it_completed_and_records_nothing_for_the_next(case: _Case) -> None:
    def interrupt_second(call: int) -> None:
        if call == 2:
            raise KeyboardInterrupt

    with _counting_executions(interrupt_second) as calls, pytest.raises(KeyboardInterrupt):
        case.run([])
    assert calls == [1, 2]
    first, second = (item.sequence_id for item in discover_sequences(docs_root=case.docs)[0])
    assert case.reused(first) is not None
    assert case.reused(second) is None
    assert len(case.recorded()) == 1

    report: list[str] = []
    with _counting_executions() as calls:
        assert case.run(report)[0] == ()
    assert len(calls) == 1, "the resumed run executes only what the interrupted run never finished"
    assert _reported_sequences(report) == [f"{_PAGE}/{first}"]


def test_a_shared_input_edited_while_a_sequence_ran_refuses_its_record(case: _Case) -> None:
    def edit_runtime_source(call: int) -> None:
        if call == 1:
            write(case.repo / "src/cadrumo_runtime/host.py", "# edited while the first sequence ran\n")

    with _counting_executions(edit_runtime_source):
        problems, _ = case.run([])
    assert any("inputs changed during execution" in problem for problem in problems)
    assert case.recorded() == []
