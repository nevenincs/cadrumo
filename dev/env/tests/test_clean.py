"""Real-behavior gate for `just clean`.

Every assertion runs against a real git repository with a real ``.gitignore``,
real files on disk and a real removal pass. Nothing here mocks git, patches the
classifier, or asserts against a hand-copied expectation of what the module
already computed: the protection rules are the whole safety property of a
command that deletes, and a protection proved by a stub is not proved.

The teeth are the pairs. Each protected family is written into a tree that also
holds a genuine cache, then the removal is applied for real, and the test
asserts both halves -- the cache is gone AND the protected file is still there.
A rule that spared everything would pass one half and fail the other.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT, UTF_8
from ...test_runs.reaper import COMPLETED_RETENTION_SECONDS
from ..clean import (
    FAMILIES,
    TEMP_FAMILY,
    VAR_SCRATCH_FAMILY,
    WORKTREE_FAMILY,
    Entry,
    Verdict,
    assess,
    classify,
    git_observations,
    holds_only_cache,
    in_flight,
    main,
    reclaim,
)
from ..temp_reaper import IDLE_CEILING_SECONDS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

IGNORE_RULES = """\
__pycache__/
*.pyc
.ruff_cache/
build/
.env
env/*
!env/.env.example
var/
secrets/
.vault/
.vaultspec/
.logs/
scratch/
.coverage
"""


def _git(repository: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    assert executable is not None, "git must be on PATH for this gate to mean anything"
    completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, temporary repository
        [executable, "-c", "user.email=gate@example.invalid", "-c", "user.name=gate", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return completed.stdout


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A real git repository carrying this project's protection-relevant ignore rules."""
    root = tmp_path / "worktree"
    root.mkdir()
    _git(root, "init", "--quiet")
    _write(root / ".gitignore", IGNORE_RULES)
    _write(root / "src" / "module.py", "value = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "seed")
    return root


def _verdict_for(entries: list[Entry], relative: str) -> tuple[Verdict, str]:
    matches = [entry for entry in entries if entry.relative.strip("/") == relative.strip("/")]
    assert matches, f"{relative} was not enumerated; got {[entry.relative for entry in entries]}"
    return matches[0].verdict, matches[0].reason


def test_a_cache_is_removed_while_every_protected_family_beside_it_survives(repository: Path) -> None:
    """The load-bearing pair: the removal must actually happen, and must reach nothing protected."""
    cache = _write(repository / "src" / "__pycache__" / "module.cpython-313.pyc")
    protected = {
        "dotenv": _write(repository / ".env", "AEAT_TOKEN=secret\n"),
        "env directory": _write(repository / "env" / ".env.local", "AEAT_TOKEN=secret\n"),
        "secrets": _write(repository / "secrets" / "master.key", "key-material"),
        "local storage": _write(repository / "var" / "storage" / "buckets" / "ledger.db", "encrypted"),
        "vault": _write(repository / ".vault" / "adr" / "decision.md", "# decision\n"),
        "vaultspec": _write(repository / ".vaultspec" / "rules" / "rule.md", "# rule\n"),
        "logs": _write(repository / ".logs" / "test-runs" / "run.log", "evidence"),
    }

    entries = assess(repository)
    reclaimed, removed = reclaim(repository, entries)

    assert not cache.exists(), "the cache the command exists to remove survived"
    assert removed >= 1 and reclaimed > 0, "nothing was reclaimed, so the pair below proves nothing"
    surviving = {name: path.exists() for name, path in protected.items()}
    assert all(surviving.values()), f"a protected family was removed: {surviving}"


def test_a_cache_nested_inside_a_protected_tree_is_spared(repository: Path) -> None:
    """Protection wins over the cache rule, or a `.venv` sweep reaches its own site-packages."""
    buried = _write(repository / "secrets" / "workspace" / "__pycache__" / "stale.pyc")

    reclaim(repository, assess(repository))

    assert buried.exists(), "a protected tree was entered because it contained a cache directory"


def test_the_mixed_var_root_is_split_rather_than_judged_whole(repository: Path) -> None:
    """`var/` carries a cache, an operator's probe trees and key material under one name.

    Collapsing it to a single verdict is wrong in both directions: protecting it
    hides the dev loop's own 346 MB application cache, and reaping it destroys
    release-cohort trees and anything the suffix rules exist to guard. The four
    assertions below are one behaviour, and any single-verdict rule fails at
    least one of them.
    """
    application_cache = _write(repository / "var" / "storage" / "cache" / "registry" / "compiled.pkl")
    application_logs = _write(repository / "var" / "storage" / "logs" / "cadrumo.log", "diagnostic")
    probe_tree = _write(repository / "var" / "repro-cohort" / "wheel.whl", "cohort artefact")
    key_material = _write(repository / "var" / "secrets" / "master.key", "key-material")
    bucket = _write(repository / "var" / "storage" / "buckets" / "ledger.db", "encrypted")

    entries = assess(repository)
    reclaim(repository, entries)

    assert _verdict_for(entries, "var/storage/cache")[0] is Verdict.REAP
    assert not application_cache.exists(), "the dev loop's own application cache survived"
    assert application_logs.exists(), "application logs were removed with the cache beside them"
    assert probe_tree.exists(), "a release-cohort tree was removed by a rule keyed on its parent"
    assert key_material.exists(), "key material under var/ was removed"
    assert bucket.exists(), "an encrypted bucket under var/ was removed"


def test_untracked_work_that_is_not_ignored_is_counted_and_never_touched(repository: Path) -> None:
    """In-flight work is exactly what git reports in status, and none of it is this command's."""
    draft = _write(repository / "src" / "draft_feature.py", "in progress\n")
    _write(repository / "src" / "module.py", "value = 2\n")

    untracked, changed = in_flight(repository)
    reclaim(repository, assess(repository))

    assert untracked == 1 and changed >= 1, f"in-flight work went uncounted: {untracked=} {changed=}"
    assert draft.exists(), "an untracked, non-ignored file was removed"
    assert (repository / "src" / "module.py").read_text(encoding="utf-8") == "value = 2\n"


def test_an_orphaned_directory_of_pure_cache_is_reaped_but_one_holding_a_file_is_not(repository: Path) -> None:
    """The promotion is decided by looking inside, so a single non-cache file must block it."""
    _write(repository / "scratch" / "orphan" / "__pycache__" / "gone.pyc")
    _write(repository / "scratch" / "mixed" / "__pycache__" / "kept.pyc")
    survivor = _write(repository / "scratch" / "mixed" / "capture.json", "{}")

    assert holds_only_cache(repository / "scratch" / "orphan")
    assert not holds_only_cache(repository / "scratch" / "mixed")
    assert not holds_only_cache(repository / "scratch"), "a parent holding a non-cache file must not be promoted"
    assert survivor.exists()


def test_ad_hoc_scratch_is_flagged_rather_than_removed(repository: Path) -> None:
    """An ignored directory this command cannot prove is regenerable is a report line, not a deletion."""
    capture = _write(repository / "scratch" / "half-finished.json", "{}")

    entries = assess(repository)
    verdict, _ = _verdict_for(entries, "scratch")
    reclaim(repository, entries)

    assert verdict is Verdict.FLAG
    assert capture.exists(), "ad-hoc scratch was removed without an operator asking for it"


def test_include_promotes_a_flagged_entry_but_cannot_override_a_protection(repository: Path) -> None:
    """The one operator escape hatch stops at the families whose removal is unrecoverable."""
    _write(repository / "scratch" / "capture.json", "{}")
    _write(repository / "secrets" / "master.key", "key-material")
    promoted = frozenset({"scratch", "secrets"})

    scratch_verdict, _ = classify(repository, "scratch/", promoted=promoted)
    secrets_verdict, secrets_reason = classify(repository, "secrets/", promoted=promoted)

    assert scratch_verdict is Verdict.REAP
    assert secrets_verdict is Verdict.KEEP, f"--include overrode a protection: {secrets_reason}"


def test_the_git_directory_is_reported_and_left_byte_identical(repository: Path) -> None:
    """Every git remedy this command names is one it must not perform."""
    git_dir = repository / ".git"
    before = sorted(
        (path.relative_to(git_dir).as_posix(), path.stat().st_size) for path in git_dir.rglob("*") if path.is_file()
    )

    observations = git_observations(repository)

    after = sorted(
        (path.relative_to(git_dir).as_posix(), path.stat().st_size) for path in git_dir.rglob("*") if path.is_file()
    )
    assert before == after, "the git directory was modified by a command that only reports on it"
    assert any("objects:" in line for line in observations), f"the object-store census is missing: {observations}"


def test_an_interrupted_git_operation_is_reported_and_preserved(repository: Path) -> None:
    """A half-finished rebase is the state a git command resumes from, never a cleanup target."""
    marker = _write(repository / ".git" / "MERGE_HEAD", "0" * 40)

    observations = git_observations(repository)

    assert any("MERGE_HEAD" in line for line in observations), (
        f"an in-flight git operation went unreported: {observations}"
    )
    assert marker.exists()


def test_the_command_exits_zero_on_a_clean_tree_and_on_a_dirty_one(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A maintenance report has no verdict to fail on, whatever it finds.

    Every ``--apply`` here is scoped to ``--only worktree``, and that is a
    correctness requirement rather than tidiness. The temp section's roots are
    the OS temp directory and this checkout's ``.logs/`` -- genuinely global
    locations that no fixture can redirect -- so an unscoped ``--apply`` in a
    test reaps a developer's real abandoned sessions and real test-run evidence
    as a side effect of running the suite. The worktree section is the only one
    whose root this test controls.
    """
    monkeypatch.setattr("dev.env.clean.REPO_ROOT", repository)

    assert main(["--only", WORKTREE_FAMILY]) == 0
    clean_output = capsys.readouterr().out
    assert "Clean:" in clean_output, f"a tree with nothing to decide did not report clean: {clean_output}"

    _write(repository / "src" / "__pycache__" / "module.cpython-313.pyc")
    _write(repository / "scratch" / "capture.json", "{}")
    assert main(["--only", WORKTREE_FAMILY]) == 0
    assert main(["--only", WORKTREE_FAMILY, "--apply"]) == 0
    dirty_output = capsys.readouterr().out
    assert "Clean:" not in dirty_output, "a tree with a spared entry pending a decision reported clean"


def test_every_family_reports_and_only_the_selected_one_runs(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The fold is a dispatch: all three sections by default, exactly one under `--only`.

    Guards the regression the fold invites -- a section quietly dropped from the
    dispatch still prints a confident, complete-looking report, and the family
    it stopped covering accrues unwatched. Each section is identified by the
    heading only it prints.
    """
    monkeypatch.setattr("dev.env.clean.REPO_ROOT", repository)
    headings = {
        WORKTREE_FAMILY: "Regenerable build and cache output",
        VAR_SCRATCH_FAMILY: "Release-build scratch under",
        TEMP_FAMILY: "Claude Code session scratchpads under",
    }

    assert main([]) == 0
    everything = capsys.readouterr().out
    missing = [family for family, heading in headings.items() if heading not in everything]
    assert not missing, f"the default run dropped a section: {missing}"

    for family, heading in headings.items():
        assert main(["--only", family]) == 0
        section = capsys.readouterr().out
        assert heading in section, f"--only {family} did not run its own section"
        others = [other for other, text in headings.items() if other != family and text in section]
        assert not others, f"--only {family} also ran {others}"


def test_var_scratch_is_deferred_by_the_worktree_section_rather_than_double_judged(repository: Path) -> None:
    """Two sections printing a verdict on one directory is how the wrong one gets trusted."""
    _write(repository / "var" / "release-cohort-integration-1234-source" / "clone.txt", "cohort clone")
    _write(repository / "var" / "storage" / "cache" / "compiled.pkl")

    entries = assess(repository)

    deferred = _verdict_for(entries, "var/release-cohort-integration-1234-source")
    assert deferred[0] is Verdict.KEEP
    assert "owning section" in deferred[1], f"the deferral does not say who owns it: {deferred[1]}"
    assert _verdict_for(entries, "var/storage/cache")[0] is Verdict.REAP


def test_the_report_deletes_nothing_anywhere_including_the_temp_families(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The recipe promises "Deletes nothing"; every section must keep that promise.

    The temp section is the one that can break it silently. Its pytest-numbered
    family has no assess-only entry point -- the only call that counts abandoned
    directories also removes them -- so a report that asks for the number acts,
    off-screen, in a directory the operator never named. Asserting on the
    worktree tree alone would never catch it, which is why the sentinel below is
    a real cache the worktree section itself would happily reap under --apply.
    """
    monkeypatch.setattr("dev.env.clean.REPO_ROOT", repository)
    cache = _write(repository / "src" / "__pycache__" / "module.cpython-313.pyc")
    scratch = _write(repository / "scratch" / "capture.json", "{}")

    assert main([]) == 0
    output = capsys.readouterr().out

    assert cache.exists(), "the report removed a cache without --apply"
    assert scratch.exists(), "the report removed spared scratch"
    assert "reaped at every pytest session start" in output, (
        "the numbered-directory family was counted, which means it was reaped, in report mode"
    )


def test_the_justfile_severity_notice_still_matches_the_code_it_describes() -> None:
    """The `clean-apply` warning is load-bearing, so its numbers must not drift.

    An agent reading `just --list` decides from one line whether a command is
    safe to run, and the comment block above the recipe is what a human reads
    before sanctioning a delete. Both quote thresholds that live as constants in
    three different modules. A constant edited without the justfile leaves a
    notice that is confidently, specifically wrong -- the worst state for a
    warning, because it still reads as authoritative.

    Where this stops: it checks the QUOTED THRESHOLDS and the destructive
    marker, not the prose around them. It cannot tell whether the blast radius
    described is still the blast radius; only the behaviour tests above do that.
    """
    justfile = (REPO_ROOT / "justfile").read_text(encoding=UTF_8)
    notice = justfile[justfile.index("Blast radius") : justfile.index("clean-apply *ARGS:")]

    assert "DESTRUCTIVE AND IRREVERSIBLE" in justfile, "the clean-apply --list line lost its severity marker"
    assert "READ-ONLY" in justfile, "the clean --list line lost its read-only marker"
    assert f"{int(IDLE_CEILING_SECONDS / 3600)}h of silence" in notice, (
        "the documented session idle ceiling no longer matches IDLE_CEILING_SECONDS"
    )
    assert f"{int(COMPLETED_RETENTION_SECONDS / 86400)}" in justfile or "retention window" in notice, (
        "the documented test-run retention no longer matches COMPLETED_RETENTION_SECONDS"
    )
    for family in FAMILIES:
        assert family in notice, f"the --only selector {family} is undocumented in the severity notice"
