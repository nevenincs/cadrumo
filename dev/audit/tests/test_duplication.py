r"""Real-behavior tests for the single duplication runner.

These tests exist because ``dev/audit/report.py`` once reported the duplication
dimension GREEN ("no clones found") on a tree carrying 65 real clones. The lie
had two independent causes, and both are pinned here:

* the source path was passed as ``str(Path("src/cadrumo"))``, which renders
  ``src\\cadrumo`` on Windows and matches nothing inside jscpd's glob engine, and
* the classifier collapsed "jscpd inspected nothing" into ``total == 0``, which
  is indistinguishable from "jscpd inspected everything and found nothing"
  unless ``files_analyzed`` is read.

Crucially the failing scan exits **0**, so a returncode check alone never catches
it. Every test below drives the real jscpd subprocess. Where a failure condition
must be forced, the CONDITION is forced (a real bad path, a real non-zero-exit
process, a real timeout) rather than stubbing the parser -- a mocked parser would
re-create exactly the blind spot these tests exist to close.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
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
from dev.audit.report import Status, audit_duplication

# Dev tooling sits outside the hexagon; the sibling dev/ suites classify as hex_core.
# The unit/integration axis is per-test: the real-jscpd tests are integration.
pytestmark = [pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]

# The real stdout jscpd emitted, byte for byte, under the original defect: a
# path it could not match, a 0 exit code, and a lone timing line. Captured from
# a live run rather than hand-written.
_DEFECT_STDOUT_EMPTY_SCAN = "\x1b[3m\x1b[90mtime\x1b[39m\x1b[23m: 0.135ms\n"


def _require_npx() -> None:
    """Assert the real npx binary is present for an integration test.

    The sanctioned convention for external-binary integration tests in this
    repo is to assert the tool is present, not to self-skip when it is absent
    (see ``dev/release/tests/test_justfile_release_guidance.py`` and
    ``dev/packaging/tests/test_smoke_split_install_sequence.py``). ``skipif`` is
    forbidden by ``test_no_skip_xfail`` for tests outside the source tree.
    """
    assert shutil.which("npx") is not None, "npx is required to run the real jscpd duplication scan"


@pytest.mark.unit
def test_command_passes_a_posix_source_path() -> None:
    r"""The source path must be POSIX on every OS.

    This is the original defect: ``str(Path("src/cadrumo"))`` renders
    ``src\\cadrumo`` on Windows, jscpd matches zero files, and the scan silently
    proves nothing while exiting 0.
    """
    command = jscpd_command("npx")

    assert "src/cadrumo" in command
    assert not any("\\" in arg for arg in command), f"a backslash path reached jscpd: {command}"


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
def test_observed_zero_cannot_be_constructed_without_inspected_files() -> None:
    """The green state structurally requires evidence the tree was inspected."""
    with pytest.raises(ValueError, match="demonstrably inspected"):
        DuplicationResult.observed_zero(files_analyzed=0)


@pytest.mark.integration
def test_real_clean_subtree_scan_observes_zero() -> None:
    """A real zero-clone jscpd run over a real clone-free tree is observed_zero.

    ``dev/audit`` is genuinely clone-free, so this is the only honest route to
    the green state: a real subprocess that really looked at real files.
    """
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT, source_root=Path("dev/audit"))

    assert result.outcome is DuplicationOutcome.OBSERVED_ZERO
    assert result.is_green is True
    assert result.clone_count == 0
    assert result.files_analyzed > 0, "a green verdict must prove files were analysed"


@pytest.mark.integration
def test_real_production_tree_scan_reports_measured_clones() -> None:
    """The real production tree carries clones and must report them as AMBER debt.

    This is the assertion the old runner inverted. The count is advisory and
    drifts as code lands, so this pins the honest SHAPE (clones observed, with a
    real measured count over a real analysed corpus) rather than a brittle
    literal.
    """
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT)

    assert result.outcome is DuplicationOutcome.CLONES
    assert result.is_green is False, "the production tree carries clones; green here is the false-green defect"
    assert result.clone_count > 0
    assert result.files_analyzed > 1000, (
        "the production tree carries >1000 source files; a small count means a partial scan"
    )
    assert result.groups, "a clone verdict must carry the clone records backing it"
    assert result.duplicated_pct


@pytest.mark.integration
def test_real_bad_source_path_is_unavailable_not_green() -> None:
    """A real scan of a path that matches nothing must refuse to claim cleanliness."""
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT, source_root=Path("src/cadrumo/no-such-directory"))

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False


@pytest.mark.integration
def test_real_timeout_is_unavailable_not_green() -> None:
    """A real jscpd run cut off by the timeout must report unavailable."""
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT, timeout=0.001)

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False
    assert "timeout" in result.reason


@pytest.mark.integration
def test_real_nonzero_exit_is_unavailable_not_green() -> None:
    """A real subprocess that exits non-zero must report unavailable.

    The failure CONDITION is forced through the injected ``which`` seam, not by
    patching global state: the resolver returns a real Python interpreter, so
    ``run_duplication_scan`` really launches ``<python> --yes jscpd@4.2.0 ...``,
    which the interpreter rejects and exits non-zero. A genuinely failing
    process is what is under test -- the parser is untouched.
    """
    result = run_duplication_scan(_REPO_ROOT, which=lambda _name: sys.executable)

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False
    assert "exited" in result.reason


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
def test_console_report_names_unavailability_instead_of_claiming_clean() -> None:
    """The operator-facing report must not print a clean line for a failed scan."""
    rendered = render_console_report(DuplicationResult.unavailable("npx was not found on PATH"))

    assert "unavailable" in rendered
    assert "no clones found" not in rendered


@pytest.mark.integration
def test_health_report_duplication_dimension_is_amber_with_a_measured_count() -> None:
    """End-to-end: the health dashboard must not render the false green.

    The tree carries clones, so the honest verdict is AMBER carrying the count.
    Per the advisory clone-count policy this dimension is never RED on clones.
    """
    _require_npx()
    dimension = audit_duplication(_REPO_ROOT)

    assert dimension.status is not Status.GREEN, "the production tree carries clones; GREEN is the reported lie"
    assert dimension.status is Status.AMBER
    assert "clone cluster(s)" in dimension.headline


@pytest.mark.unit
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

    builders = [
        rel for rel in candidates if rel not in exempt and "jscpd@" in (_REPO_ROOT / rel).read_text(encoding="utf-8")
    ]

    assert builders == [], f"jscpd must be invoked from exactly one runner; found: {builders}"


@pytest.mark.unit
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


_WHERE_PATH = re.compile(r"^-?\s*(.+?\.py) \[")


def _paths_from_where(entries: list[str]) -> frozenset[str]:
    """Extract the bare file paths a disposition's ``where`` list names."""
    paths = set()
    for entry in entries:
        match = _WHERE_PATH.match(entry)
        assert match, f"disposition `where` entry has no parseable path: {entry!r}"
        paths.add(match.group(1))
    return frozenset(paths)


def _paths_from_group(group: CloneGroup) -> frozenset[str]:
    """Extract the bare file paths a live ``CloneGroup``'s console block names.

    ``CloneGroup.lines`` renders relative to the repository root
    (``src/cadrumo/...``), while the dispositions file records paths relative
    to ``src/cadrumo/`` -- the same convention its own header states.
    """
    paths = set()
    for line in group.lines[1:]:
        stripped = line.strip()
        match = _WHERE_PATH.match(stripped)
        if not match:
            continue
        path = match.group(1)
        paths.add(path.removeprefix("src/cadrumo/"))
    return frozenset(paths)


@pytest.mark.integration
def test_every_observed_clone_group_has_a_recorded_disposition() -> None:
    """Every clone group the live scan observes must carry a recorded disposition.

    The plan's own verification criterion -- every observed clone group carries
    an explicit recorded disposition -- had no gate anywhere in the tree; the
    claim could not be checked and could rot silently as consolidations landed.
    This asserts COVERAGE (each live group's file pair is recorded in the
    dispositions file), never a COUNT: the clone count is advisory debt per the
    governing ADR, so a count assertion would fight that ADR and go red on
    every genuine consolidation. The record is a superset by design -- a group
    disappearing is progress, not a gate failure -- while a NEW, unrecorded
    group is exactly what this gate exists to catch.
    """
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT)
    assert result.outcome is DuplicationOutcome.CLONES, (
        "the production tree is expected to carry advisory clone debt; "
        "if this ever goes clean, update this test rather than deleting it"
    )

    dispositions_path = _REPO_ROOT / "dev" / "audit" / "duplication_dispositions.toml"
    dispositions = tomllib.loads(dispositions_path.read_text(encoding="utf-8"))
    recorded = {_paths_from_where(group["where"]) for group in dispositions["group"]}

    uncovered = [group.render() for group in result.groups if _paths_from_group(group) not in recorded]

    assert not uncovered, (
        "the live scan observed clone group(s) with no recorded disposition in "
        f"duplication_dispositions.toml:\n\n{chr(10).join(uncovered)}"
    )
