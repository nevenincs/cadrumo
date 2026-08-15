"""Policy coverage gate for repair, recovery, import, export, and profile-history commands.

The catalog is bound in both directions. The *coverage* direction (a
policy-relevant command declared in the CLI sources must carry a policy row)
walks the command declarations by AST. The *liveness* direction — every
catalogued ``command_path`` must resolve to a command the live CLI actually
registers — is derived from the live click tree, with nothing hand-listed:
see :func:`test_every_catalogued_command_path_resolves_in_the_live_cli`.

That second direction is what keeps a policy row from outliving its verb. The
row is an operator-facing inventory of command paths written WITHOUT the
``aeat`` executable token, so neither
:mod:`test_documented_command_conformance` (which anchors on the executable
token in docs) nor :mod:`test_suggestion_command_conformance` (which anchors on
it in string literals) can see it. Six rows for retired custody verbs and two
for never-implemented profile-bundle verbs sat here unnoticed for exactly that
reason.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import click
import pytest

from ....adapters.persistence.storage import STORAGE_NAMESPACE_REGISTRY, WORKFLOW_STATE_NAMESPACE
from ....application.repair_integrity import build_repair_policy_command_surface_catalog
from ....tests.cli_runner import cadrumo_click_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI_DIR = Path(__file__).resolve().parents[1]

_POLICY_COMMAND_MODULES: tuple[tuple[Path, str, tuple[str, ...]], ...] = (
    (_CLI_DIR / "_config" / "__init__.py", "app", ("config",)),
    (_CLI_DIR / "_config" / "_custody.py", "app", ("config",)),
    (_CLI_DIR / "_config" / "_bucket_history.py", "profile_app", ("config", "profile")),
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

# Command-path prefixes whose every leaf is policy-relevant in full because it
# mutates or inspects secure-storage custody, independently of the leaf-name
# rules in :func:`_requires_policy_coverage`. Both are DORMANT today: neither
# family is registered, so the clause selects nothing. That dormancy is asserted
# rather than assumed — see
# :func:`test_custody_family_prefixes_are_dormant_or_fully_catalogued`, without
# which a renamed or re-mounted family would let this clause pass vacuously.
_CUSTODY_FAMILY_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("config", "recovery"),
    ("config", "passphrase"),
)


def test_declared_policy_command_modules_all_exist() -> None:
    """Every module this gate AST-walks is still on disk.

    The walk's denominator is a hand-maintained module list, so a deleted module
    silently shrinks what the coverage direction can discover. Two entries
    (``_custody_secret.py`` and ``_profile_bundle.py``) were deleted by the
    custody cutover and left standing here, which raised a bare
    ``FileNotFoundError`` from inside the coverage assertion — an error, not a
    failure, and therefore unreadable as the drift signal it was. A stale entry
    must fail as a stale entry.
    """
    missing = [str(path.relative_to(_CLI_DIR)) for path, _, _ in _POLICY_COMMAND_MODULES if not path.is_file()]
    assert not missing, (
        f"policy-command modules listed by this gate no longer exist: {missing}. "
        "Remove the entry (and any catalog row that only it discovered), or restore the module."
    )


def test_policy_command_surface_catalog_covers_cli_repair_import_export_and_profile_history_commands() -> None:
    discovered = _policy_relevant_command_paths_from_sources()
    catalogued = {surface.command_path for surface in build_repair_policy_command_surface_catalog()}

    assert catalogued == discovered


def test_every_catalogued_command_path_resolves_in_the_live_cli() -> None:
    """No policy row may outlive the command it governs.

    The property, not a list of names: each ``command_path`` is walked against
    the live click tree and must land on a registered command. Nothing here
    enumerates a retired verb, so a future retirement is caught whether or not
    anyone remembers this gate exists.

    This is the direction the sibling citation gates structurally cannot cover.
    A ``command_path`` here is written without the ``aeat`` executable token,
    and both of those gates anchor their extraction on that token, so eight
    dead rows — the six retired custody verbs plus the two profile-bundle verbs
    that were never implemented — sat in production unseen while every
    ``aeat``-prefixed citation of the same verbs was already red.
    """
    live = _live_command_paths()
    dead = sorted(
        surface.command_path
        for surface in build_repair_policy_command_surface_catalog()
        if surface.command_path not in live
    )
    assert not dead, (
        "repair-policy rows govern command paths the live CLI does not register: "
        f"{dead}. A policy row for an unregistered verb is a dead operator instruction — "
        "remove the row, or register the verb."
    )


def test_custody_family_prefixes_are_dormant_or_fully_catalogued() -> None:
    """The custody carve-out is either selecting nothing, or selecting completely.

    :func:`_requires_policy_coverage` pins two family prefixes by name. Neither
    is registered today, so the clause is dormant and cannot be exercised — the
    shape that lets a pinned-name rule pass vacuously after a rename. This
    anchor states the dormancy as an assertion: if a prefix acquires live
    leaves (per-profile recovery landing, or passphrase rotation being built),
    the clause activates and every leaf under it must carry a policy row.
    """
    live = _live_command_paths()
    catalogued = {surface.command_path for surface in build_repair_policy_command_surface_catalog()}
    for prefix in _CUSTODY_FAMILY_PREFIXES:
        joined = " ".join(prefix)
        leaves = {path for path in live if path.split()[: len(prefix)] == list(prefix)}
        assert leaves <= catalogued, (
            f"`{joined}` is registered again and its leaves {sorted(leaves - catalogued)} carry no "
            "repair-policy row; the custody carve-out has activated and the catalog must follow it"
        )


def test_the_live_command_walk_is_not_vacuous() -> None:
    """The live walk materializes the real tree, lazy subtrees included.

    Every assertion above that reads ``no catalogued path is missing from the
    live tree`` inverts if the walk returns little or nothing: an empty walk
    would report every row dead, and a walk that stops at the first lazy group
    would report the deep ones dead. Anchor on the property (known deep,
    lazily-loaded leaves are present) plus a floor well below the observed
    size, never an exact tally.
    """
    live = _live_command_paths()
    assert len(live) > 100, (
        f"the live command walk found only {len(live)} leaves; the lazy subcommand loaders "
        "did not materialize, so every liveness assertion in this module is meaningless"
    )
    for anchor in ("config repair quarantine", "config profile history", "app modelo audit export"):
        assert anchor in live, f"the live walk missed the registered leaf `{anchor}`"


def _live_command_paths() -> frozenset[str]:
    """Every registered leaf command path in the live CLI, ``aeat`` token dropped.

    Walks the real click tree materialized from the Cadrumo app, so the lazy
    subcommand loaders run and deep groups are reached. Paths are space-joined
    to match the catalog's ``command_path`` shape.
    """
    root = cadrumo_click_command()
    found: set[str] = set()
    _collect_leaf_paths(root, click.Context(root, info_name="aeat"), (), found)
    return frozenset(found)


def _collect_leaf_paths(
    command: click.Command,
    ctx: click.Context,
    prefix: tuple[str, ...],
    found: set[str],
) -> None:
    # ``list_commands`` is the structural group marker; the vendored TyperGroup
    # is not a guaranteed ``click.Group`` subclass, so narrow by interface
    # (cast) rather than isinstance, matching the sibling conformance gate.
    if not hasattr(command, "list_commands"):
        if prefix:
            found.add(" ".join(prefix))
        return
    group = cast(click.Group, command)
    names = group.list_commands(ctx)
    if not names and prefix:
        found.add(" ".join(prefix))
        return
    for name in names:
        child = group.get_command(ctx, name)
        if child is None:
            continue
        _collect_leaf_paths(child, click.Context(child, info_name=name, parent=ctx), (*prefix, name), found)


def test_policy_command_surfaces_are_owned_and_namespace_policies_are_registered() -> None:
    surfaces = build_repair_policy_command_surface_catalog()
    assert len({surface.command_path for surface in surfaces}) == len(surfaces)
    registered = {definition.namespace: definition for definition in STORAGE_NAMESPACE_REGISTRY.namespaces}

    for surface in surfaces:
        assert surface.owner_domains
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
    constructor_names = _typer_constructor_names(tree)
    mounts: dict[str, list[tuple[str, str]]] = {}
    commands: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            _collect_typer_mount(node.value, mounts, constructor_names)
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


def _typer_constructor_names(tree: ast.AST) -> dict[str, str]:
    """Map ``var = typer.Typer(name="...")`` assignments to their declared mount name."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        is_typer = (isinstance(func, ast.Attribute) and func.attr == "Typer") or (
            isinstance(func, ast.Name) and func.id == "Typer"
        )
        if not is_typer:
            continue
        declared = _keyword_literal(node.value, "name")
        if declared is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names[target.id] = declared
    return names


def _collect_typer_mount(
    call: ast.Call,
    mounts: dict[str, list[tuple[str, str]]],
    constructor_names: dict[str, str],
) -> None:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "add_typer":
        return
    if not isinstance(call.func.value, ast.Name):
        return
    if not call.args or not isinstance(call.args[0], ast.Name):
        return
    child_var = call.args[0].id
    # ``add_typer(child, name="x")`` names the mount at the call site;
    # ``add_typer(child)`` inherits the child's ``typer.Typer(name="x")``.
    mount_name = _keyword_literal(call, "name") or constructor_names.get(child_var)
    if mount_name is None:
        return
    mounts.setdefault(call.func.value.id, []).append((child_var, mount_name))


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
        "restore",
    }
    # The custody subgroups are policy-relevant in full: every leaf under them
    # mutates or inspects secure-storage custody. Dormant today (neither family
    # is registered), and asserted dormant by
    # ``test_custody_family_prefixes_are_dormant_or_fully_catalogued`` so the
    # clause cannot go vacuous unnoticed.
    if any(tuple(tokens[: len(prefix)]) == prefix for prefix in _CUSTODY_FAMILY_PREFIXES):
        return True
    # `config profile history` is the append-only event-history audit surface
    # (formerly `config bucket history`, D1 family rename). It is the only
    # `history` verb that requires policy coverage — `app ledger history` and
    # other read verbs do not. Scope the match to the config-rooted history
    # verb so unrelated `history` leaves are not pulled into the gate.
    config_history = "config" in tokens and "history" in tokens
    return "repair" in tokens or config_history or tokens[-1] in recovery_leaves
