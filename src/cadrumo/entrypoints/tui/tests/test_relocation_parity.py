"""Real parity proofs for the completed canonical TUI relocations.

The feature packages deliberately expose no convenience facade.  These tests
therefore name each defining module directly, drive the shipped Textual apps
through real application doors, and inspect the live source AST for duplicate
definitions or forwarding namespaces. They deliberately stop before the future root application
and navigation join: that join must consume these independent feature
surfaces, rather than becoming a substitute for proving them.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from pydantic import BaseModel
from textual.css.query import NoMatches
from textual.widgets import DataTable, Input, Static

from ....application.flows import CopyRef, FlowDefinition, FlowPage, FlowSection
from ....application.user_profile import build_profile_overview, login_profile, logout_active_profile
from ....application.user_profile.login_interaction import attempt_profile_login, profile_login_choices
from ....core import assess_profile_password, require_active_bucket_id
from ....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ....tests.modelo_work_review import build_real_modelo_work_review
from ....tests.profile_capsule import load_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ..devtools.fixture import registration_attempt
from ..flows.app import FlowTuiApp
from ..modelo.view.work_review import ModeloWorkReviewApp
from ..profile.overview import ProfileManagerApp
from ..secret.app import LoginApp, RecoveryWordsScreen, RegistrationApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (140, 60)
_LABEL = "Relocation parity operator"
_PASSPHRASE = "relocation-parity-operator-secret"  # noqa: S105 - synthetic test fixture

_CANONICAL_DEFINITIONS = (
    ("cadrumo.entrypoints.tui.profile.overview", "ProfileManagerApp"),
    ("cadrumo.entrypoints.tui.profile.status", "StatusApp"),
    ("cadrumo.entrypoints.tui.secret.app", "LoginApp"),
    ("cadrumo.entrypoints.tui.secret.app", "RegistrationApp"),
    ("cadrumo.entrypoints.tui.secret.app", "RecoveryWordsScreen"),
    ("cadrumo.entrypoints.tui.flows.app", "FlowTuiApp"),
    ("cadrumo.entrypoints.tui.modelo.view.work_review", "ModeloWorkReviewApp"),
    ("cadrumo.entrypoints.tui.modelo.view.work_review", "ModeloWorkReviewScreen"),
)

_INERT_NAMESPACES = (
    "cadrumo.entrypoints.tui",
    "cadrumo.entrypoints.tui.components",
    "cadrumo.entrypoints.tui.profile",
    "cadrumo.entrypoints.tui.secret",
    "cadrumo.entrypoints.tui.flows",
    "cadrumo.entrypoints.tui.modelo",
    "cadrumo.entrypoints.tui.modelo.view",
    "cadrumo.entrypoints.tui.devtools",
)

_TUI_ROOT = Path(__file__).parents[1]
_REPO_ROOT = Path(__file__).parents[5]
_SOURCE_ROOTS = (
    _REPO_ROOT / "src" / "cadrumo",
    _REPO_ROOT / "dev",
    _REPO_ROOT / "packaging",
)
_SRC_ROOT = _REPO_ROOT / "src"
_MANAGER_MODULE = "cadrumo.entrypoints.tui.tests.manager_pilot"
_MANAGER_SYMBOL = "wait_until_settled"


class _FlowAnswers(BaseModel):
    """A one-field flow model used to exercise the real renderer."""


def _copy() -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="wizard.setup.title")


def _flow_definition() -> FlowDefinition:
    copy = _copy()
    return FlowDefinition(
        id="flows.test.relocation-parity",
        title=copy,
        description=copy,
        sections=(
            FlowSection(
                id="relocation-parity",
                title=copy,
                items=(
                    FlowPage(
                        id="operator_name",
                        widget=FlowWidgetKind.TEXT,
                        prompt=copy,
                        answer_type=str,
                    ),
                ),
            ),
        ),
        answers_model=_FlowAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _source_trees() -> tuple[tuple[Path, ast.Module], ...]:
    return tuple(
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for root in _SOURCE_ROOTS
        if root.is_dir()
        for path in sorted(root.rglob("*.py"))
    )


def _module_name(path: Path) -> str | None:
    """Return the importable module for a source file, when it is under ``src``."""
    try:
        relative = path.relative_to(_SRC_ROOT).with_suffix("")
    except ValueError:
        return None
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _relative_target(path: Path, node: ast.ImportFrom) -> str | None:
    """Resolve a relative import from any module under ``src/cadrumo``."""
    module = _module_name(path)
    if module is None:
        return None
    package = module.split(".") if path.name == "__init__.py" else module.split(".")[:-1]
    base_length = len(package) - node.level + 1
    if base_length <= 0:
        return None
    base = package[:base_length]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _import_from_targets(path: Path, node: ast.ImportFrom) -> tuple[str, ...]:
    base = _relative_target(path, node) if node.level else node.module
    if not base:
        return tuple(alias.name for alias in node.names if alias.name != "*")
    return (base, *(f"{base}.{alias.name}" for alias in node.names if alias.name != "*"))


def _import_targets(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _relative_target(path, node) if node.level else node.module
            targets.append(base or "<relative>")
        elif isinstance(node, ast.Call):
            targets.extend(_dynamic_import_targets(ast.Module(body=[node], type_ignores=[])))
    return tuple(targets)


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and all(isinstance(value, ast.Constant) for value in node.values):
        return "".join(str(value.value) for value in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _dynamic_import_targets(tree: ast.Module) -> tuple[str, ...]:
    targets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        is_dynamic_import = (isinstance(function, ast.Name) and function.id in {"__import__", "import_module"}) or (
            isinstance(function, ast.Attribute) and function.attr == "import_module"
        )
        if is_dynamic_import and node.args:
            target = _constant_string(node.args[0])
            if target is not None:
                targets.append(target)
    return tuple(targets)


def _repo_path(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _manager_edge(path: Path, node: ast.AST) -> tuple[object, ...]:
    if isinstance(node, ast.Import):
        return (_repo_path(path), "import", tuple((alias.name, alias.asname) for alias in node.names))
    if isinstance(node, ast.ImportFrom):
        return (
            _repo_path(path),
            "from",
            node.level,
            node.module or "",
            tuple((alias.name, alias.asname) for alias in node.names),
        )
    raise TypeError(f"unsupported import node: {type(node)!r}")


def _manager_target_hit(target: str) -> bool:
    return any(part in {_MANAGER_MODULE.rsplit(".", 1)[-1], _MANAGER_SYMBOL} for part in target.split("."))


def _manager_import_edges(trees: tuple[tuple[Path, ast.Module], ...]) -> tuple[tuple[object, ...], ...]:
    edges: list[tuple[object, ...]] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                targets = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else _import_from_targets(path, node)
                )
                if any(_manager_target_hit(target) for target in targets):
                    edges.append(_manager_edge(path, node))
        edges.extend(
            (_repo_path(path), "dynamic", target)
            for target in _dynamic_import_targets(tree)
            if _manager_target_hit(target)
        )
    return tuple(sorted(edges, key=repr))


def _class_definition_sites(class_name: str) -> tuple[Path, ...]:
    sites: list[Path] = []
    for path, tree in _source_trees():
        if any(isinstance(node, ast.ClassDef) and node.name == class_name for node in ast.walk(tree)):
            sites.append(path)
    return tuple(sites)


def _function_definition_sites(
    trees: tuple[tuple[Path, ast.Module], ...],
    function_name: str,
) -> tuple[Path, ...]:
    sites: list[Path] = []
    for path, tree in trees:
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
            for node in ast.walk(tree)
        ):
            sites.append(path)
    return tuple(sites)


def test_relocated_symbols_have_single_canonical_defining_modules_and_inert_facades() -> None:
    """Every completed relocation is reached through its defining module only."""
    for module_name, symbol_name in _CANONICAL_DEFINITIONS:
        module = importlib.import_module(module_name)
        symbol = getattr(module, symbol_name)
        assert symbol.__module__ == module_name
        assert _class_definition_sites(symbol_name) == (Path(module.__file__ or ""),)

    for namespace_name in _INERT_NAMESPACES:
        namespace = importlib.import_module(namespace_name)
        assert namespace.__all__ == ()
        source_path = Path(namespace.__file__ or "")
        imports = [
            target
            for target in _import_targets(source_path)
            if target != "__future__" and not target.startswith("from __future__")
        ]
        assert not imports, f"{namespace_name} is a forwarding facade: {imports}"


def test_manager_pilot_has_one_canonical_home_and_exactly_seven_direct_consumers() -> None:
    """The settling barrier lives in the TUI test package, not the old root."""
    old_home = _TUI_ROOT.parents[1] / "tests" / "manager_pilot.py"
    canonical_home = _TUI_ROOT / "tests" / "manager_pilot.py"
    assert not old_home.exists()
    assert canonical_home.is_file()

    expected_consumers = {
        "test_manager_field_editors.py",
        "test_manager_language_switch.py",
        "test_manager_masked_field_preservation.py",
        "test_manager_masked_required_field.py",
        "test_manager_required_field_refusal.py",
        "test_manager_screen.py",
        "test_visual_verification.py",
    }
    trees = _source_trees()
    expected_edges = tuple(
        sorted(
            (
                (
                    _repo_path(canonical_home.parent / consumer),
                    "from",
                    1,
                    "manager_pilot",
                    (("wait_until_settled", None),),
                )
                for consumer in expected_consumers
            ),
            key=repr,
        )
    )
    assert _manager_import_edges(trees) == expected_edges
    assert _function_definition_sites(trees, _MANAGER_SYMBOL) == (canonical_home,)

    tests_init = _TUI_ROOT / "tests" / "__init__.py"
    tests_init_tree = ast.parse(tests_init.read_text(encoding="utf-8"), filename=str(tests_init))
    assert not [
        node
        for node in ast.walk(tests_init_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]


@pytest.mark.asyncio
async def test_profile_and_secret_apps_preserve_the_real_custody_path(tmp_path: Path) -> None:
    """Register, unlock, and render an actual encrypted profile through relocated apps."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        registration = RegistrationApp(assess=assess_profile_password, register=registration_attempt)
        async with registration.run_test(size=_TERMINAL_SIZE) as pilot:
            registration.query_one("#field-username", Input).value = _LABEL
            registration.query_one("#field-password", Input).value = _PASSPHRASE
            registration.query_one("#field-confirm", Input).value = _PASSPHRASE
            await pilot.click("#btn-create")
            for _ in range(100):
                if isinstance(registration.screen, RecoveryWordsScreen):
                    candidate = registration.screen
                    if candidate.query("#words-value") and candidate.query("#btn-confirm-words"):
                        break
                await pilot.pause(0.1)
            assert isinstance(registration.screen, RecoveryWordsScreen)
            recovery = registration.screen
            words = recovery.query_one("#words-value", Static)
            assert str(words.render())
            recovery.query_one("#field-recovery-verification", Input).value = str(words.render())
            await pilot.click("#btn-confirm-words")
            await registration.workers.wait_for_complete()
            await pilot.pause()

        assert registration.error is None
        assert registration.outcome is not None
        profile_id = str(registration.outcome.profile_id)
        logout_active_profile()

        login = LoginApp(choices=profile_login_choices(), authenticate=attempt_profile_login)
        async with login.run_test(size=_TERMINAL_SIZE) as pilot:
            login.query_one("#field-passphrase", Input).value = _PASSPHRASE
            await pilot.click("#btn-unlock")
            await login.workers.wait_for_complete()
            await pilot.pause()

        assert login.outcome is not None
        assert login.outcome.bucket_id == profile_id
        # Textual executes the authentication request on a worker, whose
        # context-local session cannot become this test task's session.  Enter
        # the same public login door here before asking the real record store
        # for the manager's injected projection.
        login_profile(name=_LABEL, passphrase_callback=lambda: _PASSPHRASE)
        record = load_test_profile_record(require_active_bucket_id())
        overview = build_profile_overview(record, label=_LABEL)
        from ....application.user_profile import apply_manager_profile_field_mutation

        def persist(path: str, value: str):
            applied = apply_manager_profile_field_mutation(profile_id=profile_id, path=path, value=value)
            return build_profile_overview(applied, label=_LABEL)

        manager = ProfileManagerApp(overview, persist=persist)
        async with manager.run_test(size=_TERMINAL_SIZE) as pilot:
            await pilot.pause()
            rendered_rows = sum(table.row_count for table in manager.query(DataTable))
            assert rendered_rows == overview.total_count
            assert overview.total_count > overview.present_count
            manager.exit(None)


@pytest.mark.asyncio
async def test_flow_and_modelo_review_project_real_application_contracts(tmp_path: Path) -> None:
    """The relocated flow and read-only review render authoritative application data."""
    flow = FlowTuiApp(_flow_definition(), mode=FlowMode.MODIFY, registered_values={})
    async with flow.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.press(*"Ada")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#btn-submit")
        await pilot.pause()

    assert flow.final_state is not None
    assert dict(flow.final_state.answers) == {"operator_name": "Ada"}

    review = build_real_modelo_work_review(tmp_path, modelo="100", filing_year=2024, period_code="0A")
    review_app = ModeloWorkReviewApp(review)
    async with review_app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        casillas = review_app.screen.query_one("#modelo-review-casillas-table", DataTable)
        assert review.casillas
        assert casillas.row_count == len(review.casillas)
        with pytest.raises(NoMatches):
            review_app.screen.query_one(Input)
        review_app.exit(None)
