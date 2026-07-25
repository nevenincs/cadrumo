"""Duplication report shape, parsing and disposition-coverage arithmetic.

In-process checks over synthetic scanner output and the committed disposition
record: the report parses real jscpd shapes, a stdout-empty scan is a named
defect rather than a silent zero, and the coverage read is a per-file-set
multiset comparison so a second unrelated clone inside an already-recorded file
cannot pass unseen.

Split from the live-scan half so each module carries one execution lane; the
gates that actually run jscpd over the tree live in ``test_duplication_scan``.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from dev.audit.duplication import (
    CloneGroup,
    DuplicationOutcome,
    DuplicationResult,
    classify_jscpd_output,
    jscpd_command,
    render_console_report,
    run_duplication_scan,
)

from ._duplication_support import (
    _REPO_ROOT,
    _recorded_dispositions,
    _uncovered_groups,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_DEFECT_STDOUT_EMPTY_SCAN = "\x1b[3m\x1b[90mtime\x1b[39m\x1b[23m: 0.135ms\n"


def _self_clone_group(path: str, first: int, second: int) -> CloneGroup:
    """Build a clone group naming one file twice, in jscpd's console shape."""
    return CloneGroup(
        (
            "Clone found (python):",
            f" - src/cadrumo/{path} [{first}:1 - {first + 10}:9] (10 lines, 120 tokens)",
            f"   src/cadrumo/{path} [{second}:1 - {second + 10}:9]",
        )
    )


def test_command_passes_a_posix_source_path() -> None:
    r"""The source path must be POSIX on every OS.

    This is the original defect: ``str(Path("src/cadrumo"))`` renders
    ``src\\cadrumo`` on Windows, jscpd matches zero files, and the scan silently
    proves nothing while exiting 0.
    """
    command = jscpd_command("npx")

    assert "src/cadrumo" in command
    assert not any("\\" in arg for arg in command), f"a backslash path reached jscpd: {command}"


def test_empty_scan_output_is_unavailable_not_zero() -> None:
    """The recorded defect output must classify as unavailable, never green.

    jscpd exited 0 and printed only a timing line. The pre-fix parser read that
    as ``total = 0`` and rendered GREEN "no clones found".
    """
    result = classify_jscpd_output(_DEFECT_STDOUT_EMPTY_SCAN)

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False
    assert result.clone_count == 0
    assert result.files_analyzed == 0


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("", id="no-output-at-all"),
        pytest.param("Segmentation fault", id="crash-text"),
        pytest.param("Found 0 clones.\n", id="clone-total-without-analysed-file-table"),
        pytest.param("{malformed json spew", id="unparseable-spew"),
    ],
)
def test_unparseable_output_never_classifies_green(raw: str) -> None:
    """No output shape lacking proof-of-inspection may render green.

    ``Found 0 clones.`` alone is included deliberately: a clone total with no
    summary table does not prove any file was read.
    """
    result = classify_jscpd_output(raw)

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False


def test_observed_zero_cannot_be_constructed_without_inspected_files() -> None:
    """The green state structurally requires evidence the tree was inspected."""
    with pytest.raises(ValueError, match="demonstrably inspected"):
        DuplicationResult.observed_zero(files_analyzed=0)


def test_missing_npx_is_unavailable_not_green() -> None:
    """An absent npx must report unavailable rather than an accidental clean run.

    The missing-executable condition is supplied through the injected ``which``
    seam returning ``None`` -- a real resolver contract, not a patch of
    ``shutil.which``.
    """
    result = run_duplication_scan(_REPO_ROOT, which=lambda _name: None)

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False
    assert "npx" in result.reason


def test_clone_output_parses_count_pct_and_groups() -> None:
    """A real clone-bearing console report parses into count, pct, and records."""
    raw = (
        "Clone found (python):\n"
        " - src\\cadrumo\\a.py [34:1 - 49:38] (15 lines, 169 tokens)\n"
        "   src\\cadrumo\\b.py [34:1 - 49:27]\n"
        "\n"
        "│ Format │ Files analyzed │ Total lines │ Total tokens │"
        " Clones found │ Duplicated lines │ Duplicated tokens │\n"
        "│ python │ 1252 │ 290727 │ 1676107 │ 65 │ 1185 (0.41%) │ 10882 (0.65%) │\n"
        "│ Total: │ 1252 │ 290727 │ 1676107 │ 65 │ 1185 (0.41%) │ 10882 (0.65%) │\n"
        "Found 65 clones.\n"
    )

    result = classify_jscpd_output(raw)

    assert result.outcome is DuplicationOutcome.CLONES
    assert result.clone_count == 65
    assert result.files_analyzed == 1252
    assert result.duplicated_pct == "0.41"
    assert len(result.groups) == 1
    assert "src/cadrumo/a.py" in result.groups[0].render(), "clone paths are normalised to POSIX"


def test_console_report_names_unavailability_instead_of_claiming_clean() -> None:
    """The operator-facing report must not print a clean line for a failed scan."""
    rendered = render_console_report(DuplicationResult.unavailable("npx was not found on PATH"))

    assert "unavailable" in rendered
    assert "no clones found" not in rendered


def test_only_one_jscpd_invocation_exists_in_the_tree() -> None:
    """Exactly one module may construct a jscpd command, tree-wide.

    The false-green shipped inside a SECOND, drifting copy of the jscpd command
    that ``report.py`` built for itself. This pins the single-runner shape so the
    measurement tool cannot re-become the duplication it measures.

    Scoped to the whole GIT-TRACKED tree (not just ``dev/**/*.py``), so a
    reintroduced scanner in the justfile, a shell script, ``src/``, or
    ``packaging/`` is caught rather than passing silently. Narrowed to files
    that can actually EXECUTE a command -- Python, the justfile, and
    shell/PowerShell scripts -- so prose in a ``.vault/`` audit record or the
    dispositions TOML's provenance string does not trip a gate about
    invocations.
    """
    git = shutil.which("git")
    assert git is not None, "git is required to enumerate the tracked tree"
    tracked = subprocess.run(  # noqa: S603 - resolved Git with test-owned declarative argv.
        [git, "ls-files"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    executable_suffixes = {".py", ".sh", ".bash", ".ps1", ".cmd", ".bat"}
    candidates = [rel for rel in tracked if Path(rel).name == "justfile" or Path(rel).suffix in executable_suffixes]

    # The one canonical runner, and this test itself: it quotes the invocation
    # in a docstring and names the literal it scans for, neither of which is a
    # second invocation.
    exempt = {"dev/audit/duplication.py", "dev/audit/tests/test_duplication.py"}

    # A tracked path may be absent from the working tree while a peer's
    # deletion is in flight, and this worktree runs many agents at once. A file
    # that does not exist cannot invoke jscpd, so skipping it costs the gate
    # nothing; crashing on it would red this gate for whoever happens to run it
    # mid-deletion.
    builders = [
        rel
        for rel in candidates
        if rel not in exempt
        and (_REPO_ROOT / rel).is_file()
        and "jscpd@" in (_REPO_ROOT / rel).read_text(encoding="utf-8")
    ]

    assert builders == [], f"jscpd must be invoked from exactly one runner; found: {builders}"


def test_dispositions_arithmetic_reconciles() -> None:
    """The dispositions file's own counts must add up.

    The record once declared 65 observed groups while carrying 66 group blocks
    whose own summary section summed to 66 -- an internal contradiction nobody
    caught because nothing read the file. This pins two identities: the
    summary section's four counts must equal the number of ``[[group]]``
    blocks, and the non-actionable counts (the groups within jscpd's own
    inventory) must equal the declared ``observed_groups``.
    """
    dispositions_path = _REPO_ROOT / "dev" / "audit" / "duplication_dispositions.toml"
    dispositions = tomllib.loads(dispositions_path.read_text(encoding="utf-8"))

    groups = dispositions["group"]
    summary = dispositions["summary"]

    assert sum(summary.values()) == len(groups), (
        f"summary sums to {sum(summary.values())} but there are {len(groups)} recorded groups"
    )
    observed = summary["cluster_owned"] + summary["intentional"] + summary["advisory_residue"]
    assert observed == dispositions["meta"]["observed_groups"], (
        f"cluster_owned + intentional + advisory_residue ({observed}) must equal "
        f"meta.observed_groups ({dispositions['meta']['observed_groups']})"
    )


def test_a_second_clone_inside_an_already_recorded_file_is_uncovered() -> None:
    """A new intra-file clone must not inherit another group's disposition.

    Drives the real coverage computation with a real recorded self-clone
    file-set and one more observed group than the record accounts for. Under
    the previous set-membership read this returned covered, so this is the
    regression pinning the multiset semantics.
    """
    recorded = _recorded_dispositions()
    self_clone_sets = sorted((paths for paths in recorded if len(paths) == 1), key=sorted)
    assert self_clone_sets, "the record is expected to carry at least one self-clone entry"
    path = next(iter(self_clone_sets[0]))
    recorded_here = recorded[self_clone_sets[0]]

    at_record = [_self_clone_group(path, 100 * i, 100 * i + 50) for i in range(1, recorded_here + 1)]
    assert _uncovered_groups(at_record, recorded) == [], "observing exactly what is recorded must be covered"

    one_extra = [*at_record, _self_clone_group(path, 9000, 9500)]
    surplus = _uncovered_groups(one_extra, recorded)
    assert len(surplus) == 1, f"one clone group beyond the record must be flagged, got {len(surplus)}"


def test_a_landed_consolidation_does_not_fail_the_coverage_read() -> None:
    """Observing FEWER groups than recorded is progress, not a gate failure.

    The record is a superset by design. This pins the asymmetry, so a future
    tightening cannot quietly turn the coverage read into a clone-count
    assertion, which this project treats as advisory debt rather than a gate.
    """
    recorded = _recorded_dispositions()
    assert _uncovered_groups((), recorded) == []
