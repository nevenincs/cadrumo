"""Static guards for secure-storage production-hardening conventions."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import NamedTuple

import pytest
from dev.locales import LocaleManager

from cadrumo.adapters.persistence.storage.errors import SecureStorageError
from cadrumo.core import scan_directory
from cadrumo.core.errors import ERROR_REGISTRY, CadrumoError, get_registered_error_code
from cadrumo.tests import (
    SRC_CADRUMO,
    ast_for_path,
    leaf_name,
    package_ast_items,
    qualified_name,
    repo_path,
    repo_relative,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_HARDENING_TEST_SURFACES = (
    "src/cadrumo/adapters/persistence/storage/blob_store/tests/test_materialisation.py",
    "src/cadrumo/adapters/persistence/storage/tests/test_runtime.py",
    # Successor of `test_profile_repository.py`, which no longer exists: the
    # profile repository's test module in that package is now `test_repository`.
    # The stale name silently dropped a surface from the environment-mutation
    # guard, because an unreadable path yields no AST to scan.
    "src/cadrumo/application/user_profile/tests/test_repository.py",
    "src/cadrumo/core/tests/test_storage_route_classification.py",
    "src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py",
)

_ALLOWED_ENV_KEYS_BY_SURFACE: dict[str, set[str]] = {}
_ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS = {
    "src/cadrumo/adapters/persistence/storage/runtime.py",
    "src/cadrumo/adapters/persistence/storage/runtime_repository.py",
}
_APPROVED_EXPLICIT_ROUTE_TEST_SURFACES = {
    "src/cadrumo/adapters/persistence/storage/master_key/tests/test_adverse_sessions.py",
    "src/cadrumo/adapters/persistence/storage/envelope/tests/test_secure_bound_repository_contract.py",
    "src/cadrumo/adapters/persistence/storage/envelope/tests/_repository_contract_support.py",
    "src/cadrumo/adapters/persistence/storage/sql/tests/test_engine.py",
    "src/cadrumo/adapters/persistence/storage/tests/test_runtime.py",
    "src/cadrumo/application/tests/test_diagnostics.py",
    "src/cadrumo/application/modelo/tests/test_export_iva_wallet.py",
    "src/cadrumo/application/tests/test_repair_integrity.py",
    "src/cadrumo/application/tests/test_state_projection.py",
    "src/cadrumo/application/tests/test_storage_write_policy.py",
    "src/cadrumo/application/workflow/tests/test_runtime_defaults.py",
    "src/cadrumo/core/tests/test_storage_route_classification.py",
    "src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py",
    "src/cadrumo/tests/secure_sql.py",
    # Approved on the same ground as every entry above: the explicit database
    # route is the SUBJECT of these modules, not convenience setup they could
    # have avoided. The first two exercise the engine's own route handling --
    # `test_bucket_root_is_capsule_owned` is the dedicated module for the
    # refusal that a bucket root is never created by opening an engine, which
    # cannot be reached without pointing a route at an unpublished bucket, and
    # `engine_bootstrap` is the shared plumbing the already-approved `sql/` and
    # `envelope/` suites build their engines with. The last two assert the
    # operator-facing guard that REFUSES an explicit route, alongside the
    # already-approved `test_root_fallback_write_guard`.
    "src/cadrumo/adapters/persistence/storage/sql/tests/test_bucket_root_is_capsule_owned.py",
    "src/cadrumo/adapters/persistence/storage/tests/engine_bootstrap.py",
    "src/cadrumo/entrypoints/cli/tests/test_refusal_boundary_action_projection.py",
    "src/cadrumo/entrypoints/cli/tests/test_root_guard_typed_projection.py",
}


class _HardeningInventory(NamedTuple):
    repository_construction_offences: list[str]
    explicit_route_setup_offences: list[str]


@pytest.fixture(scope="module")
def hardening_inventory() -> _HardeningInventory:
    repository_construction_offences: list[str] = []
    explicit_route_setup_offences: list[str] = []

    for path, tree in package_ast_items(include_data=True):
        relative = repo_relative(path)
        if not _is_test_surface(relative):
            repository_construction_offences.extend(_repository_construction_offences(relative, tree))
        if (
            _is_test_setup_surface(relative)
            and _uses_explicit_database_route(tree)
            and relative not in _APPROVED_EXPLICIT_ROUTE_TEST_SURFACES
        ):
            explicit_route_setup_offences.append(f"{relative}: unapproved explicit database route test setup")

    return _HardeningInventory(
        repository_construction_offences=repository_construction_offences,
        explicit_route_setup_offences=explicit_route_setup_offences,
    )


def test_bucket_session_cleanup_observability_does_not_use_suppression_markers() -> None:
    path = repo_path("src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py")
    function = _function_named(path, "_dispose_engine")
    segment = _source_segment(path, function)

    assert "# noqa" not in segment
    assert "pragma: no cover" not in segment
    assert "pass" not in {node.__class__.__name__.lower() for node in ast.walk(function)}
    assert any(_is_logger_call(node, "debug") or _is_logger_call(node, "warning") for node in ast.walk(function))
    assert not any(_call_has_keyword(node, "exc_info") for node in ast.walk(function) if isinstance(node, ast.Call))


def test_named_bucket_settings_derivation_stays_in_core_settings_boundary() -> None:
    runtime_path = repo_path("src/cadrumo/adapters/persistence/storage/runtime.py")
    route_path = repo_path("src/cadrumo/core/_config_storage_route.py")

    runtime_text = runtime_path.read_text(encoding="utf-8")
    assert "__pydantic_fields_set__" not in runtime_text
    assert "settings_for_active_profile_bucket" in runtime_text

    config_function = _function_named(route_path, "settings_for_bucket_route")
    config_segment = _source_segment(route_path, config_function)
    assert "__pydantic_fields_set__" in config_segment
    assert "cadrumo_database_url" in config_segment


# The profile-repository KDF-defaults guard was RETIRED here rather than
# repaired. It asserted that `_default_kdf_params` in
# `application/user_profile/_profile_repository.py` derived its Argon2 fields
# from `KdfParams.default().to_manifest_params()` instead of restating them.
# Every noun in that sentence is gone: the shared-master `ManifestKdfParams`
# model and `to_manifest_params` no longer exist in production anywhere, the
# function is gone, and the module is now a committed-capsule label projection
# that holds no KDF concern. Reinstating the function to satisfy the guard
# would be a shim for a retired surface.
#
# The property has no successor subject either, and that is the reason it needs
# no successor guard: `ProfileCustodyKdfParameters` is constructed at exactly
# two production sites, both inside `custody/_kdf_supervision.py` -- the
# calibration grid and its one documented fallback -- so the defect shape the
# guard watched for (a consuming module restating KDF fields and drifting from
# the canonical model) has nowhere left to occur. If a second package ever
# constructs that record, this is the guard to bring back.


def test_production_secure_object_repository_construction_stays_runtime_owned(
    hardening_inventory: _HardeningInventory,
) -> None:
    assert hardening_inventory.repository_construction_offences == []


def test_explicit_database_route_test_setup_stays_approved(hardening_inventory: _HardeningInventory) -> None:
    assert hardening_inventory.explicit_route_setup_offences == []


def test_every_allowed_repository_constructor_still_needs_its_entry() -> None:
    """Each allowed constructor path must exist and still construct the repository.

    Presence is not liveness. An entry whose module was deleted or renamed, or
    which stopped constructing a :class:`SecureObjectRepository`, keeps a path
    pre-authorised for direct construction -- so whatever later occupies that
    path inherits an exemption nobody granted it.

    The check is redundancy rather than existence: drop the entry, re-run the
    real detector over the module, and require it to report the direct
    construction it was exempting.
    """
    stale: list[str] = []
    original = set(_ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS)
    for relative in sorted(original):
        path = repo_path(relative)
        if not path.is_file():
            stale.append(f"{relative} (file absent)")
            continue
        tree = ast_for_path(path)
        assert tree is not None, f"{relative}: source must be parseable"
        _ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS.clear()
        _ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS.update(original - {relative})
        try:
            offences = _repository_construction_offences(relative, tree)
        finally:
            _ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS.clear()
            _ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS.update(original)
        if not any("direct SecureObjectRepository construction" in offence for offence in offences):
            stale.append(f"{relative} (no longer constructs a SecureObjectRepository; drop the entry)")
    assert not stale, "Stale _ALLOWED_PRODUCTION_SECURE_OBJECT_REPOSITORY_CONSTRUCTORS entries:\n" + "\n".join(
        f"  {entry}" for entry in stale
    )


def test_every_hardening_test_surface_resolves_to_a_real_module() -> None:
    """Every enumerated hardening surface must exist, or it is silently unscanned.

    The environment-mutation guard iterates this fixed list. A path that no
    longer resolves contributes no AST, so the surface drops out of the scan
    while the list still reads as covering it -- the same fail-open shape the
    approval lists above each carry their own liveness check for.
    """
    absent = [relative for relative in _HARDENING_TEST_SURFACES if not repo_path(relative).is_file()]
    assert absent == [], f"_HARDENING_TEST_SURFACES entries resolve to nothing and are therefore unscanned: {absent}"


def test_every_approved_explicit_route_surface_still_needs_its_entry() -> None:
    """Each approved route surface must exist and still set an explicit route.

    The sibling of the constructor liveness check above, and it was missing:
    one entry already named a module that no longer exists, so the approval
    list had begun pre-authorising a path nobody was watching. An approval that
    outlives its subject is worse than no approval, because whatever later
    occupies the path inherits an exemption nobody granted it.

    Liveness rather than mere presence: drop the entry, re-run the real
    detector over the module, and require it to report the explicit route the
    entry was approving.
    """
    stale: list[str] = []
    for relative in sorted(_APPROVED_EXPLICIT_ROUTE_TEST_SURFACES):
        path = repo_path(relative)
        if not path.is_file():
            stale.append(f"{relative} (file absent)")
            continue
        tree = ast_for_path(path)
        assert tree is not None, f"{relative}: source must be parseable"
        if not _uses_explicit_database_route(tree):
            stale.append(f"{relative} (no longer sets an explicit database route; drop the entry)")
    assert not stale, "Stale _APPROVED_EXPLICIT_ROUTE_TEST_SURFACES entries:\n" + "\n".join(
        f"  {entry}" for entry in stale
    )


def _repository_construction_offences(relative: str, tree: ast.AST) -> list[str]:
    offences: list[str] = []
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
    return offences


def test_explicit_database_route_detector_ignores_env_absence_and_flags_real_routes() -> None:
    absent_tree = ast.parse(
        """
env = {
    "CADRUMO_DATABASE_URL": None,
}
"""
    )
    keyword_tree = ast.parse('Settings(cadrumo_database_url="sqlite:///explicit.db")')
    env_tree = ast.parse('env = {"CADRUMO_DATABASE_URL": "sqlite:///explicit.db"}')

    assert not _uses_explicit_database_route(absent_tree)
    assert _uses_explicit_database_route(keyword_tree)
    assert _uses_explicit_database_route(env_tree)


def test_hardening_test_surfaces_do_not_mutate_environment_directly() -> None:
    offences: list[str] = []
    for relative in _HARDENING_TEST_SURFACES:
        path = repo_path(relative)
        tree = ast_for_path(path)
        assert tree is not None, f"{relative}: source must be parseable"
        constants = _collect_string_bindings(tree)
        os_aliases = _collect_os_aliases(tree)
        environ_aliases = _collect_environ_aliases(tree)
        for node in ast.walk(tree):
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
            "cadrumo.adapters.persistence.storage",
            "cadrumo.adapters.persistence.storage.sql",
            "cadrumo.adapters.persistence.storage.sql.secure_objects",
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
        if isinstance(node, ast.keyword) and node.arg == "cadrumo_database_url":
            return not _is_none_literal(node.value)
        if isinstance(node, ast.Dict) and _dict_sets_explicit_database_route(node):
            return True
    return False


def _dict_sets_explicit_database_route(node: ast.Dict) -> bool:
    for key, value in zip(node.keys, node.values, strict=True):
        if _literal_string(key) in {"CADRUMO_DATABASE_URL", "cadrumo_database_url"} and not _is_none_literal(value):
            return True
    return False


def _is_none_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


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


def _function_named(path: Path, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast_for_path(path)
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
    if leaf_name(node.func) in {"setenv", "delenv", "putenv", "unsetenv"}:
        return bool(node.args) and _env_key_name(node.args[0], constants) is not None
    return False


def _env_key_for_call(node: ast.Call, constants: dict[str, str]) -> str | None:
    if not node.args:
        return None
    if leaf_name(node.func) == "update":
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
        "cadrumo.adapters.persistence.storage.bucket._errors",
        "cadrumo.adapters.persistence.storage.errors",
        "cadrumo.adapters.persistence.storage.master_key._active_session",
    ):
        importlib.import_module(module_name)


def _iter_error_subclasses(root: type[CadrumoError]) -> set[type[CadrumoError]]:
    discovered: set[type[CadrumoError]] = set()
    for subclass in root.__subclasses__():
        discovered.add(subclass)
        discovered.update(_iter_error_subclasses(subclass))
    return discovered


def _locale_key_map() -> dict[str, set[str]]:
    locales_dir = SRC_CADRUMO / "locales"
    manager = LocaleManager(SRC_CADRUMO, locales_dir)
    return {
        locale_path.name: manager.get_yaml_keys(manager.load_locale(locale_path))
        for locale_path in scan_directory(locales_dir, pattern="*.yml")
    }
