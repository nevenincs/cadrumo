"""Policy coverage gate for repair, recovery, import, export, and profile-history commands."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....adapters.persistence.storage import STORAGE_NAMESPACE_REGISTRY, WORKFLOW_STATE_NAMESPACE
from ....application.repair_integrity import build_repair_policy_command_surface_catalog

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI_DIR = Path(__file__).resolve().parents[1]

_POLICY_COMMAND_MODULES: tuple[tuple[Path, str, tuple[str, ...]], ...] = (
    (_CLI_DIR / "_config" / "__init__.py", "app", ("config",)),
    (_CLI_DIR / "_config" / "_custody.py", "app", ("config",)),
    (_CLI_DIR / "_config" / "_custody_secret.py", "app", ("config",)),
    (_CLI_DIR / "_config" / "_bucket_history.py", "profile_app", ("config", "profile")),
    (_CLI_DIR / "_config" / "_profile_bundle.py", "profile_app", ("config", "profile")),
    (_CLI_DIR / "_config" / "_repair_cli.py", "repair_app", ("config", "repair")),
    (_CLI_DIR / "_config" / "_repair_profile.py", "repair_app", ("config", "repair")),
    (_CLI_DIR / "_ledger.py", "app", ("app", "ledger")),
    (_CLI_DIR / "_ledger_import_cli.py", "app", ("app", "ledger")),
    (_CLI_DIR / "_ledger_read_cli.py", "app", ("app", "ledger")),
    (_CLI_DIR / "_modelo.py", "app", ("app", "modelo")),
    (_CLI_DIR / "_modelo_audit_cli.py", "audit_app", ("app", "modelo", "audit")),
    (_CLI_DIR / "_modelo_export_cli.py", "app", ("app", "modelo")),
    (_CLI_DIR / "_modelo_records_cli.py", "filing_record_app", ("app", "modelo", "filing-record")),
    (_CLI_DIR / "_app_live.py", "app", ("app", "live")),
)


def test_policy_command_surface_catalog_covers_cli_repair_import_export_and_profile_history_commands() -> None:
    discovered = _policy_relevant_command_paths_from_sources()
    catalogued = {surface.command_path for surface in build_repair_policy_command_surface_catalog()}

    assert catalogued == discovered


def test_policy_command_surfaces_are_decision_linked_and_namespace_policies_are_registered() -> None:
    surfaces = build_repair_policy_command_surface_catalog()
    assert len({surface.command_path for surface in surfaces}) == len(surfaces)
    registered = {definition.namespace: definition for definition in STORAGE_NAMESPACE_REGISTRY.namespaces}

    for surface in surfaces:
        assert surface.decision_links
        assert surface.owner_domains
        for link in surface.decision_links:
            assert link.startswith("[[")
            assert link.endswith("]]")
        for policy in surface.namespace_policies:
            assert policy.namespace_classification.role != "unknown_secure_object_namespace"
            assert policy.owner_domain != "unknown"
            assert policy.repair_policy
            assert policy.recovery_policy
            assert policy.mutation_authority
            if policy.registered_namespace is not None:
                definition = registered[policy.registered_namespace]
                assert policy.registered_namespace_key == definition.key
                assert policy.registered_owner == definition.owner
                assert policy.owner_domain == definition.owner
                assert policy.registered_sensitivity == definition.sensitivity.value
                assert policy.registered_schema_version == definition.schema_version
                assert policy.registered_scope == definition.scope.value
                assert policy.namespace_classification.role == definition.scope.value


def test_repair_secure_object_surfaces_use_registry_metadata_instead_of_role_markers() -> None:
    surfaces = {surface.command_path: surface for surface in build_repair_policy_command_surface_catalog()}

    quarantine_policies = surfaces["config repair quarantine"].namespace_policies
    assert WORKFLOW_STATE_NAMESPACE.namespace in tuple(policy.registered_namespace for policy in quarantine_policies)
    assert "profile_local_secure_object" not in tuple(
        policy.namespace_classification.role for policy in quarantine_policies
    )

    reset_policies = surfaces["config repair reset-progress"].namespace_policies
    assert tuple(policy.registered_namespace for policy in reset_policies) == (WORKFLOW_STATE_NAMESPACE.namespace,)
    assert reset_policies[0].owner_domain == WORKFLOW_STATE_NAMESPACE.owner

    integrity_policies = surfaces["config repair integrity objects"].namespace_policies
    assert WORKFLOW_STATE_NAMESPACE.namespace in tuple(policy.registered_namespace for policy in integrity_policies)
    assert "profile_local_secure_object" not in tuple(
        policy.namespace_classification.role for policy in integrity_policies
    )


def _policy_relevant_command_paths_from_sources() -> set[str]:
    paths: set[str] = set()
    for source_path, root_var, root_prefix in _POLICY_COMMAND_MODULES:
        paths.update(_command_paths_from_module(source_path, root_var=root_var, root_prefix=root_prefix))
    return {path for path in paths if _requires_policy_coverage(path)}


def _command_paths_from_module(source_path: Path, *, root_var: str, root_prefix: tuple[str, ...]) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    mounts: dict[str, list[tuple[str, str]]] = {}
    commands: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            _collect_typer_mount(node.value, mounts)
        if isinstance(node, ast.FunctionDef):
            _collect_typer_commands(node, commands)

    paths: set[str] = set()

    def walk(app_var: str, prefix: tuple[str, ...]) -> None:
        for command_name in commands.get(app_var, ()):
            paths.add(" ".join((*prefix, command_name)))
        for child_var, mount_name in mounts.get(app_var, ()):
            walk(child_var, (*prefix, mount_name))

    walk(root_var, root_prefix)
    return paths


def _collect_typer_mount(call: ast.Call, mounts: dict[str, list[tuple[str, str]]]) -> None:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "add_typer":
        return
    if not isinstance(call.func.value, ast.Name):
        return
    if not call.args or not isinstance(call.args[0], ast.Name):
        return
    mount_name = _keyword_literal(call, "name")
    if mount_name is None:
        return
    mounts.setdefault(call.func.value.id, []).append((call.args[0].id, mount_name))


def _collect_typer_commands(node: ast.FunctionDef, commands: dict[str, list[str]]) -> None:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        if not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "command":
            continue
        if not isinstance(decorator.func.value, ast.Name):
            continue
        commands.setdefault(decorator.func.value.id, []).append(_command_name(decorator, fallback=node.name))


def _command_name(call: ast.Call, *, fallback: str) -> str:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return fallback.replace("_", "-")


def _keyword_literal(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _requires_policy_coverage(command_path: str) -> bool:
    tokens = command_path.split()
    recovery_leaves = {
        "export",
        "import",
        "recover",
        "recovery",
        "rekey",
        "restore",
        "show-recovery",
        "verify-recovery",
    }
    # `config profile history` is the append-only event-history audit surface
    # (formerly `config bucket history`, D1 family rename). It is the only
    # `history` verb that requires policy coverage — `app ledger history` and
    # other read verbs do not. Scope the match to the config-rooted history
    # verb so unrelated `history` leaves are not pulled into the gate.
    config_history = "config" in tokens and "history" in tokens
    return "repair" in tokens or config_history or tokens[-1] in recovery_leaves
