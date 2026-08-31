"""Policy coverage gate for repair, recovery, import, export, and profile-history commands.

The catalog is bound in both directions, and both are now derived from the
live click tree rather than any hand-listed inventory. The *coverage*
direction (a policy-relevant command the live CLI registers must carry a
policy row) filters :func:`_live_command_paths` through
:func:`_requires_policy_coverage`. The *liveness* direction — every catalogued
``command_path`` must resolve to a command the live CLI actually registers —
walks the same tree the other way: see
:func:`test_every_catalogued_command_path_resolves_in_the_live_cli`.

A hand-maintained module list previously stood in for the coverage direction,
which let a declared-but-unmounted command satisfy the check by AST alone, and
let a module added without also being added to the list go uncovered by
construction. Both failure modes are structural with a hand-listed
denominator and impossible against the live tree: a command cannot be
"coverage-visible but not actually registered", because coverage IS derived
from what is registered.

The row is an operator-facing inventory of command paths written WITHOUT the
``aeat`` executable token, so neither
:mod:`test_documented_command_conformance` (which anchors on the executable
token in docs) nor :mod:`test_suggestion_command_conformance` (which anchors on
it in string literals) can see it. Six rows for retired custody verbs and two
for never-implemented profile-bundle verbs once sat here unnoticed for exactly
that reason.
"""

from __future__ import annotations

from typing import cast

import click
import pytest

from ....adapters.persistence.storage._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ....adapters.persistence.storage._secure_object_namespaces import WORKFLOW_STATE_NAMESPACE
from ....application.repair_integrity import build_repair_policy_command_surface_catalog
from ....tests.cli_runner import cadrumo_click_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

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
    """Every policy-relevant command path the live CLI actually registers.

    Derived from the same live click-tree walk the liveness direction uses
    (:func:`_live_command_paths`), so a command cannot be coverage-visible
    without being registered, and a newly mounted module is discovered the
    moment its command is reachable rather than the moment someone remembers
    to add its source file to a hand-maintained list.
    """
    return {path for path in _live_command_paths() if _requires_policy_coverage(path)}


def _requires_policy_coverage(command_path: str) -> bool:
    tokens = command_path.split()
    # The four local-transport tokens plus the remote pair. D2 split transport
    # verbs by counterparty -- `export`/`import` move data to and from a local
    # filesystem, `push`/`pull` move it to and from a remote -- so a predicate
    # naming only the local half governs half the data-movement surface. It
    # silently dropped `app modelo spreadsheet push`, which writes
    # SYNC_RUN_RECORDS and WAS governed under its pre-D2 name. The catalogue
    # governs surfaces that "inspect, repair, import, export, or recover
    # namespace-owned data", and a remote read persists what it fetches, so the
    # remote tokens belong here on the same reasoning as the local ones.
    recovery_leaves = {
        "export",
        "import",
        "recover",
        "restore",
        "push",
        "push-all",
        "pull",
        "pull-all",
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
