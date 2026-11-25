"""Clean-verdict reuse in the quality suite, exercised on small real repository trees.

Each case builds a tree with a real detector script, real declared inputs and a
real pytest positive control, then runs the suite's own scheduler over it. The
detector appends to a run log outside the tree, so whether a gate ran or was
reused is read from what actually executed, not from the suite's own claim.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

from dev.exit_codes import TOOL_BROKEN
from dev.paths import REPO_ROOT
from dev.source_tree import repository_files

from .. import suite
from ..suite import GATES, Gate, run_gates
from ..suite_verdicts import (
    REUSE,
    REUSE_DISABLED,
    Environment,
    InputSelection,
    KeyRefusal,
    ReuseDeclaration,
    TreeSnapshot,
    VerdictKey,
    current_environment,
    positive_control_command,
    read_verdict,
    reusable,
    verdict_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_GATE: Final[str] = "check-fixture"

_DETECTOR: Final[str] = """\
import pathlib, sys
data = pathlib.Path(sys.argv[1])
log = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
if log is not None:
    with log.open("a", encoding="utf-8") as handle:
        handle.write("ran\\n")
files = sorted(data.glob("*.txt"))
if not files:
    print("no input files")
    raise SystemExit(7)
found = [path.name for path in files if "DEFECT" in path.read_text(encoding="utf-8")]
for name in found:
    print(f"defect in {name}")
raise SystemExit(1 if found else 0)
"""

_CONTROL: Final[str] = """\
import pathlib, subprocess, sys

DETECTOR = pathlib.Path(__file__).resolve().parent.parent / "detector.py"


def test_detector_reports_a_planted_defect(tmp_path):
    (tmp_path / "planted.txt").write_text("DEFECT", encoding="utf-8")
    result = subprocess.run([sys.executable, str(DETECTOR), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "defect in planted.txt" in result.stdout
"""


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "controls").mkdir()
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[tool.fixture]\nlimit = 1\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "detector.py").write_text(_DETECTOR, encoding="utf-8")
    (root / "controls" / "test_control.py").write_text(_CONTROL, encoding="utf-8")
    (root / "data" / "a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "data" / "b.txt").write_text("beta\n", encoding="utf-8")
    return root


def _declaration(*, scanned: tuple[str, ...] = ("data",)) -> ReuseDeclaration:
    return ReuseDeclaration(
        scanned=(InputSelection(scanned, frozenset({".txt"})),),
        tools=("pytest",),
        executables=(),
        positive_control=("controls/test_control.py::test_detector_reports_a_planted_defect",),
    )


def _detector_gate(root: Path, log: Path) -> Gate:
    return Gate(_GATE, (sys.executable, str(root / "detector.py"), str(root / "data"), str(log)))


def _runs(log: Path) -> int:
    return len(log.read_text(encoding="utf-8").splitlines()) if log.is_file() else 0


@pytest.fixture
def declared(monkeypatch: pytest.MonkeyPatch) -> Callable[[ReuseDeclaration], None]:
    def declare(declaration: ReuseDeclaration) -> None:
        monkeypatch.setattr(suite, "REUSE", {_GATE: declaration})

    return declare


def test_a_clean_verdict_is_reused_on_identical_inputs(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None]
) -> None:
    root, log, verdicts = _tree(tmp_path), tmp_path / "runs.log", tmp_path / "verdicts"
    declared(_declaration())

    [first] = run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)
    [second] = run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    assert first.result.status == "passed"
    assert first.result.note == "clean verdict recorded"
    record = read_verdict(verdicts, _GATE)
    assert record is not None
    assert record["verdict"] == "clean"
    assert record["scanned_files"] == 2
    assert record["positive_control"] == {"nodes": list(_declaration().positive_control), "passed": True}
    assert second.result.status == "reused"
    assert second.result.returncode == 0
    assert _runs(log) == 1


@pytest.mark.parametrize(
    "changed",
    ["data/a.txt", "pyproject.toml", "uv.lock", "detector.py", "controls/test_control.py", ".gitignore"],
)
def test_changing_one_byte_of_a_declared_input_forces_a_rerun(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None], changed: str
) -> None:
    root, log, verdicts = _tree(tmp_path), tmp_path / "runs.log", tmp_path / "verdicts"
    declared(_declaration())
    run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    target = root / changed
    target.write_bytes(target.read_bytes() + b"#")
    [again] = run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    assert again.result.status == "passed"
    assert _runs(log) == 2


def test_a_file_outside_the_declared_inputs_does_not_force_a_rerun(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None]
) -> None:
    """The key is the declared inputs only, so an unrelated file leaves the verdict standing."""
    root, log, verdicts = _tree(tmp_path), tmp_path / "runs.log", tmp_path / "verdicts"
    declared(_declaration())
    run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    (root / "notes.md").write_text("unrelated\n", encoding="utf-8")
    (root / "ignored").mkdir()
    (root / "ignored" / "c.txt").write_text("DEFECT\n", encoding="utf-8")
    [again] = run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    assert again.result.status == "reused"
    assert _runs(log) == 1


def test_a_red_is_never_recorded_and_always_reruns(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None]
) -> None:
    root, log, verdicts = _tree(tmp_path), tmp_path / "runs.log", tmp_path / "verdicts"
    (root / "data" / "b.txt").write_text("DEFECT\n", encoding="utf-8")
    declared(_declaration())

    [first] = run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)
    [second] = run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    assert first.result.status == second.result.status == "failed"
    assert "defect in b.txt" in second.result.output
    assert read_verdict(verdicts, _GATE) is None
    assert _runs(log) == 2


def test_a_zero_file_input_set_fails_even_when_the_tool_exits_clean(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None]
) -> None:
    root, verdicts = _tree(tmp_path), tmp_path / "verdicts"
    declared(_declaration(scanned=("absent",)))
    lenient = Gate(_GATE, (sys.executable, "-c", "pass"))

    [outcome] = run_gates([lenient], verdict_dir=verdicts, root=root)

    assert outcome.result.status == "failed"
    assert outcome.result.returncode == TOOL_BROKEN
    assert "zero files" in outcome.result.output
    assert read_verdict(verdicts, _GATE) is None


@pytest.mark.parametrize("stored", [b"{not json", b"[]", b"\xff\xfe", b""])
def test_an_unreadable_verdict_file_means_a_full_run(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None], stored: bytes
) -> None:
    root, log, verdicts = _tree(tmp_path), tmp_path / "runs.log", tmp_path / "verdicts"
    declared(_declaration())
    run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    (verdicts / f"{_GATE}.json").write_bytes(stored)
    [again] = run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    assert again.result.status == "passed"
    assert _runs(log) == 2
    assert read_verdict(verdicts, _GATE) is not None, "a fresh clean run publishes a readable verdict again"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("key", "0" * 64),
        ("verdict", "failed"),
        ("scanned_files", 0),
        ("positive_control", {"nodes": [], "passed": True}),
    ],
)
def test_a_recorded_verdict_differing_in_any_field_is_not_reused(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None], field: str, value: object
) -> None:
    root, log, verdicts = _tree(tmp_path), tmp_path / "runs.log", tmp_path / "verdicts"
    declared(_declaration())
    run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)
    path = verdicts / f"{_GATE}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record[field] = value
    path.write_text(json.dumps(record), encoding="utf-8")

    [again] = run_gates([_detector_gate(root, log)], verdict_dir=verdicts, root=root)

    assert again.result.status == "passed"
    assert _runs(log) == 2


def test_without_a_verdict_directory_every_gate_runs_and_nothing_is_recorded(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None]
) -> None:
    root, log = _tree(tmp_path), tmp_path / "runs.log"
    declared(_declaration())

    outcomes = [run_gates([_detector_gate(root, log)], root=root)[0] for _ in range(2)]

    assert [outcome.result.status for outcome in outcomes] == ["passed", "passed"]
    assert all(outcome.key is None and outcome.record is None for outcome in outcomes)
    assert _runs(log) == 2


def test_a_failing_positive_control_turns_a_clean_gate_red_and_records_nothing(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None]
) -> None:
    """A detector that cannot see a planted defect has not shown the tree is clean."""
    root, verdicts = _tree(tmp_path), tmp_path / "verdicts"
    (root / "detector.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    declared(_declaration())

    [outcome] = run_gates([Gate(_GATE, (sys.executable, str(root / "detector.py")))], verdict_dir=verdicts, root=root)

    assert outcome.result.status == "failed"
    assert outcome.result.returncode == TOOL_BROKEN
    assert "positive control failed" in outcome.result.output
    assert read_verdict(verdicts, _GATE) is None


def test_inputs_that_change_while_the_suite_runs_are_not_recorded(
    tmp_path: Path, declared: Callable[[ReuseDeclaration], None]
) -> None:
    root, verdicts = _tree(tmp_path), tmp_path / "verdicts"
    declared(_declaration())
    editing = Gate(
        _GATE,
        (
            sys.executable,
            "-c",
            "import pathlib, sys; target = pathlib.Path(sys.argv[1]); target.write_text('edited\\n', encoding='utf-8')",
            str(root / "data" / "a.txt"),
        ),
    )

    [outcome] = run_gates([editing], verdict_dir=verdicts, root=root)

    assert outcome.result.status == "passed"
    assert "changed while the suite ran" in outcome.result.note
    assert read_verdict(verdicts, _GATE) is None


def _environment(**distributions: str) -> Environment:
    return Environment(
        interpreter="CPython fixture",
        distributions={"pytest": "8.0.0", **distributions},
        variables=(("CADRUMO_FIXTURE", "1"),),
        executables={},
    )


def _snapshot() -> TreeSnapshot:
    return TreeSnapshot(
        files={"data/a.txt": "1" * 64, "pyproject.toml": "2" * 64},
        unreadable=frozenset(),
        unlisted_python=(),
    )


def test_a_changed_tool_version_changes_the_key_and_refuses_the_old_verdict() -> None:
    declaration = _declaration()
    before = verdict_key(_GATE, ("tool",), declaration, _snapshot(), _environment())
    after = verdict_key(_GATE, ("tool",), declaration, _snapshot(), _environment(pytest="8.0.1"))
    assert isinstance(before, VerdictKey) and isinstance(after, VerdictKey)
    record = {
        "schema": "cadrumo-static-check-verdict/v1",
        "check": _GATE,
        "key": before.key,
        "verdict": "clean",
        "scanned_files": 1,
        "positive_control": {"nodes": list(declaration.positive_control), "passed": True},
    }

    assert before.key != after.key
    assert reusable(record, _GATE, before, declaration)
    assert not reusable(record, _GATE, after, declaration)


@pytest.mark.parametrize(
    ("environment", "snapshot", "reason"),
    [
        (
            _environment(),
            TreeSnapshot({"data/a.txt": "1" * 64}, frozenset({"pyproject.toml"}), ()),
            "could not be read",
        ),
        (
            _environment(),
            TreeSnapshot({"data/a.txt": "1" * 64}, frozenset(), ("src/stray.py",)),
            "outside the inclusion",
        ),
        (
            Environment("CPython fixture", {}, (), {}),
            TreeSnapshot({"data/a.txt": "1" * 64}, frozenset(), ()),
            "tool version unavailable",
        ),
    ],
)
def test_missing_or_unreadable_metadata_yields_no_key(
    environment: Environment, snapshot: TreeSnapshot, reason: str
) -> None:
    key = verdict_key(_GATE, ("tool",), _declaration(), snapshot, environment)
    assert isinstance(key, KeyRefusal)
    assert reason in key.reason


def test_a_changed_environment_variable_or_command_changes_the_key() -> None:
    declaration = _declaration()
    base = verdict_key(_GATE, ("tool",), declaration, _snapshot(), _environment())
    variable = verdict_key(
        _GATE,
        ("tool",),
        declaration,
        _snapshot(),
        Environment("CPython fixture", {"pytest": "8.0.0"}, (("CADRUMO_FIXTURE", "2"),), {}),
    )
    command = verdict_key(_GATE, ("tool", "--strict"), declaration, _snapshot(), _environment())
    assert isinstance(base, VerdictKey) and isinstance(variable, VerdictKey) and isinstance(command, VerdictKey)
    assert len({base.key, variable.key, command.key}) == 3


@pytest.mark.parametrize(
    "variable", ["CADRUMO_CI_REPORTS_DIR", "CADRUMO_CI_REPORT_NAME", "CADRUMO_PYTEST_WORKERS", "CADRUMO_GATE_BUDGET"]
)
def test_a_per_run_location_or_worker_variable_leaves_the_key_unchanged(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    def key_with(value: str) -> str:
        monkeypatch.setenv(variable, value)
        key = verdict_key(_GATE, ("tool",), _declaration(), _snapshot(), current_environment())
        assert isinstance(key, VerdictKey)
        return key.key

    assert key_with("first-run") == key_with("second-run")


def test_any_other_product_variable_changes_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def key_with(value: str) -> str:
        monkeypatch.setenv("CADRUMO_STORAGE_ROOT", value)
        key = verdict_key(_GATE, ("tool",), _declaration(), _snapshot(), current_environment())
        assert isinstance(key, VerdictKey)
        return key.key

    assert key_with("first-root") != key_with("second-root")


# ---------------------------------------------------------------------------
# The live declarations
# ---------------------------------------------------------------------------

_NATIVE_GATES: Final[frozenset[str]] = frozenset({"check-frontend", "check-rust"})


def test_every_gate_either_declares_its_reuse_inputs_or_states_why_it_always_runs() -> None:
    names = {name for name, _ in GATES} | _NATIVE_GATES
    assert set(REUSE) | set(REUSE_DISABLED) == names
    assert not set(REUSE) & set(REUSE_DISABLED)
    assert all(reason.strip() for reason in REUSE_DISABLED.values())


def test_every_reused_gate_declares_a_positive_control_and_scanned_inputs() -> None:
    for name, declaration in REUSE.items():
        assert declaration.positive_control, f"{name} is reused without a positive control"
        assert declaration.scanned, f"{name} declares no scanned inputs"


def test_every_live_scanned_input_set_resolves_to_files() -> None:
    """An empty live selection would make a reused verdict a statement about nothing."""
    listed = repository_files(REPO_ROOT)
    empty = [
        name
        for name, declaration in REUSE.items()
        if not any(selection.selects(path) for path in listed for selection in declaration.scanned)
    ]
    assert not empty, f"these gates' declared inputs select no repository file: {empty}"


def test_every_positive_control_node_is_collected() -> None:
    """A renamed control test would otherwise leave reuse resting on a node that no longer exists."""
    nodes = sorted({node for declaration in REUSE.values() for node in declaration.positive_control})
    command = positive_control_command(ReuseDeclaration((), (), (), tuple(nodes)))
    collect = [*command[:3], "--collect-only", *command[3:]]
    completed = suite.run_gate("positive-control-collection", tuple(collect), cwd=REPO_ROOT)
    assert completed.returncode == 0, completed.output[-4000:]
