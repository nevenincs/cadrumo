"""Real-behaviour tests for the refresh / check CLI modes (W02.P05).

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

from ..__main__ import check_sequences, discover_sequences, main, refresh_sequences

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/cli-mode-case"
_SEQUENCE_ID = "cli-mode-case"

#: A real enrolled page: one directive, a deliberately-unconsumed capture (the
#: advisory case), and a semantically asserted result frame.
_PAGE_TEXT = (
    "# CLI mode case\n"
    "\n"
    "Narrative prose around the sequence.\n"
    "\n"
    "```{cli-sequence} " + _SEQUENCE_ID + "\n"
    ":verify: Verify the profile listing succeeds.\n"
    "aeat --format json config profile list\n"
    "@capture run_status status\n"
    "@result aeat --format json config profile list\n"
    '@expect status == "success"\n'
    "@expect exit_code == 0\n"
    "```\n"
    "\n"
    "Closing prose.\n"
)


@pytest.fixture(scope="module")
def docs_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("docs-tree")
    target = root / f"{_PAGE}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_PAGE_TEXT, encoding="utf-8")
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
            "```{cli-sequence} faulty-case\n:verify: V.\nnot-a-frame\n```\n",
            encoding="utf-8",
        )
        _, problems = discover_sequences(docs_root=tmp_path)
        assert any("'faulty'" in problem and "not-a-frame" in problem for problem in problems)

    def test_duplicate_sequence_ids_across_pages_are_refused(self, tmp_path: Path) -> None:
        body = (
            "```{cli-sequence} dupe-case\n:verify: V.\n@result aeat config profile list\n@expect exit_code == 0\n```\n"
        )
        (tmp_path / "one.md").write_text(body, encoding="utf-8")
        (tmp_path / "two.md").write_text(body, encoding="utf-8")
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
