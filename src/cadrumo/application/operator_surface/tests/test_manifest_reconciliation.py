"""Pure reconciliation tests for the live operator-surface inventory."""

from __future__ import annotations

from typing import TypedDict

import pytest
from pydantic import ValidationError

from ..errors import OperatorSurfaceContractError
from ..manifest import (
    ExplicitExclusionInventoryRow,
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    MountedFamilyInventoryRow,
    ProfilePolicyInventoryRow,
    ReconciliationSurface,
    ResultSchemaInventoryRow,
    SurfaceExposureInventoryRow,
    reconcile_operator_surface_inventory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _ReconciliationInventory(TypedDict):
    live_leaves: tuple[LiveLeafInventoryRow, ...]
    result_schemas: tuple[ResultSchemaInventoryRow, ...]
    input_schemas: tuple[InputSchemaInventoryRow, ...]
    mounted_families: tuple[MountedFamilyInventoryRow, ...]
    profile_policies: tuple[ProfilePolicyInventoryRow, ...]
    surface_exposures: tuple[SurfaceExposureInventoryRow, ...]
    exclusions: tuple[ExplicitExclusionInventoryRow, ...]


def _complete_inventory() -> _ReconciliationInventory:
    """Return one fully accounted-for real reconciliation input shape."""
    return {
        "live_leaves": (
            LiveLeafInventoryRow(
                subject_leaf_key="app.ledger.list",
                canonical_cli_path=("app", "ledger", "list"),
                alias_cli_paths=(("app", "ledger", "ls"),),
                provenance="resolved Click command tree",
            ),
        ),
        "result_schemas": (
            ResultSchemaInventoryRow(
                subject_leaf_key="app.ledger.list",
                schema_name="LedgerListPayload",
                provenance="COMMAND_GRAPH",
            ),
        ),
        "input_schemas": (
            InputSchemaInventoryRow(
                subject_leaf_key="app.ledger.list",
                required_input_names=("period",),
                provenance="VerbInputSchema",
            ),
        ),
        "mounted_families": (
            MountedFamilyInventoryRow(
                root="app",
                child="ledger",
                provenance="OperatorSurfaceContract.command_families",
            ),
        ),
        "profile_policies": (
            ProfilePolicyInventoryRow(
                subject_leaf_key="app.ledger.list",
                classification="profile_bound_read",
                should_expose_externally=True,
                provenance="profile policy classification",
            ),
        ),
        "surface_exposures": (
            SurfaceExposureInventoryRow(
                subject_leaf_key="app.ledger.list",
                exposed=True,
                provenance="external surface inventory",
            ),
        ),
        "exclusions": (),
    }


def test_reconciliation_joins_all_surfaces_by_subject_and_uses_canonical_family_path() -> None:
    report = reconcile_operator_surface_inventory(**_complete_inventory())

    assert len(report.leaves) == 1
    leaf = report.leaves[0]
    assert leaf.live_leaf.subject_leaf_key == "app.ledger.list"
    assert leaf.live_leaf.alias_cli_paths == (("app", "ledger", "ls"),)
    assert leaf.mounted_family is not None
    assert leaf.mounted_family.identity == ("app", "ledger")
    assert leaf.result_schema is not None
    assert leaf.result_schema.schema_name == "LedgerListPayload"
    assert leaf.input_schema is not None
    assert leaf.input_schema.required_input_names == ("period",)


def test_reconciliation_requires_reasoned_authoritative_external_exclusion() -> None:
    inventory = _complete_inventory()
    inventory["profile_policies"] = (
        ProfilePolicyInventoryRow(
            subject_leaf_key="app.ledger.list",
            classification="operator_only",
            should_expose_externally=False,
            provenance="profile policy classification",
        ),
    )
    inventory["surface_exposures"] = (
        SurfaceExposureInventoryRow(
            subject_leaf_key="app.ledger.list",
            exposed=False,
            provenance="external surface inventory",
        ),
    )

    with pytest.raises(OperatorSurfaceContractError, match="silent external-surface exclusion"):
        reconcile_operator_surface_inventory(**inventory)

    inventory["exclusions"] = (
        ExplicitExclusionInventoryRow(
            subject_leaf_key="app.ledger.list",
            surface=ReconciliationSurface.SURFACE_EXPOSURE,
            reason="operator-only policy class",
            authority="profile-policy ADR",
            provenance="external policy projection",
        ),
    )
    report = reconcile_operator_surface_inventory(**inventory)

    assert report.leaves[0].surface_exposure is not None
    assert report.leaves[0].surface_exposure.exposed is False
    assert report.leaves[0].exclusions[0].authority == "profile-policy ADR"


def test_reconciliation_accounts_for_the_root_status_callback_without_a_mounted_family() -> None:
    inventory = _complete_inventory()
    inventory["live_leaves"] = (
        *inventory["live_leaves"],
        LiveLeafInventoryRow(
            subject_leaf_key="root.status",
            canonical_cli_path=(),
            provenance="S05 root callback inventory",
        ),
    )
    inventory["result_schemas"] = (
        *inventory["result_schemas"],
        ResultSchemaInventoryRow(
            subject_leaf_key="root.status",
            schema_name="RootStatusPayload",
            provenance="COMMAND_GRAPH",
        ),
    )
    inventory["input_schemas"] = (
        *inventory["input_schemas"],
        InputSchemaInventoryRow(
            subject_leaf_key="root.status",
            required_input_names=(),
            provenance="VerbInputSchema",
        ),
    )
    inventory["profile_policies"] = (
        *inventory["profile_policies"],
        ProfilePolicyInventoryRow(
            subject_leaf_key="root.status",
            classification="root_status",
            should_expose_externally=True,
            provenance="profile policy classification",
        ),
    )
    inventory["surface_exposures"] = (
        *inventory["surface_exposures"],
        SurfaceExposureInventoryRow(
            subject_leaf_key="root.status",
            exposed=True,
            provenance="external surface inventory",
        ),
    )
    inventory["exclusions"] = (
        ExplicitExclusionInventoryRow(
            subject_leaf_key="root.status",
            surface=ReconciliationSurface.MOUNTED_FAMILY,
            reason="root callback has no mounted command family",
            authority="operator-surface contract",
            provenance="S05 root callback inventory",
        ),
    )

    report = reconcile_operator_surface_inventory(**inventory)

    root_status = next(leaf for leaf in report.leaves if leaf.live_leaf.subject_leaf_key == "root.status")
    assert root_status.live_leaf.canonical_cli_path == ()
    assert root_status.mounted_family is None


def test_reconciliation_rejects_unmatched_duplicate_and_ambiguous_identities() -> None:
    inventory = _complete_inventory()
    inventory["result_schemas"] = (
        ResultSchemaInventoryRow(
            subject_leaf_key="app.unknown.list",
            schema_name="UnknownPayload",
            provenance="COMMAND_GRAPH",
        ),
    )
    with pytest.raises(OperatorSurfaceContractError, match="unmatched result_schema identity"):
        reconcile_operator_surface_inventory(**inventory)

    inventory = _complete_inventory()
    result_schema = inventory["result_schemas"][0]
    inventory["result_schemas"] = (result_schema, result_schema)
    with pytest.raises(OperatorSurfaceContractError, match="duplicate result_schema identity"):
        reconcile_operator_surface_inventory(**inventory)

    inventory = _complete_inventory()
    first_leaf = inventory["live_leaves"][0]
    assert isinstance(first_leaf, LiveLeafInventoryRow)
    inventory["live_leaves"] = (
        first_leaf,
        LiveLeafInventoryRow(
            subject_leaf_key="app.ledger.other",
            canonical_cli_path=("app", "ledger", "other"),
            alias_cli_paths=(("app", "ledger", "ls"),),
            provenance="resolved Click command tree",
        ),
    )
    with pytest.raises(OperatorSurfaceContractError, match="ambiguous CLI path"):
        reconcile_operator_surface_inventory(**inventory)


def test_reconciliation_rejects_orphan_mounted_family_with_identity_and_provenance() -> None:
    inventory = _complete_inventory()
    inventory["mounted_families"] = (
        *inventory["mounted_families"],
        MountedFamilyInventoryRow(
            root="app",
            child="ghost",
            provenance="unexpected contract declaration",
        ),
    )

    with pytest.raises(OperatorSurfaceContractError, match="orphan mounted family declaration") as exc_info:
        reconcile_operator_surface_inventory(**inventory)

    assert "app ghost" in str(exc_info.value)
    assert "unexpected contract declaration" in str(exc_info.value)


def test_an_absent_family_is_always_an_orphan() -> None:
    """A declaration with no live command family cannot silence reconciliation."""
    inventory = _complete_inventory()
    orphan = MountedFamilyInventoryRow(
        root="config",
        child="ghost",
        provenance="OperatorSurfaceContract.command_families",
    )
    inventory["mounted_families"] = (*inventory["mounted_families"], orphan)
    with pytest.raises(OperatorSurfaceContractError, match="orphan mounted family declaration") as exc_info:
        reconcile_operator_surface_inventory(**inventory)

    assert "config ghost" in str(exc_info.value)


def test_reconciliation_rejects_silent_missing_surface_and_policy_exposure_contradiction() -> None:
    inventory = _complete_inventory()
    inventory["input_schemas"] = ()
    with pytest.raises(OperatorSurfaceContractError, match="missing input_schema accounting"):
        reconcile_operator_surface_inventory(**inventory)

    inventory = _complete_inventory()
    inventory["surface_exposures"] = (
        SurfaceExposureInventoryRow(
            subject_leaf_key="app.ledger.list",
            exposed=False,
            provenance="external surface inventory",
        ),
    )
    inventory["exclusions"] = (
        ExplicitExclusionInventoryRow(
            subject_leaf_key="app.ledger.list",
            surface=ReconciliationSurface.SURFACE_EXPOSURE,
            reason="test policy is intentionally inconsistent",
            authority="test authority",
            provenance="test inventory",
        ),
    )
    with pytest.raises(OperatorSurfaceContractError, match="external exposure contradicts profile policy"):
        reconcile_operator_surface_inventory(**inventory)


def test_reconciliation_rows_are_strict_models() -> None:
    with pytest.raises(ValidationError, match="tuple_type"):
        LiveLeafInventoryRow.model_validate(
            {
                "subject_leaf_key": "app.ledger.list",
                "canonical_cli_path": ["app", "ledger", "list"],
                "provenance": "resolved Click command tree",
            },
        )

    with pytest.raises(ValidationError, match=r"only for root\.status"):
        LiveLeafInventoryRow(
            subject_leaf_key="app.ledger.list",
            canonical_cli_path=(),
            provenance="resolved Click command tree",
        )

    with pytest.raises(ValidationError, match="inventory text must not be blank"):
        ResultSchemaInventoryRow(
            subject_leaf_key="app.ledger.list",
            schema_name="LedgerListPayload",
            provenance=" ",
        )

    with pytest.raises(ValidationError, match="inventory text must not be blank"):
        InputSchemaInventoryRow(
            subject_leaf_key="app.ledger.list",
            provenance=" ",
        )
