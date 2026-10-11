"""The recorded command-to-operation join is the one derived from the live tree.

Three live sources are read and must agree with the recorded table: the
command graph, which names every executable command and its handler; the
source of the command-line package and the runtime client, read for the
submissions each handler reaches; and the production registry, which names
every operation and its request type.

No count is a pass condition. The assertions are about membership and
agreement, so a tree that grows a command or an operation changes the derived
join and the recorded table together, and nothing here is edited.

The second half proves the reading itself on small source trees written for
the purpose, one defect at a time: a gate that cannot fail on a planted defect
says nothing by passing on the live tree.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from ....application.operator_surface.command_ports import CommandNodeKind
from ....tests.inventory import SRC_CADRUMO, production_python_files, read_source
from ...operation_composition import build_production_operation_registry
from ...tests.source_tree_support import SourceTree
from ..command_operation_table import (
    COMMAND_OPERATION_ROWS,
    COMMAND_RUNTIME_REQUEST_ROWS,
    OPERATIONS_WITHOUT_COMMAND,
)
from ..command_specs import COMMAND_GRAPH
from ..main import _emit_command_surface_manifest
from ..operator_surface_reconciliation import recorded_command_operation_join
from ._operation_submission_flow_support import SubmissionFlow, Symbol
from .command_operation_derivation import (
    COMMAND_LINE_PACKAGE,
    SCANNED_PACKAGES,
    SELECTED_OPERATIONS,
    SUBMISSION_RECORD,
    TABLE_PATH,
    CliPath,
    CommandOperationDerivation,
    SelectedOperations,
    command_line_files,
    derive_command_operations,
    derive_live_command_operations,
    derive_live_command_runtime_requests,
    render_command_operation_table,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REGENERATE = (
    "write it again with: python -m cadrumo.entrypoints.cli.tests.command_operation_derivation --runtime-requests"
)

_GENERIC_SUBMIT_FUNCTIONS = frozenset({"run_registered_operation", "submit_profile_operation"})
"""The two functions nearly every command submits through, read here by name alone."""

_FULL_SCREEN_PACKAGE = "cadrumo/entrypoints/tui/"


def _recorded_operations() -> dict[CliPath, frozenset[str]]:
    return {row.cli_path: frozenset(row.operation_ids) for row in recorded_command_operation_join().commands}


def test_the_derivation_settles_every_command_and_accounts_for_every_submission() -> None:
    """Nothing is left unread, no selection is wrong or stale, and no submission is orphaned."""
    findings = derive_live_command_operations().findings
    assert not findings, "the command-operation join is not exact:\n" + "\n".join(findings)


def test_the_recorded_table_is_the_derived_join() -> None:
    """The table a consumer reads says exactly what the live tree derives."""
    derivation = derive_live_command_operations()
    derived_rows = {
        (cli_path, operation_id)
        for cli_path, operation_ids in derivation.operations.items()
        for operation_id in sorted(operation_ids) or (None,)
    }
    recorded_rows = set(COMMAND_OPERATION_ROWS)
    stale = sorted(recorded_rows - derived_rows, key=repr)
    missing = sorted(derived_rows - recorded_rows, key=repr)
    assert not stale, f"recorded but no longer derived: {stale}; {_REGENERATE}"
    assert not missing, f"derived but not recorded: {missing}; {_REGENERATE}"
    assert frozenset(OPERATIONS_WITHOUT_COMMAND) == derivation.operations_without_command, _REGENERATE
    sent = derive_live_command_runtime_requests()
    derived_requests = {(cli_path, action) for cli_path, actions in sent.items() for action in actions}
    recorded_requests = set(COMMAND_RUNTIME_REQUEST_ROWS)
    assert recorded_requests == derived_requests, (
        f"recorded but no longer derived: {sorted(recorded_requests - derived_requests)}; "
        f"derived but not recorded: {sorted(derived_requests - recorded_requests)}; {_REGENERATE}"
    )
    assert TABLE_PATH.read_text(encoding="utf-8") == render_command_operation_table(derivation, sent), (
        f"the recorded table carries the derived rows in another spelling; {_REGENERATE}"
    )


def test_the_join_covers_every_executable_node_of_the_live_graph() -> None:
    """Every leaf and every group callback has a row, including one that submits nothing."""
    recorded = _recorded_operations()
    nodes = COMMAND_GRAPH.nodes()
    leaves = {node.path[1:] for node in nodes if node.spec.kind == CommandNodeKind.LEAF}
    executable = {node.path[1:] for node in nodes if node.spec.handler is not None}
    assert leaves, "the live command graph declares no leaf; the denominator is empty"
    assert leaves <= executable, f"a leaf carries no handler binding: {sorted(leaves - executable)}"
    assert set(recorded) == executable, (
        f"executable but not in the join: {sorted(executable - set(recorded))}; "
        f"in the join but not executable: {sorted(set(recorded) - executable)}"
    )


def test_the_join_and_the_registry_name_the_same_operations() -> None:
    """Every operation in the join is registered, and every registered operation is in the join."""
    join = recorded_command_operation_join()
    registered = {definition.definition_id for definition in build_production_operation_registry().definitions}
    joined = {row.operation_id for row in join.operations}
    submitted = {operation_id for row in join.commands for operation_id in row.operation_ids}
    assert joined == registered, (
        f"in the join but not registered: {sorted(joined - registered)}; "
        f"registered but not in the join: {sorted(registered - joined)}"
    )
    assert submitted <= registered, f"a command submits an unregistered operation: {sorted(submitted - registered)}"
    unsubmitted = {row.operation_id for row in join.operations if not row.cli_paths}
    assert unsubmitted == registered - submitted


def test_each_direction_of_the_join_says_what_the_other_says() -> None:
    """A command lists an operation exactly when that operation lists the command."""
    join = recorded_command_operation_join()
    forward = {(row.cli_path, operation_id) for row in join.commands for operation_id in row.operation_ids}
    inverse = {(cli_path, row.operation_id) for row in join.operations for cli_path in row.cli_paths}
    assert forward == inverse


def test_the_emitted_command_surface_manifest_carries_the_join(capsys: pytest.CaptureFixture[str]) -> None:
    """The manifest an outer root reads carries both directions of the recorded join, unchanged."""
    _emit_command_surface_manifest()

    emitted = json.loads(capsys.readouterr().out)["command_operations"]
    assert emitted == recorded_command_operation_join().model_dump(mode="json")
    submitted = {tuple(row["cli_path"]): row["operation_ids"] for row in emitted["commands"]}
    submitters = {row["operation_id"]: row["cli_paths"] for row in emitted["operations"]}
    assert submitted["app", "ledger", "add"] == ["ledger.add"]
    assert submitters["ledger.add"] == [["app", "ledger", "add"]]
    assert submitted["config", "storage", "view"] == []


def _symbols_calling(names: frozenset[str], path: str) -> set[Symbol]:
    """Name each module-level function or method of one file that calls any of ``names`` directly."""
    module = ast.parse(read_source(SRC_CADRUMO.parent / path), filename=path)
    owners: list[tuple[str, ast.AST]] = []
    for node in module.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            owners.append((node.name, node))
        elif isinstance(node, ast.ClassDef):
            owners.extend(
                (f"{node.name}.{member.name}", member)
                for member in node.body
                if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
            )
    return {
        (path, qualified)
        for qualified, owner in owners
        if any(
            isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id in names
            for inner in ast.walk(owner)
        )
    }


def test_every_call_of_a_generic_submit_function_is_reached_by_a_command() -> None:
    """A second, cruder reading of the call sites agrees that a command accounts for each one.

    The derivation follows resolved calls; this reads the two function names
    and nothing else. A call site the derivation failed to link would leave
    its function reading as one that submits nothing, and only a reading that
    does not depend on that link can notice.
    """
    callers: set[Symbol] = set()
    for path in command_line_files():
        callers |= _symbols_calling(_GENERIC_SUBMIT_FUNCTIONS, path)
    assert callers, "the command-line package calls neither generic submit function; the denominator is empty"
    reached = derive_live_command_operations().reached_submitters
    unaccounted = sorted(callers - reached)
    assert not unaccounted, f"a generic submit call no command reaches, or one not read as a submission: {unaccounted}"


def test_every_submission_is_constructed_where_the_reading_looks() -> None:
    """No package outside the reading's scope, other than the full-screen surface, constructs a submission."""
    record_file, record_name = SUBMISSION_RECORD
    root = SRC_CADRUMO.parent
    construction = f"{record_name}("
    constructing = {
        path.relative_to(root).as_posix() for path in production_python_files() if construction in read_source(path)
    } - {record_file}
    assert any(path.startswith(COMMAND_LINE_PACKAGE) for path in constructing)
    outside = sorted(path for path in constructing if not path.startswith((*SCANNED_PACKAGES, _FULL_SCREEN_PACKAGE)))
    assert not outside, f"a submission is constructed in a package the reading never enters: {outside}"


@pytest.mark.parametrize(
    ("cli_path", "expected"),
    [
        pytest.param(("app", "ledger", "add"), {"ledger.add"}, id="one-operation"),
        pytest.param(("app", "modelo", "reconcile", "import"), {"modelo.reconcile.import"}, id="reconcile-import"),
        pytest.param(
            ("app", "modelo", "export"),
            {"modelo.export", "modelo.work.revision"},
            id="export-selects-its-revision-first",
        ),
        pytest.param(
            ("app", "ledger", "classify"),
            {"ledger.classify.single", "ledger.classify.bulk", "ledger.classify.review", "ledger.classify.iva-derive"},
            id="four-modes",
        ),
        pytest.param(("app", "ledger", "split"), {"ledger.split.manual", "ledger.split.review"}, id="two-modes"),
        pytest.param(("config", "auth", "logout"), {"auth.session.logout"}, id="mode-argument-logout"),
        pytest.param(("config", "auth", "reset"), {"auth.session.reset"}, id="mode-argument-reset"),
        pytest.param(("config", "google", "status"), {"config.google.status"}, id="selected-by-request-type"),
        pytest.param(("config", "profile", "edit"), {"user-profile.patch", "user-profile.view"}, id="runtime-client"),
        pytest.param(("app", "overview", "calendar"), {"overview.calendar"}, id="named-selection"),
        pytest.param(("app", "quickfile"), {"modelo.quickfile"}, id="group-callback"),
        pytest.param(("config", "storage", "view"), set[str](), id="local-read"),
        pytest.param(("app", "tui"), set[str](), id="launcher"),
    ],
)
def test_known_commands_join_their_operations(cli_path: CliPath, expected: set[str]) -> None:
    assert _recorded_operations()[cli_path] == expected


def test_every_selection_names_a_reason() -> None:
    assert all(selection.reason.strip() for selection in SELECTED_OPERATIONS)


# -- the reading, proved on source trees written for the purpose ---------------

_FIXTURE_RECORD: Symbol = ("pkg/access.py", "Submit")

_FIXTURE_ACCESS = """
class Submit:
    def __init__(self, **fields):
        self.fields = fields
"""

_FIXTURE_OPERATIONS = """
A_DEFINITION_ID = "a.op"
B_DEFINITION_ID = "b.op"
C_DEFINITION_ID = "c.op"
FAMILY = {"one": "x.one", "two": "x.two"}


class BaseRequest:
    def encode(self):
        return "base"


class ARequest(BaseRequest):
    def encode(self):
        return "a"


class SpecialARequest(ARequest):
    pass


class BRequest:
    def encode(self):
        return "b"


class CRequest:
    def encode(self):
        return "c"


class ModeRequest:
    def encode(self):
        return "mode"


class SharedRequest:
    def encode(self):
        return "shared"
"""

_FIXTURE_TRANSPORT = """
from ..access import Submit
from ..operations import B_DEFINITION_ID, BRequest


def run(payload, *, definition_id):
    return Submit(definition_id=definition_id, payload_json=payload.encode())


def run_selected(payload):
    contract = lookup(type(payload))
    return Submit(definition_id=contract.definition_id, payload_json=payload.encode())


def lookup(kind):
    return kind


class Client:
    def read(self):
        return Submit(definition_id=B_DEFINITION_ID, payload_json=BRequest().encode())


def open_client() -> Client:
    return Client()
"""

_FIXTURE_COMMANDS = """
from ..access import Submit
from ..operations import (
    A_DEFINITION_ID,
    B_DEFINITION_ID,
    ARequest,
    BaseRequest,
    BRequest,
    CRequest,
    ModeRequest,
    SpecialARequest,
)
from .transport import open_client, run, run_selected


def alpha():
    run(ARequest(), definition_id=A_DEFINITION_ID)


def beta():
    request = BRequest()
    run(request, definition_id=B_DEFINITION_ID)


def either(flag):
    if flag:
        run(ARequest(), definition_id=A_DEFINITION_ID)
    else:
        run(BRequest(), definition_id=B_DEFINITION_ID)


def _moded(kind):
    run(ModeRequest(), definition_id=A_DEFINITION_ID if kind == "a" else B_DEFINITION_ID)


def mode_a():
    _moded("a")


def mode_b():
    _moded(kind="b")


def by_type():
    run_selected(CRequest())


def _consent(request: ARequest):
    return Submit(definition_id=A_DEFINITION_ID, payload_json=sealed(request))


def sealed(request):
    return [request][0]


def _dispatch(request):
    if isinstance(request, ARequest):
        _consent(request)
    else:
        run_selected(request)


def guarded_a():
    _dispatch(ARequest())


def guarded_c():
    _dispatch(CRequest())


def build() -> BaseRequest:
    return ARequest()


def declared():
    request = build()
    if isinstance(request, ARequest):
        _consent(request)


def inherited():
    _consent(SpecialARequest())


def through_client():
    client = open_client()
    client.read()


def quiet():
    return 1
"""

_FIXTURE_HANDLERS: Mapping[CliPath, Symbol | None] = {
    ("alpha",): ("pkg/cli/commands.py", "alpha"),
    ("beta",): ("pkg/cli/commands.py", "beta"),
    ("either",): ("pkg/cli/commands.py", "either"),
    ("mode", "a"): ("pkg/cli/commands.py", "mode_a"),
    ("mode", "b"): ("pkg/cli/commands.py", "mode_b"),
    ("by-type",): ("pkg/cli/commands.py", "by_type"),
    ("guarded", "a"): ("pkg/cli/commands.py", "guarded_a"),
    ("guarded", "c"): ("pkg/cli/commands.py", "guarded_c"),
    ("declared",): ("pkg/cli/commands.py", "declared"),
    ("inherited",): ("pkg/cli/commands.py", "inherited"),
    ("through-client",): ("pkg/cli/commands.py", "through_client"),
    ("quiet",): ("pkg/cli/commands.py", "quiet"),
    ("unavailable",): None,
}

_FIXTURE_REQUEST_TYPES: Mapping[str, Symbol] = {
    "a.op": ("pkg/operations.py", "ARequest"),
    "b.op": ("pkg/operations.py", "BRequest"),
    "c.op": ("pkg/operations.py", "CRequest"),
    "x.one": ("pkg/operations.py", "SharedRequest"),
    "x.two": ("pkg/operations.py", "SharedRequest"),
    "never.submitted": ("pkg/operations.py", "NeverRequest"),
}


def _derive_fixture(
    tmp_path: Path,
    *,
    extra_source: str = "",
    extra_handlers: Mapping[CliPath, Symbol | None] | None = None,
    selections: tuple[SelectedOperations, ...] = (),
) -> CommandOperationDerivation:
    """Derive the join of the fixture tree, optionally with one more command-line module."""
    files = {
        "pkg/__init__.py": "",
        "pkg/access.py": _FIXTURE_ACCESS,
        "pkg/operations.py": _FIXTURE_OPERATIONS,
        "pkg/cli/__init__.py": "",
        "pkg/cli/transport.py": _FIXTURE_TRANSPORT,
        "pkg/cli/commands.py": _FIXTURE_COMMANDS,
    }
    if extra_source:
        files["pkg/cli/extra.py"] = extra_source
    for relative, source in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    tree = SourceTree(tmp_path, packages=frozenset({"pkg"}))
    flow = SubmissionFlow(tree, scanned=("pkg/cli/",), submission=_FIXTURE_RECORD)
    return derive_command_operations(
        handlers={**_FIXTURE_HANDLERS, **(extra_handlers or {})},
        flow=flow,
        operation_request_types=_FIXTURE_REQUEST_TYPES,
        command_line_symbols=tuple(symbol for path in files for symbol in flow.symbols(path)),
        selections=selections,
    )


def test_the_reading_follows_each_command_to_its_own_operations(tmp_path: Path) -> None:
    derivation = _derive_fixture(tmp_path)

    assert derivation.findings == ()
    assert derivation.operations == {
        # One shared transport, and each caller keeps the id it passed.
        ("alpha",): {"a.op"},
        ("beta",): {"b.op"},
        # No condition is evaluated: both branches count.
        ("either",): {"a.op", "b.op"},
        # A mode the caller passes as a constant settles the callee's choice.
        ("mode", "a"): {"a.op"},
        ("mode", "b"): {"b.op"},
        # An id the source does not spell is named by the one operation taking that request type.
        ("by-type",): {"c.op"},
        # A path that accepts only another request class is not this command's path.
        ("guarded", "a"): {"a.op"},
        ("guarded", "c"): {"c.op"},
        # A declared return type says what an object is at least, so it rules no path out;
        # a constructed subclass is an instance of the class the path accepts.
        ("declared",): {"a.op"},
        ("inherited",): {"a.op"},
        # A method is followed through the class its receiver is declared to return.
        ("through-client",): {"b.op"},
        # Submitting nothing is recorded, for an implemented command and an unimplemented one alike.
        ("quiet",): set(),
        ("unavailable",): set(),
    }
    assert derivation.operations_without_command == {"x.one", "x.two", "never.submitted"}


_FAMILY_COMMAND = """
from ..operations import FAMILY, SharedRequest
from .transport import run


def picked(key):
    run(SharedRequest(), definition_id=FAMILY[key])
"""
_FAMILY_HANDLER: Mapping[CliPath, Symbol | None] = {("picked",): ("pkg/cli/extra.py", "picked")}


def test_a_run_time_selection_is_a_finding_until_it_is_named(tmp_path: Path) -> None:
    unnamed = _derive_fixture(tmp_path, extra_source=_FAMILY_COMMAND, extra_handlers=_FAMILY_HANDLER)

    assert len(unnamed.findings) == 1
    assert "picked: the submission at pkg/cli/transport.py" in unnamed.findings[0]
    assert "['x.one', 'x.two']" in unnamed.findings[0]
    assert unnamed.operations["picked",] == set()

    named = _derive_fixture(
        tmp_path,
        extra_source=_FAMILY_COMMAND,
        extra_handlers=_FAMILY_HANDLER,
        selections=(SelectedOperations(("picked",), frozenset({"x.two"}), "the key is read from the terminal"),),
    )

    assert named.findings == ()
    assert named.operations["picked",] == {"x.two"}
    assert named.operations_without_command == {"x.one", "never.submitted"}


@pytest.mark.parametrize(
    ("selection", "finding"),
    [
        pytest.param(
            SelectedOperations(("picked",), frozenset({"a.op"}), "any reason"),
            "picked: the selection names none of ['x.one', 'x.two']",
            id="outside-the-family",
        ),
        pytest.param(
            SelectedOperations(("picked",), frozenset({"x.one", "c.op"}), "any reason"),
            "picked: the selection names 'c.op', which no unsettled submission selects from",
            id="wider-than-the-family",
        ),
        pytest.param(
            SelectedOperations(("picked",), frozenset({"x.one"}), " "),
            "picked: the selection states no reason",
            id="no-reason",
        ),
        pytest.param(
            SelectedOperations(("alpha",), frozenset({"a.op"}), "any reason"),
            "alpha: the source now settles every submission, so its selection must be removed",
            id="no-longer-needed",
        ),
        pytest.param(
            SelectedOperations(("retired",), frozenset({"a.op"}), "any reason"),
            "retired: a selection names a command the graph does not declare as executable",
            id="unknown-command",
        ),
    ],
)
def test_a_selection_is_held_to_the_submission_it_settles(
    tmp_path: Path, selection: SelectedOperations, finding: str
) -> None:
    settled = SelectedOperations(("picked",), frozenset({"x.one"}), "the key is read from the terminal")
    selections = (selection,) if selection.cli_path == ("picked",) else (settled, selection)

    derivation = _derive_fixture(
        tmp_path, extra_source=_FAMILY_COMMAND, extra_handlers=_FAMILY_HANDLER, selections=selections
    )

    assert any(finding in found for found in derivation.findings), derivation.findings


@pytest.mark.parametrize(
    ("source", "handlers", "finding"),
    [
        pytest.param(
            "from ..operations import ARequest\nfrom .transport import run\n\n\n"
            "def orphan():\n    run(ARequest(), definition_id='a.op')\n",
            {},
            "pkg/cli/extra.py:orphan submits an operation and no command reaches it",
            id="submission-no-command-reaches",
        ),
        pytest.param(
            "from ..operations import ARequest\nfrom .transport import run\n\n\n"
            "def misspelled():\n    run(ARequest(), definition_id='a.opp')\n",
            {("misspelled",): ("pkg/cli/extra.py", "misspelled")},
            "misspelled: 'a.opp' is not a registered operation",
            id="unregistered-operation",
        ),
        pytest.param(
            "def through_unknown(thing):\n    thing.read()\n",
            {("through-unknown",): ("pkg/cli/extra.py", "through_unknown")},
            "pkg/cli/extra.py:2 calls .read() on a receiver of unknown class",
            id="receiver-of-unknown-class",
        ),
        pytest.param(
            "from .transport import run\n\n\n"
            "def computed(request, name):\n    run(request, definition_id=name.lower())\n",
            {("computed",): ("pkg/cli/extra.py", "computed")},
            "computed: the submission at pkg/cli/transport.py",
            id="operation-the-source-cannot-read",
        ),
        pytest.param(
            "",
            {("moved",): ("pkg/cli/commands.py", "moved")},
            "moved: handler pkg/cli/commands.py:moved is not a function of the scanned packages",
            id="handler-the-file-no-longer-defines",
        ),
    ],
)
def test_the_reading_reports_what_it_cannot_account_for(
    tmp_path: Path, source: str, handlers: Mapping[CliPath, Symbol | None], finding: str
) -> None:
    derivation = _derive_fixture(tmp_path, extra_source=source, extra_handlers=handlers)

    assert any(finding in found for found in derivation.findings), derivation.findings
