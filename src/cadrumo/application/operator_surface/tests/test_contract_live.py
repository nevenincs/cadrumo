"""Live reconciliation of the operator surface against the materialised CLI.

Separated from the unit contract suite because it walks the real Typer/Click
tree and projects every verb's input schema, which is an integration-scope act. The
marker taxonomy allows one execution-scope marker per module, so an
integration test cannot share a module with unit tests -- and the split is
honest rather than clerical: this module is the only one here that materialises
the production command tree.

See Also:
    :func:`~application.operator_surface.get_operator_surface_contract`
        Cached contract builder the reconciliation compares against.
    :mod:`~entrypoints.schema_surface`
        Declared callback, reuse and root-landing authorities the walk reconciles.
"""

from __future__ import annotations

import pytest
from typer._click.core import Command as ClickCommand
from typer._click.core import Context as ClickContext
from typer.main import get_command as typer_get_command

from ._contract_locale_fixture import pin_english_locale

__all__ = ["pin_english_locale"]

from ....entrypoints.cli import (
    VerbLeafKind,
    build_verb_input_schemas,
    command_execution_policy_for_cli_path,
    command_schema_refs,
    is_exposable_command,
)
from ....entrypoints.cli import app as cli_app
from ....entrypoints.schema_surface import (
    CALLBACK_EXCLUSION_REASON_BY_CLI_PATH,
    CALLBACK_RESULT_REUSE_BY_CLI_PATH,
    CALLBACK_SCHEMA_KEY_BY_CLI_PATH,
    GROUP_CALLBACK_SCHEMA_KEYS,
    ROOT_LANDING_SCHEMA_KEYS,
    normalise_cli_path_to_schema_key,
)
from .. import (
    MountedCommandDomain,
    OperatorMutability,
    RootSurfaceName,
    get_operator_surface_contract,
)
from .._manifest import (
    ExplicitExclusionInventoryRow,
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    MountedFamilyInventoryRow,
    OperatorSurfaceReconciliation,
    ProfilePolicyInventoryRow,
    ReconciliationSurface,
    ResultSchemaInventoryRow,
    SurfaceExposureInventoryRow,
    reconcile_operator_surface_inventory,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _raw_live_click_surface() -> tuple[
    dict[tuple[str, ...], ClickCommand],
    frozenset[tuple[str, ...]],
    dict[tuple[str, ...], tuple[str, ...]],
]:
    """Walk the materialised production CLI without consulting any schema projection.

    Terminal commands and ``invoke_without_command`` callbacks are intentionally
    recorded separately.  The latter are real dispatch surfaces but do not appear
    as child leaves in Click's tree, which is exactly the blind spot this
    reconciliation is meant to close.
    """
    root = typer_get_command(cli_app)
    terminals: dict[tuple[str, ...], ClickCommand] = {}
    callbacks: set[tuple[str, ...]] = set()
    children_by_group: dict[tuple[str, ...], tuple[str, ...]] = {}

    def walk(command: ClickCommand, context: ClickContext, path: tuple[str, ...]) -> None:
        lister = getattr(command, "list_commands", None)
        getter = getattr(command, "get_command", None)
        if not callable(lister) or not callable(getter):
            terminals[path] = command
            return
        if bool(getattr(command, "invoke_without_command", False)):
            callbacks.add(path)
        child_names = tuple(str(name) for name in lister(context))
        children_by_group[path] = child_names
        for child_name in child_names:
            child = getter(context, child_name)
            if child is not None:
                walk(
                    child,
                    ClickContext(child, parent=context, info_name=child_name),
                    (*path, child_name),
                )

    walk(root, ClickContext(root, info_name=str(root.name)), ())
    return terminals, frozenset(callbacks), children_by_group


def _live_reconciliation() -> OperatorSurfaceReconciliation:
    """Build the reconciliation from the raw walk, for membership-only assertions.

    Kept deliberately thin: it repeats none of the sibling test's independence
    proofs, and asserts nothing itself. Its only job is to hand a second test
    the same joined report without either test importing the CLI adapter's
    private per-invocation cache.
    """
    raw_terminals, _, _ = _raw_live_click_surface()
    primary_path_by_key = {normalise_cli_path_to_schema_key(path): path for path in raw_terminals}
    for callback_path, key in CALLBACK_SCHEMA_KEY_BY_CLI_PATH.items():
        primary_path_by_key[key] = callback_path
    callback_reuse_paths_by_key: dict[str, set[tuple[str, ...]]] = {}
    for callback_path, key in CALLBACK_RESULT_REUSE_BY_CLI_PATH.items():
        callback_reuse_paths_by_key.setdefault(key, set()).add(callback_path)

    keys = tuple(sorted(primary_path_by_key))
    input_schemas = build_verb_input_schemas(keys)
    return reconcile_operator_surface_inventory(
        live_leaves=tuple(
            LiveLeafInventoryRow(
                subject_leaf_key=key,
                canonical_cli_path=primary_path_by_key[key],
                alias_cli_paths=tuple(sorted(callback_reuse_paths_by_key.get(key, set()))),
                provenance="raw materialised Click traversal with declared callback reuse",
            )
            for key in keys
        ),
        result_schemas=tuple(
            ResultSchemaInventoryRow(
                subject_leaf_key=ref.command,
                schema_name=ref.schema_name,
                provenance="SCHEMA_REGISTRY through command_schema_refs",
            )
            for ref in command_schema_refs()
            if ref.command in primary_path_by_key
        ),
        input_schemas=tuple(
            InputSchemaInventoryRow(
                subject_leaf_key=key,
                required_input_names=tuple(parameter.name for parameter in schema.required_inputs),
                provenance="VerbInputSchema.required_inputs",
            )
            for key, schema in sorted(input_schemas.items())
        ),
        mounted_families=tuple(
            MountedFamilyInventoryRow(
                root=family.root.value,
                child=family.child,
                provenance="OperatorSurfaceContract.command_families",
                unimplemented_reason=family.unimplemented_reason,
            )
            for family in get_operator_surface_contract().command_families
        ),
        profile_policies=tuple(
            ProfilePolicyInventoryRow(
                subject_leaf_key=key,
                classification=(
                    "non_profile_bound"
                    if key in ROOT_LANDING_SCHEMA_KEYS
                    else (
                        "profile_bound_write"
                        if command_execution_policy_for_cli_path(primary_path_by_key[key]).write_route
                        == "profile-bound"
                        else "non_profile_bound"
                    )
                ),
                should_expose_via_mcp=key not in ROOT_LANDING_SCHEMA_KEYS,
                provenance="callback-attached command policy plus root landing exposure contract",
            )
            for key in keys
        ),
        surface_exposures=tuple(
            SurfaceExposureInventoryRow(
                subject_leaf_key=key,
                exposed=is_exposable_command(key),
                provenance="is_exposable_command",
            )
            for key in keys
        ),
        exclusions=tuple(
            exclusion
            for key in sorted(ROOT_LANDING_SCHEMA_KEYS)
            for exclusion in (
                ExplicitExclusionInventoryRow(
                    subject_leaf_key=key,
                    surface=ReconciliationSurface.MOUNTED_FAMILY,
                    reason="root landing callback has no mounted command family",
                    authority="ROOT_LANDING_SCHEMA_KEYS",
                    provenance="entrypoints.schema_surface",
                ),
                ExplicitExclusionInventoryRow(
                    subject_leaf_key=key,
                    surface=ReconciliationSurface.SURFACE_EXPOSURE,
                    reason="root landing callback is excluded from MCP tools",
                    authority="ROOT_LANDING_SCHEMA_KEYS",
                    provenance="entrypoints.schema_surface",
                ),
            )
        ),
    )


def test_live_operator_surface_reconciles_raw_click_paths_callbacks_and_mcp_policy_by_identity() -> None:
    """Reconcile independently walked Click identities with every projection.

    The expected MCP set is assembled from raw terminal paths and callback
    authorities.  It deliberately never calls the MCP adapter's exposure filter:
    a mistaken filter must make descriptor output disagree with this proof.
    """
    raw_terminals, raw_callback_paths, children_by_group = _raw_live_click_surface()
    raw_terminal_path_by_key: dict[str, tuple[str, ...]] = {}
    for path in raw_terminals:
        key = normalise_cli_path_to_schema_key(path)
        prior = raw_terminal_path_by_key.setdefault(key, path)
        assert prior == path, f"two raw terminal Click paths normalised to {key!r}: {prior!r}, {path!r}"

    callback_schema_paths = frozenset(CALLBACK_SCHEMA_KEY_BY_CLI_PATH)
    callback_reuse_paths = frozenset(CALLBACK_RESULT_REUSE_BY_CLI_PATH)
    help_only_callback_paths = frozenset(CALLBACK_EXCLUSION_REASON_BY_CLI_PATH)
    assert raw_callback_paths == callback_schema_paths | callback_reuse_paths | help_only_callback_paths
    assert frozenset(CALLBACK_SCHEMA_KEY_BY_CLI_PATH.values()) == GROUP_CALLBACK_SCHEMA_KEYS
    assert (
        frozenset(key for key in CALLBACK_SCHEMA_KEY_BY_CLI_PATH.values() if key.startswith("root."))
        == ROOT_LANDING_SCHEMA_KEYS
    )

    primary_path_by_key = dict(raw_terminal_path_by_key)
    for callback_path, key in CALLBACK_SCHEMA_KEY_BY_CLI_PATH.items():
        assert key not in primary_path_by_key, f"schema key {key!r} has both raw terminal and callback paths"
        primary_path_by_key[key] = callback_path
    callback_reuse_paths_by_key: dict[str, set[tuple[str, ...]]] = {}
    for callback_path, key in CALLBACK_RESULT_REUSE_BY_CLI_PATH.items():
        assert key in raw_terminal_path_by_key, f"callback reuse key {key!r} has no raw terminal command"
        callback_reuse_paths_by_key.setdefault(key, set()).add(callback_path)

    schema_refs = command_schema_refs()
    registered_keys = frozenset(ref.command for ref in schema_refs)
    assert len(registered_keys) == len(schema_refs), "result-schema registry published a duplicate command identity"
    assert frozenset(primary_path_by_key) == registered_keys, (
        "raw Click surfaces and result-schema registration diverged: "
        f"raw-only={sorted(set(primary_path_by_key) - registered_keys)!r}; "
        f"registry-only={sorted(registered_keys - set(primary_path_by_key))!r}"
    )

    input_schemas = build_verb_input_schemas(tuple(sorted(registered_keys)))
    assert frozenset(input_schemas) == registered_keys
    for key, schema in input_schemas.items():
        assert schema.resolved_leaf.cli_path == primary_path_by_key[key]
        expected_kind = VerbLeafKind.CALLBACK if key in GROUP_CALLBACK_SCHEMA_KEYS else VerbLeafKind.COMMAND
        assert schema.resolved_leaf.kind is expected_kind

    exposable_keys = frozenset(key for key in registered_keys if is_exposable_command(key))
    expected_exposable_keys = (
        frozenset(raw_terminal_path_by_key) | frozenset(CALLBACK_SCHEMA_KEY_BY_CLI_PATH.values())
    ) - ROOT_LANDING_SCHEMA_KEYS
    assert exposable_keys == expected_exposable_keys, (
        "exposable command keys did not equal raw terminal commands plus declared callback schema surfaces: "
        f"missing={sorted(expected_exposable_keys - exposable_keys)!r}; "
        f"unexpected={sorted(exposable_keys - expected_exposable_keys)!r}"
    )

    live_leaves = tuple(
        LiveLeafInventoryRow(
            subject_leaf_key=key,
            canonical_cli_path=primary_path_by_key[key],
            alias_cli_paths=tuple(sorted(callback_reuse_paths_by_key.get(key, set()))),
            provenance="raw materialised Click traversal with declared callback reuse",
        )
        for key in sorted(primary_path_by_key)
    )
    result_schemas = tuple(
        ResultSchemaInventoryRow(
            subject_leaf_key=ref.command,
            schema_name=ref.schema_name,
            provenance="SCHEMA_REGISTRY through command_schema_refs",
        )
        for ref in schema_refs
    )
    input_rows = tuple(
        InputSchemaInventoryRow(
            subject_leaf_key=key,
            required_input_names=tuple(parameter.name for parameter in schema.required_inputs),
            provenance="VerbInputSchema.required_inputs",
        )
        for key, schema in sorted(input_schemas.items())
    )
    mounted_families = tuple(
        MountedFamilyInventoryRow(
            root=family.root.value,
            child=family.child,
            provenance="OperatorSurfaceContract.command_families",
            unimplemented_reason=family.unimplemented_reason,
        )
        for family in get_operator_surface_contract().command_families
    )
    profile_policies = tuple(
        ProfilePolicyInventoryRow(
            subject_leaf_key=key,
            classification=(
                "non_profile_bound"
                if key in ROOT_LANDING_SCHEMA_KEYS
                else (
                    "profile_bound_write"
                    if command_execution_policy_for_cli_path(primary_path_by_key[key]).write_route == "profile-bound"
                    else "non_profile_bound"
                )
            ),
            should_expose_via_mcp=key not in ROOT_LANDING_SCHEMA_KEYS,
            provenance="callback-attached command policy plus root landing exposure contract",
        )
        for key, schema in sorted(input_schemas.items())
    )
    surface_exposures = tuple(
        SurfaceExposureInventoryRow(
            subject_leaf_key=key,
            exposed=key in exposable_keys,
            provenance="is_exposable_command",
        )
        for key in sorted(input_schemas)
    )
    exclusions = tuple(
        exclusion
        for key in sorted(ROOT_LANDING_SCHEMA_KEYS)
        for exclusion in (
            ExplicitExclusionInventoryRow(
                subject_leaf_key=key,
                surface=ReconciliationSurface.MOUNTED_FAMILY,
                reason="root landing callback has no mounted command family",
                authority="ROOT_LANDING_SCHEMA_KEYS",
                provenance="entrypoints.schema_surface",
            ),
            ExplicitExclusionInventoryRow(
                subject_leaf_key=key,
                surface=ReconciliationSurface.SURFACE_EXPOSURE,
                reason="root landing callback is excluded from MCP tools",
                authority="ROOT_LANDING_SCHEMA_KEYS",
                provenance="entrypoints.schema_surface",
            ),
        )
    )

    report = reconcile_operator_surface_inventory(
        live_leaves=live_leaves,
        result_schemas=result_schemas,
        input_schemas=input_rows,
        mounted_families=mounted_families,
        profile_policies=profile_policies,
        surface_exposures=surface_exposures,
        exclusions=exclusions,
    )
    reconciled_by_key = {leaf.live_leaf.subject_leaf_key: leaf for leaf in report.leaves}

    assert frozenset(reconciled_by_key) == registered_keys
    assert frozenset(row.subject_leaf_key for row in profile_policies) == registered_keys
    assert {row.classification for row in profile_policies}.issuperset({"profile_bound_write", "non_profile_bound"})
    reconciled_raw_paths = {
        path
        for row in reconciled_by_key.values()
        for path in (row.live_leaf.canonical_cli_path, *row.live_leaf.alias_cli_paths)
    }
    assert reconciled_raw_paths == (frozenset(raw_terminals) | callback_schema_paths | callback_reuse_paths), (
        "the reconciliation omitted or invented a raw envelope-emitting Click path"
    )

    excluded_from_mcp = frozenset(
        key
        for key, row in reconciled_by_key.items()
        if row.surface_exposure is not None and not row.surface_exposure.exposed
    )
    assert excluded_from_mcp == ROOT_LANDING_SCHEMA_KEYS
    for key in excluded_from_mcp:
        row = reconciled_by_key[key]
        assert {exclusion.surface for exclusion in row.exclusions} == {
            ReconciliationSurface.MOUNTED_FAMILY,
            ReconciliationSurface.SURFACE_EXPOSURE,
        }
        assert row.mounted_family is None
        assert row.profile_policy is not None
        assert row.profile_policy.should_expose_via_mcp is False

    for key in sorted(exposable_keys):
        assert reconciled_by_key[key].result_schema is not None
        assert reconciled_by_key[key].input_schema is not None

    provisioning = next(
        family
        for family in get_operator_surface_contract().command_families
        if family.domain is MountedCommandDomain.PROVISIONING
    )
    assert provisioning.root is RootSurfaceName.CONFIG
    assert provisioning.child == "provision"
    assert provisioning.service_owner == "cadrumo.application.provisioning"
    assert provisioning.mutability is OperatorMutability.LOCAL_STATE_MUTATING
    assert "provision" in provisioning.operator_question.lower()
    assert "readiness" in provisioning.operator_question.lower()
    assert sorted(children_by_group[("config", "provision")]) == sorted(report.commands_for_family(provisioning))


def test_derived_family_membership_equals_the_independently_walked_tree() -> None:
    """Every family's derived verbs equal its live children, for every family.

    The property this replaces was a spot check on one family, which is how the
    contract's hand-written command tuples drifted in both directions while the
    suite stayed green -- verbs the CLI mounted that no family listed, and verbs
    families listed that the CLI does not mount.

    Membership is no longer declared, so the assertion is not "the two lists
    agree" but "the derivation reproduces the tree it was derived from" for
    EVERY family: a grouping bug that silently returned an empty or truncated
    set for some families would otherwise be invisible. The walk here is the
    raw one, independent of the reconciliation's own path projection.
    """
    raw_terminals, _, _ = _raw_live_click_surface()
    report = _live_reconciliation()

    families = get_operator_surface_contract().command_families
    assert families, "the contract declared no families, so this gate would check nothing"

    # A family's verbs are its terminal commands plus the callbacks carrying
    # their OWN schema key. Both corrections matter and pull opposite ways: a
    # terminals-only denominator misses `config repair` and `app ledger
    # participation`, which dispatch from a callback with no leaf entry, while
    # an all-callbacks denominator adds `app diagnostics` (help-only, emits no
    # envelope) and `config profile descendiente` (an alias reusing another
    # leaf's result, so not a command in its own right).
    dispatch_paths = frozenset(raw_terminals) | frozenset(CALLBACK_SCHEMA_KEY_BY_CLI_PATH)
    mismatches: list[str] = []
    for family in families:
        identity = (family.root.value, family.child)
        derived = frozenset(report.commands_for_family(family))
        expected = frozenset(
            ".".join(path[2:]) if len(path) > 2 else family.child
            for path in dispatch_paths
            if len(path) > 1 and (path[0], path[1]) == identity
        )
        if derived != expected:
            mismatches.append(
                f"{' '.join(identity)}: derived-only={sorted(derived - expected)}, "
                f"live-only={sorted(expected - derived)}"
            )
    assert not mismatches, "derived family membership did not reproduce the live tree:\n" + "\n".join(mismatches)
