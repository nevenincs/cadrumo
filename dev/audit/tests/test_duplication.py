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

import ast
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from ..duplication import (
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


def _mentions_jscpd_outside_docstrings(path: Path) -> bool:
    """True when a file references ``jscpd@`` as code, not as prose.

    A Python docstring that quotes the invocation for documentation -- as
    ``test_duplication_scan`` does to explain what it forces through the
    ``which`` seam -- is prose describing the one real runner, not a second
    command-construction site. Stripping docstring line ranges before
    searching lets the gate tell the two apart without an ever-growing
    per-file exemption list that would need a new entry every time a test
    module documents the invocation it exercises.

    Non-Python executables (the justfile, shell/PowerShell scripts) have no
    docstring concept, so the substring search runs over their full text.
    Unparsable Python cannot be proven docstring-only, so it counts as a hit
    rather than being silently skipped.
    """
    text = path.read_text(encoding="utf-8")
    if "jscpd@" not in text:
        return False
    if path.suffix != ".py":
        return True
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return True

    docstring_lines: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) or not body:
            continue
        first = body[0]
        is_string_expr = (
            isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)
        )
        if not is_string_expr:
            continue
        end = getattr(first, "end_lineno", first.lineno)
        docstring_lines.update(range(first.lineno, end + 1))

    lines = text.splitlines()
    stripped = "\n".join(line for lineno, line in enumerate(lines, start=1) if lineno not in docstring_lines)
    return "jscpd@" in stripped


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
    invocations. Within a Python file, a docstring quoting the invocation for
    documentation (see ``test_duplication_scan``) is excluded from the search
    via :func:`_mentions_jscpd_outside_docstrings`, so a test module can name
    the literal in prose without needing its own exemption entry here.
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

    # Subject floor. This is the runner whose own drifting second copy produced the
    # original false-green; a collapse of the tracked-file enumeration would leave
    # ``candidates`` empty and pass ``builders == []`` while a second invocation
    # survived unseen. Assert the corpus is populated so an empty builder list means
    # "one runner" rather than "nothing was searched".
    assert len(candidates) > 50, (
        f"enumerated only {len(candidates)} executable tracked files; the tree scan collapsed, "
        "so an empty builder list below would mean 'nothing was searched' rather than "
        "'exactly one runner exists'"
    )

    # The one canonical runner, and this test itself: the runner holds the
    # real invocation constant, and this test holds the "jscpd@" literal it
    # searches WITH -- code, not prose, so the docstring exclusion cannot
    # clear either and both stay named here.
    exempt = {"dev/audit/duplication.py", "dev/audit/tests/test_duplication.py"}

    # A tracked path may be absent from the working tree while a peer's
    # deletion is in flight, and this worktree runs many agents at once. A file
    # that does not exist cannot invoke jscpd, so skipping it costs the gate
    # nothing; crashing on it would red this gate for whoever happens to run it
    # mid-deletion.
    builders = [
        rel
        for rel in candidates
        if rel not in exempt and (_REPO_ROOT / rel).is_file() and _mentions_jscpd_outside_docstrings(_REPO_ROOT / rel)
    ]

    assert builders == [], f"jscpd must be invoked from exactly one runner; found: {builders}"


def test_a_second_clone_inside_an_already_recorded_file_is_uncovered() -> None:
    """A new intra-file clone must not inherit another group's disposition.

    Drives the real coverage computation with one independently constructed
    recorded self-clone file-set and one more observed group than that record
    accounts for. Under the previous set-membership read this returned covered,
    so this is the regression pinning the multiset semantics without requiring
    the live disposition record to retain debt forever.
    """
    path = "application/modelo/example.py"
    self_clone_set = frozenset({path})
    recorded = Counter({self_clone_set: 1})
    recorded_here = recorded[self_clone_set]

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
