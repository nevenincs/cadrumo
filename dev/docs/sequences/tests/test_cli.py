"""Real-behaviour tests for the refresh / check CLI modes.

Every test drives ``main()`` (the exact ``python -m dev.docs.sequences``
surface) against a real temp docs tree carrying a genuine backtick-fenced
``cli-sequence`` directive; refresh and check runs execute the real CLI in
fresh hermetic sandboxes. Divergence is produced by mutating the committed
golden file — the drift a CLI behaviour change creates — never by stubbing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..__main__ import main
from ..checks import (
    COHERENCE_TIER_PREFIX,
    _timeout_progress_diagnostic,
    check_page_coherence,
    check_sequences,
    discover_sequences,
    refresh_sequences,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/cli-mode-case"
_SEQUENCE_ID = "cli-mode-case"

#: The valid-profile prerequisite sentence every enrolled test page carries
#: above its first directive (the rollout profile-requirement gate).
_PROFILE_PREREQUISITE = "Create a profile first with `aeat config profile create`.\n"

#: A real enrolled page: one directive, a deliberately-unconsumed capture (the
#: advisory case), and a semantically asserted result frame.
_PAGE_TEXT = (
    "# CLI mode case\n"
    "\n"
    "Narrative prose around the sequence. " + _PROFILE_PREREQUISITE + "\n"
    "```{cli-sequence} " + _SEQUENCE_ID + "\n"
    ":verify: Verify the profile listing succeeds.\n"
    "```\n"
    "\n"
    "Closing prose.\n"
)
_CONTRACT_BODY = (
    "aeat --format json config profile list\n"
    "@capture run_status status\n"
    "@result aeat --format json config profile list\n"
    '@expect status == "success"\n'
    "@expect exit_code == 0\n"
)


def _write_contract(root: Path, page: str, sequence_id: str, body: str) -> None:
    """Write one private contract fixture at the production keyed path."""
    target = root / "_sequences" / "contracts" / Path(page) / f"{sequence_id}.seq"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.strip() + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def docs_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("docs-tree")
    target = root / f"{_PAGE}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_PAGE_TEXT, encoding="utf-8")
    _write_contract(root, _PAGE, _SEQUENCE_ID, _CONTRACT_BODY)
    return root


@pytest.fixture(scope="module")
def refreshed_goldens(docs_tree: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One real ``refresh`` run shared by the check tests; returns the goldens root."""
    goldens_root = tmp_path_factory.mktemp("goldens")
    written, problems, advisories = refresh_sequences(docs_root=docs_tree, goldens_root=goldens_root)
    assert problems == ()
    assert [target.name for target in written] == [f"{_SEQUENCE_ID}.json"]
    assert any("run_status" in advisory for advisory in advisories)  # the unused capture
    return goldens_root


def _golden_file(goldens_root: Path) -> Path:
    return goldens_root / _PAGE / f"{_SEQUENCE_ID}.json"


class TestDiscovery:
    def test_directive_is_discovered_and_parsed(self, docs_tree: Path) -> None:
        discovered, problems = discover_sequences(docs_root=docs_tree)
        assert problems == ()
        assert len(discovered) == 1
        item = discovered[0]
        assert item.page == _PAGE
        assert item.sequence_id == _SEQUENCE_ID
        assert len(item.sequence.frames) == 2

    def test_unclosed_fence_is_a_named_problem(self, tmp_path: Path) -> None:
        page = tmp_path / "broken.md"
        page.write_text("```{cli-sequence} broken-case\n:verify: V.\naeat config profile list\n", encoding="utf-8")
        _, problems = discover_sequences(docs_root=tmp_path)
        assert any("never closed" in problem and "broken-case" in problem for problem in problems)

    def test_grammar_faults_name_the_page(self, tmp_path: Path) -> None:
        page = tmp_path / "faulty.md"
        page.write_text(
            "```{cli-sequence} faulty-case\n:verify: V.\n```\n",
            encoding="utf-8",
        )
        _write_contract(tmp_path, "faulty", "faulty-case", "not-a-frame")
        _, problems = discover_sequences(docs_root=tmp_path)
        assert any("'faulty'" in problem and "not-a-frame" in problem for problem in problems)

    def test_public_directive_body_is_refused(self, tmp_path: Path) -> None:
        """Commands and assertions cannot leak back into user-facing Markdown."""
        page = tmp_path / "leaked.md"
        page.write_text(
            "```{cli-sequence} leaked-case\n"
            ":verify: Verify it.\n"
            "@result aeat config profile list\n"
            "@expect exit_code == 0\n"
            "```\n",
            encoding="utf-8",
        )
        _write_contract(
            tmp_path,
            "leaked",
            "leaked-case",
            "@result aeat config profile list\n@expect exit_code == 0",
        )
        _, problems = discover_sequences(docs_root=tmp_path)
        assert any("directive bodies must be empty" in problem for problem in problems), problems

    def test_private_option_on_public_directive_is_refused(self, tmp_path: Path) -> None:
        """Seed and shell machinery belongs to the private contract."""
        page = tmp_path / "private-option.md"
        page.write_text(
            "```{cli-sequence} private-option-case\n:shells: bash\n```\n",
            encoding="utf-8",
        )
        _write_contract(
            tmp_path,
            "private-option",
            "private-option-case",
            "@result aeat config profile list\n@expect exit_code == 0",
        )
        _, problems = discover_sequences(docs_root=tmp_path)
        assert any(":shells:" in problem and "user-facing Markdown" in problem for problem in problems), problems

    def test_duplicate_sequence_ids_across_pages_are_refused(self, tmp_path: Path) -> None:
        body = "```{cli-sequence} dupe-case\n:verify: V.\n```\n"
        (tmp_path / "one.md").write_text(body, encoding="utf-8")
        (tmp_path / "two.md").write_text(body, encoding="utf-8")
        contract = "@result aeat config profile list\n@expect exit_code == 0"
        _write_contract(tmp_path, "one", "dupe-case", contract)
        _write_contract(tmp_path, "two", "dupe-case", contract)
        discovered, problems = discover_sequences(docs_root=tmp_path)
        assert len(discovered) == 1
        assert any("duplicate sequence id" in problem for problem in problems)

    def test_unknown_sequence_scope_is_a_named_problem(self, docs_tree: Path) -> None:
        _, problems = discover_sequences(docs_root=docs_tree, sequence_id="no-such-sequence")
        assert any("no-such-sequence" in problem for problem in problems)


class TestRefreshMode:
    def test_refresh_writes_the_golden_and_exits_zero(
        self,
        docs_tree: Path,
        refreshed_goldens: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The module-scoped fixture already refreshed; a second CLI-level run
        # is idempotent and reports the rewrite.
        exit_code = main(
            [
                "refresh",
                "--sequence",
                _SEQUENCE_ID,
                "--docs-root",
                str(docs_tree),
                "--goldens-root",
                str(refreshed_goldens),
            ],
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "refreshed:" in captured.out
        assert "advisory:" in captured.out  # the unused run_status capture
        golden = json.loads(_golden_file(refreshed_goldens).read_text(encoding="utf-8"))
        assert golden["sequence_id"] == _SEQUENCE_ID
        assert len(golden["frames"]) == 2

    def test_refresh_of_unknown_sequence_fails(self, docs_tree: Path, tmp_path: Path) -> None:
        exit_code = main(
            [
                "refresh",
                "--sequence",
                "no-such-sequence",
                "--docs-root",
                str(docs_tree),
                "--goldens-root",
                str(tmp_path),
            ],
        )
        assert exit_code == 1


class TestCheckMode:
    def test_clean_goldens_pass(
        self,
        docs_tree: Path,
        refreshed_goldens: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        exit_code = main(["check", "--docs-root", str(docs_tree), "--goldens-root", str(refreshed_goldens)])
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        assert "clean" in captured.out

    def test_golden_drift_fails_with_frame_diff_and_refresh_remedy(
        self,
        docs_tree: Path,
        refreshed_goldens: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Inject the drift a CLI behaviour change would produce and assert the
        check names the page, sequence, frame, differing path, and remedy."""
        drifted_root = tmp_path / "goldens"
        source = _golden_file(refreshed_goldens)
        target = drifted_root / _PAGE / f"{_SEQUENCE_ID}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        document = json.loads(source.read_text(encoding="utf-8"))
        document["frames"][0]["envelope"]["status"] = "warning"
        target.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        exit_code = main(["check", "--docs-root", str(docs_tree), "--goldens-root", str(drifted_root)])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert _PAGE in captured.err and _SEQUENCE_ID in captured.err
        assert "frame 0" in captured.err
        assert "status" in captured.err
        assert "python -m dev.docs.sequences refresh" in captured.err

    def test_missing_golden_fails_with_the_refresh_invocation(
        self,
        docs_tree: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        exit_code = main(["check", "--docs-root", str(docs_tree), "--goldens-root", str(tmp_path / "empty")])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "no committed golden" in captured.err
        assert f"refresh --sequence {_SEQUENCE_ID}" in captured.err

    def test_check_functions_are_the_cli_surface(
        self,
        docs_tree: Path,
        refreshed_goldens: Path,
    ) -> None:
        """The engine function the future gates call is the same one the CLI
        wraps: a direct call returns zero problems on clean goldens."""
        problems, advisories = check_sequences(docs_root=docs_tree, goldens_root=refreshed_goldens)
        assert problems == ()
        assert any("run_status" in advisory for advisory in advisories)


class TestProfilePrerequisiteGate:
    def test_enrolled_page_without_profile_mention_is_refused(self, tmp_path: Path) -> None:
        page = tmp_path / "no-profile.md"
        page.write_text(
            "# No prerequisite\n\nProse without the requirement.\n\n"
            "```{cli-sequence} no-profile-case\n"
            ":verify: Verify the listing succeeds.\n"
            "```\n",
            encoding="utf-8",
        )
        _write_contract(
            tmp_path,
            "no-profile",
            "no-profile-case",
            '@result aeat --format json config profile list\n@expect status == "success"',
        )
        _, problems = discover_sequences(docs_root=tmp_path)
        assert any(
            "valid-profile prerequisite" in problem and "'no-profile'" in problem and "profile-setup.md" in problem
            for problem in problems
        ), problems

    def test_profile_link_above_the_first_directive_qualifies(self, tmp_path: Path) -> None:
        page = tmp_path / "linked.md"
        page.write_text(
            "# Linked prerequisite\n\n"
            "You need a profile: see [Create your profile](../how-to/profile-setup.md).\n\n"
            "```{cli-sequence} linked-case\n"
            ":verify: Verify the listing succeeds.\n"
            "```\n",
            encoding="utf-8",
        )
        _write_contract(
            tmp_path,
            "linked",
            "linked-case",
            '@result aeat --format json config profile list\n@expect status == "success"',
        )
        _, problems = discover_sequences(docs_root=tmp_path)
        assert problems == ()

    def test_mention_below_the_first_directive_does_not_qualify(self, tmp_path: Path) -> None:
        page = tmp_path / "too-late.md"
        page.write_text(
            "# Too late\n\n"
            "```{cli-sequence} too-late-case\n"
            ":verify: Verify the listing succeeds.\n"
            "```\n\n"
            "Afterwards: create a profile with `aeat config profile create`.\n",
            encoding="utf-8",
        )
        _write_contract(
            tmp_path,
            "too-late",
            "too-late-case",
            '@result aeat --format json config profile list\n@expect status == "success"',
        )
        _, problems = discover_sequences(docs_root=tmp_path)
        assert any("valid-profile prerequisite" in problem for problem in problems), problems

    def test_page_without_directives_needs_no_mention(self, tmp_path: Path) -> None:
        (tmp_path / "plain.md").write_text("# Plain narrative page\n\nNo sequences here.\n", encoding="utf-8")
        _, problems = discover_sequences(docs_root=tmp_path)
        assert problems == ()


def _coherence_page(_second_expected_status: str) -> str:
    """A two-sequence page whose second sequence only holds CUMULATIVELY.

    Sequence one creates a Modelo 130 work unit; sequence two runs the SAME
    idempotent-guarded create, which reports ``status == "reused"`` only when
    the first sequence's state is still present — the genuine shared-sandbox
    proof (an isolated run would report ``"created"``).
    """
    return (
        "# Coherent page\n\n"
        "Create a profile first with `aeat config profile create`.\n\n"
        "```{cli-sequence} coherence-first\n"
        ":verify: Verify the draft was created.\n"
        "```\n\n"
        "```{cli-sequence} coherence-second\n"
        ":verify: Verify the draft is reused.\n"
        "```\n"
    )


def _write_coherence_contracts(root: Path, page: str, second_expected_status: str) -> None:
    """Write the two private contracts used by one cumulative-page fixture."""
    create = "aeat --format json app modelo work create --modelo 130 --year 2025 --period 1T"
    _write_contract(
        root,
        page,
        "coherence-first",
        f'{create.replace("aeat ", "@result aeat ", 1)}\n@expect result.status == "created"\n@expect exit_code == 0',
    )
    _write_contract(
        root,
        page,
        "coherence-second",
        f"{create.replace('aeat ', '@result aeat ', 1)}\n"
        f'@expect result.status == "{second_expected_status}"\n'
        "@expect exit_code == 0",
    )


class TestPageCoherenceMode:
    def test_cumulative_page_state_is_shared_and_coherent(self, tmp_path: Path) -> None:
        """The green proof IS the cumulative proof: sequence two's
        ``status == "reused"`` expectation can only hold because sequence one's
        work unit survives in the shared page sandbox."""
        (tmp_path / "coherent.md").write_text(_coherence_page("reused"), encoding="utf-8")
        _write_coherence_contracts(tmp_path, "coherent", "reused")
        problems = check_page_coherence(docs_root=tmp_path)
        assert problems == (), problems

    def test_incoherent_page_fails_with_the_tier_named(self, tmp_path: Path) -> None:
        """A page whose prose-described expectation breaks under cumulative
        state fails naming the tier, page, sequence, frame, and the live vs
        expected values — never a golden-tier message."""
        (tmp_path / "incoherent.md").write_text(_coherence_page("created"), encoding="utf-8")
        _write_coherence_contracts(tmp_path, "incoherent", "created")
        problems = check_page_coherence(docs_root=tmp_path)
        assert len(problems) == 1
        problem = problems[0]
        assert problem.startswith(COHERENCE_TIER_PREFIX)
        assert "'incoherent'" in problem and "coherence-second" in problem
        assert '@expect result.status == "created" failed' in problem
        assert '"reused"' in problem  # the live cumulative value is named

    def test_goldens_are_untouched_by_the_coherence_tier(
        self,
        docs_tree: Path,
        refreshed_goldens: Path,
    ) -> None:
        """Coherence never reads or writes goldens: the tier passes with NO
        goldens root at all, and the per-sequence golden check still passes
        unchanged afterwards — the two contracts stay independent."""
        problems = check_page_coherence(docs_root=docs_tree)
        assert problems == ()
        golden_problems, _ = check_sequences(docs_root=docs_tree, goldens_root=refreshed_goldens)
        assert golden_problems == ()

    def test_all_static_page_passes_the_coherence_tier(self, tmp_path: Path) -> None:
        """An all-@static page runs nothing, so the coherence tier skips it cleanly.

        Regression: an all-@static sequence has no executed frames, so it yields
        no transcript; the coherence tier must skip it, never try to build an
        empty SequenceTranscript (which raised a pydantic ``too_short`` error and
        aborted the whole page's cumulative run)."""
        page = (
            "# Live reads\n\n"
            "Set up a profile first with `aeat config profile create`.\n\n"
            "```{cli-sequence} live-notifications-static\n"
            "```\n"
        )
        (tmp_path / "live.md").write_text(page, encoding="utf-8")
        _write_contract(
            tmp_path,
            "live",
            "live-notifications-static",
            "@step Pull your notifications from AEAT.\n"
            "@static aeat app live notifications pull\n"
            "@blocked live-aeat The pull verb fetches from the AEAT sede; the sandbox refuses it.\n"
            "@step View the stored snapshot.\n"
            "@static aeat app live notifications latest\n"
            "@blocked live-aeat The app live group reads the operator's authenticated sede session.",
        )
        problems = check_page_coherence(docs_root=tmp_path)
        assert problems == (), problems

    def test_cli_coherence_flag_reds_with_the_tier_note(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (tmp_path / "incoherent.md").write_text(_coherence_page("created"), encoding="utf-8")
        _write_coherence_contracts(tmp_path, "incoherent", "created")
        exit_code = main(["check", "--coherence", "--docs-root", str(tmp_path)])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert COHERENCE_TIER_PREFIX in captured.err
        assert "cumulatively in one sandbox" in captured.err
        assert "refresh does not apply" in captured.err

    def test_cli_coherence_flag_refuses_sequence_scoping(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["check", "--coherence", "--sequence", "anything"])
        assert exit_code == 2
        assert "--page, not --sequence" in capsys.readouterr().err

    def test_cli_bounded_coherence_runs_the_discovered_page_in_a_real_child(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (tmp_path / "coherent.md").write_text(_coherence_page("reused"), encoding="utf-8")
        _write_coherence_contracts(tmp_path, "coherent", "reused")
        discovered, discovery_problems = discover_sequences(docs_root=tmp_path)
        assert discovery_problems == ()
        page = discovered[0].page
        timeout = 60.0

        exit_code = main(
            [
                "check",
                "--coherence",
                "--page",
                page,
                "--docs-root",
                str(tmp_path),
                "--timeout",
                str(timeout),
            ],
        )

        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.err == ""
        assert "cli-sequence page coherence: clean" in captured.out


@pytest.mark.parametrize("invalid_timeout", ["nan", "inf", "-inf", "0", "-1"])
def test_cli_rejects_invalid_timeout_without_a_traceback(
    invalid_timeout: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["check", f"--timeout={invalid_timeout}"])

    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert "finite number greater than zero" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    "invalid_record",
    [
        {
            "page": "",
            "sequence_id": "receipt",
            "frame_index": 0,
            "frame_source": "body",
            "frame_line": 1,
            "argv": ["aeat"],
        },
        {
            "page": "page",
            "sequence_id": "receipt",
            "frame_index": -1,
            "frame_source": "body",
            "frame_line": 1,
            "argv": ["aeat"],
        },
        {
            "page": "page",
            "sequence_id": "receipt",
            "frame_index": 0,
            "frame_source": "",
            "frame_line": 1,
            "argv": ["aeat"],
        },
        {
            "page": "page",
            "sequence_id": "receipt",
            "frame_index": 0,
            "frame_source": "body",
            "frame_line": 0,
            "argv": ["aeat"],
        },
        {
            "page": "page",
            "sequence_id": "receipt",
            "frame_index": 0,
            "frame_source": "body",
            "frame_line": 1,
            "argv": [],
        },
        {
            "page": "page",
            "sequence_id": "receipt",
            "frame_index": 0,
            "frame_source": "body",
            "frame_line": 1,
            "argv": [""],
        },
    ],
)
def test_timeout_diagnostic_rejects_malformed_child_receipts(
    tmp_path: Path,
    invalid_record: dict[str, object],
) -> None:
    journal = tmp_path / "last-frame.json"
    journal.write_text(json.dumps(invalid_record), encoding="utf-8")

    diagnostic = _timeout_progress_diagnostic(journal, timeout=1.0)

    assert "before the child recorded an executing frame" in diagnostic
