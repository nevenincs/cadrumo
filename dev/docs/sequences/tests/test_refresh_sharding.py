"""Page selection, shard scheduling and schedule-independence of the golden refresh."""

from __future__ import annotations

import filecmp
from pathlib import Path

import pytest

from dev.docs.sequences.checks import (
    DEFAULT_REFRESH_JOBS,
    DiscoveredSequence,
    RefreshUnit,
    _problem_entries,
    _refresh_child_command,
    build_argument_parser,
    discover_sequences,
    english_pinned_environment,
    frame_runs_command,
    pages_running_command,
    refresh_pages,
    refresh_units,
)
from dev.paths import AUTHORITY_ROOT_ENV

_PROFILE_PREREQUISITE = "Create a profile first with `aeat config profile create`.\n"

_LIST_BODY = "@result aeat --format json config profile list\n@expect exit_code == 0\n"
_STATUS_BODY = "@result aeat --format json config profile status\n@expect exit_code == 0\n"
_SHOWN_ONLY_BODY = (
    "@static aeat --format json config profile status\n"
    "@blocked sandbox-posture Shown only; the sandbox does not run it.\n"
    "@result aeat --format json config profile list\n"
    "@expect exit_code == 0\n"
)
_ALL_STATIC_BODY = (
    "@static aeat config profile status\n@blocked sandbox-posture Shown only; the sandbox does not run it.\n"
)


def _write_page_sequence(root: Path, page: str, sequence_id: str, body: str, *, verify: bool = True) -> None:
    """Enrol one more sequence on a page, creating the page and its profile prerequisite on first use."""
    target = root / f"{page}.md"
    claim = ":verify: Verify the command succeeds.\n" if verify else ""
    directive = "```{cli-sequence} " + sequence_id + "\n" + claim + "```\n"
    if target.is_file():
        target.write_text(target.read_text(encoding="utf-8") + "\n" + directive, encoding="utf-8")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Page\n\n" + _PROFILE_PREREQUISITE + "\n" + directive, encoding="utf-8")
    contract = root / "_sequences" / "contracts" / Path(page) / f"{sequence_id}.seq"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(body, encoding="utf-8")


def _discovered(root: Path) -> tuple[DiscoveredSequence, ...]:
    discovered, problems = discover_sequences(docs_root=root)
    assert problems == (), problems
    return discovered


@pytest.mark.unit
@pytest.mark.hex_core
class TestFrameRunsCommand:
    def test_consecutive_tokens_after_the_executable_match(self) -> None:
        argv = ("aeat", "--format", "json", "app", "ledger", "classify", "--all")
        assert frame_runs_command(argv, ("app", "ledger", "classify"))

    def test_tokens_must_be_consecutive(self) -> None:
        assert not frame_runs_command(("aeat", "app", "ledger", "--x", "classify"), ("app", "ledger", "classify"))

    def test_a_longer_command_does_not_match_a_shorter_invocation(self) -> None:
        assert not frame_runs_command(("aeat", "app", "ledger"), ("app", "ledger", "classify"))

    def test_the_executable_token_is_not_part_of_the_command_path(self) -> None:
        assert not frame_runs_command(("aeat", "app"), ("aeat", "app"))

    def test_an_empty_command_selects_nothing(self) -> None:
        assert not frame_runs_command(("aeat", "app"), ())

    def test_a_sibling_verb_sharing_a_prefix_is_not_the_command(self) -> None:
        assert not frame_runs_command(("aeat", "app", "ledger", "classify-all"), ("app", "ledger", "classify"))


@pytest.mark.unit
@pytest.mark.hex_core
class TestPagesRunningCommand:
    def test_pages_selected_by_an_executed_frame_in_discovery_order(self, tmp_path: Path) -> None:
        _write_page_sequence(tmp_path, "how-to/alpha", "alpha-case", _LIST_BODY)
        _write_page_sequence(tmp_path, "how-to/beta", "beta-case", _STATUS_BODY)
        discovered = _discovered(tmp_path)
        assert pages_running_command(discovered, ("config", "profile", "status")) == ("how-to/beta",)
        assert pages_running_command(discovered, ("config", "profile")) == ("how-to/alpha", "how-to/beta")

    def test_a_static_frame_that_only_shows_the_command_selects_nothing(self, tmp_path: Path) -> None:
        _write_page_sequence(tmp_path, "how-to/shown", "shown-case", _SHOWN_ONLY_BODY)
        discovered = _discovered(tmp_path)
        assert pages_running_command(discovered, ("config", "profile", "status")) == ()
        assert pages_running_command(discovered, ("config", "profile", "list")) == ("how-to/shown",)

    def test_the_committed_corpus_has_pages_executing_the_ledger_classify_command(self) -> None:
        discovered, problems = discover_sequences()
        assert problems == (), problems
        pages = pages_running_command(discovered, ("app", "ledger", "classify"))
        assert pages
        assert set(pages) <= {item.page for item in discovered}


@pytest.mark.unit
@pytest.mark.hex_core
class TestRefreshUnits:
    @staticmethod
    def _tree(root: Path, *, heavy_sequences: int) -> tuple[DiscoveredSequence, ...]:
        for index in range(heavy_sequences):
            _write_page_sequence(root, "how-to/heavy", f"heavy-{index}", _LIST_BODY)
        _write_page_sequence(root, "how-to/light-a", "light-a-case", _STATUS_BODY)
        _write_page_sequence(root, "how-to/light-b", "light-b-case", _STATUS_BODY)
        return _discovered(root)

    def test_a_page_heavier_than_an_even_share_splits_into_its_sequences(self, tmp_path: Path) -> None:
        units = refresh_units(self._tree(tmp_path, heavy_sequences=3), jobs=4)
        assert [(unit.page, unit.sequence_id) for unit in units] == [
            ("how-to/heavy", "heavy-0"),
            ("how-to/heavy", "heavy-1"),
            ("how-to/heavy", "heavy-2"),
            ("how-to/light-a", None),
            ("how-to/light-b", None),
        ]

    def test_pages_within_an_even_share_stay_whole(self, tmp_path: Path) -> None:
        units = refresh_units(self._tree(tmp_path, heavy_sequences=3), jobs=1)
        assert [(unit.page, unit.sequence_id) for unit in units] == [
            ("how-to/heavy", None),
            ("how-to/light-a", None),
            ("how-to/light-b", None),
        ]

    def test_a_single_sequence_page_is_never_split(self, tmp_path: Path) -> None:
        units = refresh_units(self._tree(tmp_path, heavy_sequences=1), jobs=8)
        assert all(unit.sequence_id is None for unit in units)

    def test_all_static_sequences_are_not_units(self, tmp_path: Path) -> None:
        _write_page_sequence(tmp_path, "how-to/display", "display-case", _ALL_STATIC_BODY, verify=False)
        assert refresh_units(_discovered(tmp_path), jobs=2) == ()

    def test_weight_counts_executed_frames_plus_start_up(self, tmp_path: Path) -> None:
        _write_page_sequence(tmp_path, "how-to/one", "one-case", _LIST_BODY)
        discovered = _discovered(tmp_path)
        (unit,) = refresh_units(discovered, jobs=2)
        assert unit.weight == len(discovered[0].sequence.executed_frames) + 3


@pytest.mark.unit
@pytest.mark.hex_core
class TestRefreshArguments:
    def test_refresh_takes_several_pages_and_a_job_count(self) -> None:
        args = build_argument_parser().parse_args(
            ["refresh", "--page", "how-to/a", "--page", "how-to/b", "--jobs", "3"],
        )
        assert args.page == ["how-to/a", "how-to/b"]
        assert args.jobs == 3

    def test_refresh_defaults_to_the_sharded_job_count_and_every_page(self) -> None:
        args = build_argument_parser().parse_args(["refresh"])
        assert args.jobs == DEFAULT_REFRESH_JOBS
        assert args.page is None
        assert args.command is None

    def test_scopes_are_mutually_exclusive(self) -> None:
        with pytest.raises(SystemExit):
            build_argument_parser().parse_args(["refresh", "--page", "how-to/a", "--command", "app ledger classify"])

    @pytest.mark.parametrize("jobs", ["0", "-1", "two"])
    def test_a_job_count_below_one_is_refused(self, jobs: str) -> None:
        with pytest.raises(SystemExit):
            build_argument_parser().parse_args(["refresh", "--jobs", jobs])

    def test_check_keeps_one_page_and_has_no_job_count(self) -> None:
        args = build_argument_parser().parse_args(["check", "--page", "how-to/a"])
        assert args.page == "how-to/a"
        with pytest.raises(SystemExit):
            build_argument_parser().parse_args(["check", "--jobs", "2"])


@pytest.mark.unit
@pytest.mark.hex_core
class TestChildContract:
    def test_a_page_unit_refreshes_exactly_one_page_serially_under_the_supplied_roots(self, tmp_path: Path) -> None:
        command = _refresh_child_command(
            unit=RefreshUnit("how-to/a", None, 9), docs_root=tmp_path / "docs", goldens_root=tmp_path / "g"
        )
        assert command[1:5] == ["-m", "dev.docs.sequences", "refresh", "--page"]
        assert command[5:8] == ["how-to/a", "--jobs", "1"]
        assert command[command.index("--docs-root") + 1] == str(tmp_path / "docs")
        assert command[command.index("--goldens-root") + 1] == str(tmp_path / "g")

    def test_a_sequence_unit_refreshes_that_sequence_alone(self) -> None:
        command = _refresh_child_command(unit=RefreshUnit("how-to/a", "a-case", 9), docs_root=None, goldens_root=None)
        assert command[3:7] == ["refresh", "--sequence", "a-case", "--jobs"]
        assert "--page" not in command

    def test_child_omits_roots_it_was_not_given(self) -> None:
        command = _refresh_child_command(unit=RefreshUnit("how-to/a", None, 9), docs_root=None, goldens_root=None)
        assert "--docs-root" not in command
        assert "--goldens-root" not in command

    def test_problems_are_recovered_with_their_continuation_lines(self) -> None:
        stderr = "UserWarning: noise\nproblem: page 'a': first\n  detail line\nproblem: page 'b': second\n"
        assert _problem_entries(stderr) == ("page 'a': first\n  detail line", "page 'b': second")

    def test_child_environment_keeps_the_authority_the_parent_confirmed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(AUTHORITY_ROOT_ENV, str(tmp_path / "authority"))
        monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(tmp_path / "state"))
        environment = english_pinned_environment()
        assert environment[AUTHORITY_ROOT_ENV] == str(tmp_path / "authority")
        assert "CADRUMO_STORAGE_ROOT" not in environment

    def test_child_environment_spells_the_authority_root_natively(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(AUTHORITY_ROOT_ENV, f"{tmp_path.as_posix()}/authority")
        assert english_pinned_environment()[AUTHORITY_ROOT_ENV] == str(tmp_path / "authority")


@pytest.mark.integration
@pytest.mark.hex_core
@pytest.mark.docs
class TestShardedRefreshMatchesSerial:
    def test_goldens_written_by_children_are_byte_identical_to_a_serial_refresh(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        _write_page_sequence(docs, "how-to/alpha", "alpha-one", _LIST_BODY)
        _write_page_sequence(docs, "how-to/alpha", "alpha-two", _STATUS_BODY)
        _write_page_sequence(docs, "how-to/beta", "beta-case", _STATUS_BODY)
        assert any(unit.sequence_id is not None for unit in refresh_units(_discovered(docs), jobs=2))
        serial_root, sharded_root = tmp_path / "serial", tmp_path / "sharded"
        progress: list[str] = []

        serial_written, serial_problems, _ = refresh_pages(docs_root=docs, goldens_root=serial_root, jobs=1)
        sharded_written, sharded_problems, _ = refresh_pages(
            docs_root=docs, goldens_root=sharded_root, jobs=2, progress=progress.append
        )

        assert serial_problems == () == sharded_problems
        assert [path.relative_to(serial_root) for path in serial_written] == [
            path.relative_to(sharded_root) for path in sharded_written
        ]
        assert len(sharded_written) == 3
        assert len(progress) == 3
        for path in sharded_written:
            twin = serial_root / path.relative_to(sharded_root)
            assert filecmp.cmp(path, twin, shallow=False), path
