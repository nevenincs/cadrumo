"""Static hygiene guard for throwaway master keys and SQL-backed repositories."""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path
from typing import NamedTuple

import pytest

from .....tests import (
    ast_for_path,
    leaf_name,
    non_test_package_python_files,
    package_python_files,
    repo_relative,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _Violation(NamedTuple):
    path: str
    line: int
    constructor: str


_DEFAULT_SQL_BACKED_CONSTRUCTORS: frozenset[str] = frozenset(
    {
        "AmortizacionLedgerRepository",
        "ArrendamientoRepository",
        "AssetsLedgerRepository",
        "AttachmentStore",
        "Borrador100SnapshotRepository",
        "BucketEventHistoryRepository",
        "CalculationObservationRepository",
        "CalculationRevisionCatalogueRepository",
        "FincaAmortizacionLedgerRepository",
        "FincaGastoRepository",
        "FincaRendimientoRepository",
        "FincaRepository",
        "FiledDeclaracionObservationStore",
        "InventoryLedgerRepository",
        "InvoiceCatalogueRepository",
        "IvaCompensationHistoryRepository",
        "IvaWalletDecisionRepository",
        "JustificanteRepository",
        "ModeloAmendmentRepository",
        "ModeloDraftRepository",
        "ModeloHistoryRepository",
        "ModeloRecordCatalogueRepository",
        "CommittedProfileRepository",
        "SecureObjectRepository",
        "SubmissionRepository",
        "TransactionCatalogueRepository",
        "ProfileRecordRepository",
        "UserProfileSnapshotRepository",
        "VerificationReportCatalogueRepository",
        "WorkflowRunRepository",
        "WorkflowStateRepository",
        "WorkUnitCatalogueRepository",
    },
)

_INJECTION_KEYWORDS: frozenset[str] = frozenset(
    {
        "engine",
        "bucket_id",
        "object_repository",
        "objects",
        "repository",
        "secure_objects",
    },
)


def test_ephemeral_master_key_tests_isolate_default_secure_object_repository() -> None:
    """Ephemeral keys must not write through the process-default SQL repository."""

    violations: list[_Violation] = []
    for _path, relative_path, tree in _iter_test_module_trees():
        if not _uses_ephemeral_master_key(tree):
            continue
        risky_calls = _default_sql_backed_constructor_calls(tree)
        if not risky_calls:
            continue
        if _has_autouse_temp_database_isolation(tree):
            continue
        violations.extend(_Violation(relative_path, line, constructor) for line, constructor in risky_calls)

    assert not violations, "\n".join(
        (
            "EphemeralMasterKeyProvider tests must isolate default SQL-backed secure-object writes "
            "with an autouse settings override plus engine disposal, or inject an explicit repository.",
            *tuple(f"{violation.path}:{violation.line} {violation.constructor}" for violation in violations),
        ),
    )


def test_database_operating_passphrases_use_core_test_setting() -> None:
    """Database-backed tests must not carry local master-key passphrase literals."""

    violations: list[str] = []
    for _path, relative_path, tree in _iter_test_module_trees():
        if not _operates_database_storage(tree):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _has_literal_passphrase_callback(node):
                violations.append(f"{relative_path}:{node.lineno}: literal passphrase_callback")
            if _sets_literal_secret_passphrase_env(node):
                violations.append(f"{relative_path}:{node.lineno}: literal CADRUMO_SECRET_PASSPHRASE")
            if _overrides_literal_secret_passphrase(node):
                violations.append(f"{relative_path}:{node.lineno}: literal cadrumo_secret_passphrase override")

    assert not violations, "\n".join(
        (
            "Database-backed tests must read the shared test password from "
            "Settings.cadrumo_dev_test_database_password or aeat-tests.secure_sql.",
            *violations,
        ),
    )


def _iter_test_module_trees() -> tuple[tuple[Path, str, ast.AST], ...]:
    modules: list[tuple[Path, str, ast.AST]] = []
    for path in _iter_test_modules():
        relative_path = repo_relative(path)
        tree = ast_for_path(path)
        assert tree is not None, f"{relative_path} must be parseable"
        modules.append((path, relative_path, tree))
    return tuple(modules)


@cache
def _iter_test_modules() -> tuple[Path, ...]:
    return tuple(
        path
        for path in package_python_files(include_data=True)
        if path.name.startswith("test_") or path.name.endswith("_test.py") or path.name == "conftest.py"
    )


def _uses_ephemeral_master_key(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call) and leaf_name(node.func) == "EphemeralMasterKeyProvider" for node in ast.walk(tree)
    )


def _operates_database_storage(tree: ast.AST) -> bool:
    return bool(_default_sql_backed_constructor_calls(tree)) or any(
        isinstance(node, ast.Call)
        and (
            leaf_name(node.func)
            in {
                "create_engine_from_settings",
                "get_engine",
                "get_sessionmaker",
                "session_scope",
            }
            or _call_sets_temp_database_url_env(node)
        )
        for node in ast.walk(tree)
    )


def _default_sql_backed_constructor_calls(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    calls: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        constructor = leaf_name(node.func)
        if constructor not in _DEFAULT_SQL_BACKED_CONSTRUCTORS:
            continue
        if _has_explicit_repository_injection(node):
            continue
        calls.append((node.lineno, constructor))
    return tuple(calls)


def _has_explicit_repository_injection(node: ast.Call) -> bool:
    if node.args:
        return True
    if leaf_name(node.func) == "SecureObjectRepository":
        return bool(node.keywords)
    return any(keyword.arg in _INJECTION_KEYWORDS for keyword in node.keywords if keyword.arg is not None)


def _has_autouse_temp_database_isolation(tree: ast.AST) -> bool:
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_autouse_pytest_fixture(node)
        and (
            _overrides_temp_database_or_storage_settings(node)
            or _sets_temp_storage_root_env(node)
            or _sets_temp_database_url_env(node)
        )
        and _disposes_engine_around_fixture(node)
        for node in ast.walk(tree)
    )


def _is_autouse_pytest_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if leaf_name(decorator.func) != "fixture":
            continue
        if any(
            keyword.arg == "autouse" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
            for keyword in decorator.keywords
        ):
            return True
    return False


def _overrides_temp_database_or_storage_settings(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    temp_path_names = _tmp_path_derived_names(node)
    return any(
        _call_overrides_temp_database_or_storage_settings(child, temp_path_names=temp_path_names)
        for child in ast.walk(node)
    )


def _tmp_path_derived_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    names = {"tmp_path"}
    changed = True
    while changed:
        changed = False
        for child in ast.walk(node):
            if not isinstance(child, ast.Assign):
                continue
            rendered = ast.unparse(child.value)
            if not any(name in rendered for name in names):
                continue
            for target in child.targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    changed = True
    return frozenset(names)


def _call_overrides_temp_database_or_storage_settings(
    node: ast.AST,
    *,
    temp_path_names: frozenset[str],
) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if leaf_name(node.func) != "override_settings":
        return False
    for keyword in node.keywords:
        rendered = ast.unparse(keyword.value)
        if (
            keyword.arg == "cadrumo_database_url"
            and "sqlite:///" in rendered
            and any(name in rendered for name in temp_path_names)
        ):
            return True
        if keyword.arg == "cadrumo_local_storage_root" and any(name in rendered for name in temp_path_names):
            return True
    return False


def _sets_temp_storage_root_env(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_call_sets_temp_storage_root_env(child) for child in ast.walk(node))


def _call_sets_temp_storage_root_env(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if leaf_name(node.func) != "setenv":
        return False
    if len(node.args) < 2:
        return False
    if _literal_string(node.args[0]) != "CADRUMO_LOCAL_STORAGE_ROOT":
        return False
    return "tmp_path" in ast.unparse(node.args[1])


def _sets_temp_database_url_env(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_call_sets_temp_database_url_env(child) for child in ast.walk(node))


def _call_sets_temp_database_url_env(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if leaf_name(node.func) != "setenv":
        return False
    if len(node.args) < 2:
        return False
    if _literal_string(node.args[0]) != "CADRUMO_DATABASE_URL":
        return False
    rendered = ast.unparse(node.args[1])
    return "sqlite:///" in rendered and "tmp_path" in rendered


def _disposes_engine_around_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    dispose_calls = sum(
        1 for child in ast.walk(node) if isinstance(child, ast.Call) and leaf_name(child.func) == "dispose_engine"
    )
    has_yield = any(isinstance(child, (ast.Yield, ast.YieldFrom)) for child in ast.walk(node))
    return has_yield and dispose_calls >= 2


def _has_literal_passphrase_callback(node: ast.Call) -> bool:
    return any(
        keyword.arg == "passphrase_callback"
        and isinstance(keyword.value, ast.Lambda)
        and _literal_nonblank_string(keyword.value.body) is not None
        for keyword in node.keywords
    )


def _sets_literal_secret_passphrase_env(node: ast.Call) -> bool:
    if leaf_name(node.func) not in {"setenv", "putenv"}:
        return False
    if len(node.args) < 2:
        return False
    return _is_secret_passphrase_env_arg(node.args[0]) and _literal_nonblank_string(node.args[1]) is not None


def _overrides_literal_secret_passphrase(node: ast.Call) -> bool:
    if leaf_name(node.func) != "override_settings":
        return False
    for keyword in node.keywords:
        if keyword.arg != "cadrumo_secret_passphrase":
            continue
        if _literal_nonblank_string(keyword.value) is not None:
            return True
        if (
            isinstance(keyword.value, ast.Call)
            and leaf_name(keyword.value.func) == "SecretStr"
            and keyword.value.args
            and _literal_nonblank_string(keyword.value.args[0]) is not None
        ):
            return True
    return False


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_nonblank_string(node: ast.AST) -> str | None:
    value = _literal_string(node)
    if value is None or not value.strip():
        return None
    return value


def _is_secret_passphrase_env_arg(node: ast.AST) -> bool:
    if _literal_string(node) == "CADRUMO_SECRET_PASSPHRASE":
        return True
    return isinstance(node, ast.Name) and node.id == "PASSPHRASE_ENV_VAR"


def test_every_pinned_constructor_still_names_a_real_class() -> None:
    """Anchor the prohibition's target set, so a rename cannot empty it.

    This gate matches CONSTRUCTOR NAMES. A name nothing defines can never
    match, so renaming a SQL-backed repository silently drops it out of the
    hygiene rule while leaving every assertion green -- the rename looks free
    precisely because the gate stopped watching.

    Found stale on its first run: the set carried both the Spanish-stem
    ``FiledDeclaracionObservationStore`` and an English
    ``FiledDeclarationObservationStore``. Only the first exists, and the second
    is a name the domain-naming rule forbids ever creating, so it was pinning a
    class that could not appear.
    """
    defined: set[str] = set()
    for path in non_test_package_python_files():
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                defined.add(node.name)
            elif isinstance(node, ast.alias):
                defined.add(node.asname or node.name.rsplit(".", 1)[-1])

    unresolved = sorted(name for name in _DEFAULT_SQL_BACKED_CONSTRUCTORS if name not in defined)

    assert not unresolved, (
        f"these pinned constructors name no class in production code: {unresolved}. Re-point the "
        "entry at whatever the class is called now, or drop it -- a pin on a name nothing defines "
        "matches nothing and quietly narrows what this gate covers."
    )
