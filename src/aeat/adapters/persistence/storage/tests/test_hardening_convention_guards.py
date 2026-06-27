"""Static guards for secure-storage production-hardening conventions."""

from __future__ import annotations

import ast
import importlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from .....core.errors import ERROR_REGISTRY, AeatError, get_registered_error_code
from .....locales.manager import LocaleManager
from .....tests._inventory import SRC_AEAT, ast_for_path, package_ast_items, qualified_name, repo_path, repo_relative
from ..errors import SecureStorageError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_HARDENING_TEST_SURFACES = (
    "src/aeat/adapters/persistence/storage/blob_store/tests/test_materialisation.py",
    "src/aeat/adapters/persistence/storage/master_key/tests/test_master_key.py",
    "src/aeat/adapters/persistence/storage/tests/test_runtime.py",
    "src/aeat/adapters/persistence/storage/master_key/tests/test_kdf_params.py",
    "src/aeat/application/user_profile/tests/test_profile_repository.py",
    "src/aeat/core/tests/test_storage_route_classification.py",
    "src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py",
)

_ALLOWED_ENV_KEYS_BY_SURFACE: dict[str, set[str]] = {}
_ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS = {
    "src/aeat/adapters/persistence/storage/runtime.py",
    "src/aeat/adapters/persistence/storage/runtime_repository.py",
}
_APPROVED_EXPLICIT_ROUTE_TEST_SURFACES = {
    "src/aeat/adapters/persistence/storage/envelope/tests/test_secure_bound_repository.py",
    "src/aeat/adapters/persistence/storage/envelope/tests/test_secure_bound_repository_contract.py",
    "src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py",
    "src/aeat/adapters/persistence/storage/master_key/tests/test_adverse_sessions.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_apply_batch.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_archive_bundle_roundtrip.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_constraints.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_engine.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_repository.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part1.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part3.py",
    "src/aeat/adapters/persistence/storage/sql/tests/_secure_objects_support.py",
    "src/aeat/adapters/persistence/storage/sql/tests/test_session.py",
    "src/aeat/adapters/persistence/storage/tests/test_ephemeral_key_hygiene.py",
    "src/aeat/adapters/persistence/storage/tests/test_hardening_convention_guards.py",
    "src/aeat/adapters/persistence/storage/tests/test_runtime.py",
    "src/aeat/application/tests/test_diagnostics.py",
    "src/aeat/application/tests/test_repair_integrity.py",
    "src/aeat/application/tests/test_state_projection.py",
    "src/aeat/application/tests/test_storage_write_policy.py",
    "src/aeat/application/user_profile/tests/test_repository.py",
    "src/aeat/application/workflow/tests/test_runtime_defaults.py",
    "src/aeat/core/tests/test_storage_route_classification.py",
    "src/aeat/entrypoints/cli/tests/test_cold_start_no_profile.py",
    "src/aeat/entrypoints/cli/tests/test_repair_bootstrap_exempt.py",
    "src/aeat/entrypoints/cli/tests/test_root_fallback_write_guard.py",
    "src/aeat/tests/secure_sql.py",
    "src/aeat/tests/test_config.py",
    "src/aeat/tests/test_secure_sql.py",
}


def test_bucket_session_cleanup_observability_does_not_use_suppression_markers(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    path = repo_path("src/aeat/adapters/persistence/storage/master_key/_bucket_session.py")
    function = _function_named(path, "_evict_engine", source_tree_ast)
    segment = _source_segment(path, function)

    assert "# noqa" not in segment
    assert "pragma: no cover" not in segment
    assert "pass" not in {node.__class__.__name__.lower() for node in ast.walk(function)}
    assert any(_is_logger_call(node, "debug") or _is_logger_call(node, "warning") for node in ast.walk(function))
    assert not any(_call_has_keyword(node, "exc_info") for node in ast.walk(function) if isinstance(node, ast.Call))


def test_named_bucket_settings_derivation_stays_in_core_settings_boundary(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    runtime_path = repo_path("src/aeat/adapters/persistence/storage/runtime.py")
    route_path = repo_path("src/aeat/core/_config_storage_route.py")

    runtime_text = runtime_path.read_text(encoding="utf-8")
    assert "__pydantic_fields_set__" not in runtime_text
    assert "settings_for_active_profile_bucket" in runtime_text

    config_function = _function_named(route_path, "settings_for_bucket_route", source_tree_ast)
    config_segment = _source_segment(route_path, config_function)
    assert "__pydantic_fields_set__" in config_segment
    assert "aeat_database_url" in config_segment


def test_profile_repository_kdf_defaults_flow_from_canonical_master_key_model(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    path = repo_path("src/aeat/application/user_profile/_profile_repository.py")
    function = _function_named(path, "_default_kdf_params", source_tree_ast)
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    assert any(_is_kdf_default_to_manifest_call(call) for call in calls)
    assert not any(_call_name(call.func) == "ManifestKdfParams" for call in calls)
    assert not any(
        keyword.arg in {"algorithm", "version", "memory_cost", "time_cost", "parallelism", "salt", "output_length"}
        for call in calls
        for keyword in call.keywords
    )


def test_production_secure_object_repository_construction_stays_runtime_owned(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    offences: list[str] = []
    for path, tree in package_ast_items(source_tree_ast, include_data=True):
        relative = repo_relative(path)
        if _is_test_surface(relative):
            continue
        constructors = _secure_object_repository_constructor_names(tree)
        module_aliases = _secure_object_repository_module_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_secure_object_repository_constructor_call(
                node,
                constructors,
                module_aliases,
            ):
                continue
            if relative not in _ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS:
                offences.append(f"{relative}:{node.lineno}: direct SecureObjectRepository construction")
                continue
            engine_keyword = next((keyword for keyword in node.keywords if keyword.arg == "engine"), None)
            if engine_keyword is None:
                offences.append(f"{relative}:{node.lineno}: runtime construction must bind an engine explicitly")
                continue
            if isinstance(engine_keyword.value, ast.Constant) and engine_keyword.value.value is None:
                offences.append(f"{relative}:{node.lineno}: runtime construction must not bind engine=None")

    assert offences == []


def test_explicit_database_route_test_setup_stays_approved(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    offences: list[str] = []
    for path, tree in package_ast_items(source_tree_ast, include_data=True):
        relative = repo_relative(path)
        if not _is_test_setup_surface(relative):
            continue
        if not _uses_explicit_database_route(tree):
            continue
        if relative not in _APPROVED_EXPLICIT_ROUTE_TEST_SURFACES:
            offences.append(f"{relative}: unapproved explicit database route test setup")

    assert offences == []


def test_hardening_test_surfaces_do_not_reintroduce_shortcut_markers(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    offences: list[str] = []
    for relative in _HARDENING_TEST_SURFACES:
        path = repo_path(relative)
        tree = ast_for_path(path, source_tree_ast)
        assert tree is not None, f"{relative}: source must be parseable"
        constants = _collect_string_bindings(tree)
        os_aliases = _collect_os_aliases(tree)
        environ_aliases = _collect_environ_aliases(tree)
        for node in ast.walk(tree):
            if _is_pytest_skip_or_xfail_marker(node):
                assert isinstance(node, (ast.expr, ast.stmt))
                offences.append(f"{relative}:{node.lineno}: {qualified_name(node)}")
            if (
                isinstance(node, ast.Call)
                and _is_environment_call(node, constants, os_aliases, environ_aliases)
                and not _is_allowed_env_key(relative, _env_key_for_call(node, constants))
            ):
                offences.append(f"{relative}:{node.lineno}: environment call")
            if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign | ast.Delete) and _mutates_environment(
                node,
                constants,
                os_aliases,
                environ_aliases,
            ):
                offences.append(f"{relative}:{node.lineno}: environment mutation")
            if isinstance(node, ast.ClassDef) and node.name.startswith(("_Fake", "_Stub")):
                offences.append(f"{relative}:{node.lineno}: {node.name}")
            if _is_mock_import(node):
                assert isinstance(node, (ast.Import, ast.ImportFrom))
                offences.append(f"{relative}:{node.lineno}: mock import")
    assert offences == []


def _is_test_surface(relative: str) -> bool:
    path = Path(relative)
    return (
        path.name.startswith("test_")
        or path.name.endswith("_test_suite.py")
        or path.name == "conftest.py"
        or "/test_" in relative
        or "tests" in path.parts
    )


def _is_test_setup_surface(relative: str) -> bool:
    path = Path(relative)
    return _is_test_surface(relative) or "/tests/" in relative or path.name == "secure_sql.py"


def _secure_object_repository_constructor_names(tree: ast.AST) -> set[str]:
    names = {"SecureObjectRepository"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names if alias.name == "SecureObjectRepository")

    discovered = True
    while discovered:
        discovered = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
                continue
            if node.value.id not in names:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    discovered = True
    return names


def _secure_object_repository_module_aliases(tree: ast.AST) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name.endswith(
                    (
                        "adapters.persistence.storage.sql",
                        "adapters.persistence.storage.sql.secure_objects",
                    ),
                )
            )
        if isinstance(node, ast.ImportFrom) and node.module in {
            "aeat.adapters.persistence.storage",
            "aeat.adapters.persistence.storage.sql",
            "aeat.adapters.persistence.storage.sql.secure_objects",
        }:
            aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name in {"sql", "secure_objects"}
            )
    return aliases


def _is_secure_object_repository_constructor_call(
    node: ast.Call,
    constructors: set[str],
    module_aliases: set[str],
) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in constructors
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "SecureObjectRepository":
        return False
    return qualified_name(node.func.value) in module_aliases


def _uses_explicit_database_route(tree: ast.AST) -> bool:
    docstring_constant_ids = _docstring_constant_ids(tree)
    for node in ast.walk(tree):
        if id(node) in docstring_constant_ids:
            continue
        if isinstance(node, ast.keyword) and node.arg == "aeat_database_url":
            return True
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and ("AEAT_DATABASE_URL" in node.value or "aeat_database_url" in node.value)
        ):
            return True
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if (
                    isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                    and ("AEAT_DATABASE_URL" in value.value or "aeat_database_url" in value.value)
                ):
                    return True
    return False


def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            ids.add(id(first.value))
    return ids


def test_secure_storage_error_registry_bindings_have_locale_keys() -> None:
    _import_secure_storage_error_modules()
    locale_keys = _locale_key_map()
    offences: list[str] = []
    for error_type in sorted(_iter_error_subclasses(SecureStorageError), key=lambda cls: cls.__name__):
        code = get_registered_error_code(error_type)
        if code.code not in ERROR_REGISTRY:
            offences.append(f"{error_type.__module__}.{error_type.__name__}: unregistered code {code.code}")
        missing = [locale_name for locale_name, keys in locale_keys.items() if code.message_key not in keys]
        if missing:
            offences.append(f"{error_type.__module__}.{error_type.__name__}: {code.message_key} missing from {missing}")

    assert offences == []


def _function_named(
    path: Path,
    name: str,
    source_tree_ast: Mapping[Path, ast.AST] | None = None,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast_for_path(path, source_tree_ast)
    assert tree is not None, f"{repo_relative(path)} must be parseable"
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{repo_relative(path)} does not define {name}")


def _source_segment(path: Path, node: ast.AST) -> str:
    source = path.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, node)
    assert segment is not None
    return segment


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_logger_call(node: ast.AST, method: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "_log"
    )


def _call_has_keyword(node: ast.Call, keyword_name: str) -> bool:
    return any(keyword.arg == keyword_name for keyword in node.keywords)


def _is_kdf_default_to_manifest_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "to_manifest_params":
        return False
    default_call = node.func.value
    return (
        isinstance(default_call, ast.Call)
        and isinstance(default_call.func, ast.Attribute)
        and default_call.func.attr == "default"
        and isinstance(default_call.func.value, ast.Name)
        and default_call.func.value.id == "KdfParams"
    )


def _is_pytest_skip_or_xfail_marker(node: ast.AST) -> bool:
    name = qualified_name(node)
    return name in {
        "pytest.skip",
        "pytest.mark.skip",
        "pytest.mark.skipif",
        "pytest.mark.xfail",
        "skip",
        "skipif",
        "xfail",
    }


def _is_mock_import(node: ast.AST) -> bool:
    if isinstance(node, ast.ImportFrom):
        return node.module in {"mock", "unittest.mock"} or (
            node.module == "unittest" and any(alias.name == "mock" for alias in node.names)
        )
    if isinstance(node, ast.Import):
        return any(alias.name in {"mock", "unittest.mock"} for alias in node.names)
    return False


def _collect_string_bindings(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.target.id] = node.value.value
    return constants


def _collect_os_aliases(tree: ast.AST) -> set[str]:
    aliases = {"os"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update(alias.asname or "os" for alias in node.names if alias.name == "os")
    return aliases


def _collect_environ_aliases(tree: ast.AST) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            aliases.update(alias.asname or "environ" for alias in node.names if alias.name == "environ")
    return aliases


def _is_environment_call(
    node: ast.Call,
    constants: dict[str, str],
    os_aliases: set[str],
    environ_aliases: set[str],
) -> bool:
    qualified = qualified_name(node.func)
    os_functions = {f"{alias}.{name}" for alias in os_aliases for name in ("getenv", "putenv", "unsetenv")}
    if qualified in os_functions or qualified == "getenv":
        return True
    if _is_environ_method_call(node, os_aliases, environ_aliases):
        return True
    if _call_name(node.func) in {"setenv", "delenv", "putenv", "unsetenv"}:
        return bool(node.args) and _env_key_name(node.args[0], constants) is not None
    return False


def _env_key_for_call(node: ast.Call, constants: dict[str, str]) -> str | None:
    if not node.args:
        return None
    if _call_name(node.func) == "update":
        return _env_key_from_mapping(node.args[0], constants)
    return _env_key_name(node.args[0], constants)


def _env_key_name(node: ast.expr, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id, node.id)
    return None


def _env_key_from_mapping(node: ast.expr, constants: dict[str, str]) -> str | None:
    if not isinstance(node, ast.Dict):
        return None
    for key in node.keys:
        if key is not None and (resolved := _env_key_name(key, constants)) is not None:
            return resolved
    return None


def _is_allowed_env_key(relative: str, key: str | None) -> bool:
    if key is None:
        return False
    return key in _ALLOWED_ENV_KEYS_BY_SURFACE.get(relative, set())


def _mutates_environment(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.Delete,
    constants: dict[str, str],
    os_aliases: set[str],
    environ_aliases: set[str],
) -> bool:
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign | ast.AugAssign):
        targets.append(node.target)
    elif isinstance(node, ast.Delete):
        targets.extend(node.targets)
    return any(
        isinstance(target, ast.Subscript)
        and _is_environ_target(target.value, os_aliases, environ_aliases)
        and _env_key_name(target.slice, constants) is not None
        for target in targets
    )


def _is_environ_method_call(node: ast.Call, os_aliases: set[str], environ_aliases: set[str]) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr in {"get", "pop", "setdefault", "update", "__setitem__"}
        and _is_environ_target(node.func.value, os_aliases, environ_aliases)
    )


def _is_environ_target(node: ast.expr, os_aliases: set[str], environ_aliases: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in environ_aliases
    if not isinstance(node, ast.Attribute) or node.attr != "environ":
        return False
    return isinstance(node.value, ast.Name) and node.value.id in os_aliases


def _import_secure_storage_error_modules() -> None:
    for module_name in (
        "aeat.adapters.persistence.storage.bucket._errors",
        "aeat.adapters.persistence.storage.errors",
        "aeat.adapters.persistence.storage.master_key._active_session",
    ):
        importlib.import_module(module_name)


def _iter_error_subclasses(root: type[AeatError]) -> set[type[AeatError]]:
    discovered: set[type[AeatError]] = set()
    for subclass in root.__subclasses__():
        discovered.add(subclass)
        discovered.update(_iter_error_subclasses(subclass))
    return discovered


def _locale_key_map() -> dict[str, set[str]]:
    locales_dir = SRC_AEAT / "locales"
    manager = LocaleManager(SRC_AEAT, locales_dir)
    return {
        locale_path.name: manager.get_yaml_keys(manager.load_locale(locale_path))
        for locale_path in sorted(locales_dir.glob("*.yml"))
    }
