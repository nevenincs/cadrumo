"""Real Click-tree identity and typed root write-policy refusal projection."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.main import get_command

from ....adapters.persistence.storage.master_key import close_active_bucket_session
from ....application.storage_write_policy import inspect_storage_write_policy
from ....core.bucket_pointer import pointer_path
from ....core.config import Settings, override_settings
from ....tests.cli_runner import cadrumo_click_command
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile
from ...cli import app
from .._command_suggestions import INVOCATION_REMAINDER_META_KEY
from .._common import (
    RequestedCliLeaf,
    attach_cli_policy_refusal_projection,
    cli_policy_refusal_context,
    cli_policy_refusal_projection,
    current_requested_cli_leaf,
    preserve_requested_cli_leaf,
    project_cli_policy_refusal,
)
from ..errors import CliRefusedBoundaryError, error_boundary_under_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _resolve_real_leaf(*tokens: str) -> RequestedCliLeaf:
    root = get_command(app)
    ctx = typer.Context(root, info_name="aeat")
    ctx.meta[INVOCATION_REMAINDER_META_KEY] = list(tokens)
    try:
        leaf = preserve_requested_cli_leaf(ctx)
    finally:
        ctx.close()
    assert leaf is not None
    return leaf


def test_nested_leaf_identity_is_preserved_before_root_guards() -> None:
    leaf = _resolve_real_leaf("app", "modelo", "work", "calculate", "revision-id")

    assert leaf.canonical_cli_path == ("app", "modelo", "work", "calculate")
    assert leaf.subject_leaf_key == "modelo.work.calculate"


def test_schema_alias_identity_comes_from_the_shared_live_path_projection() -> None:
    leaf = _resolve_real_leaf("config", "profile", "history")

    assert leaf.canonical_cli_path == ("config", "profile", "history")
    assert leaf.subject_leaf_key == "config.bucket.history"


def test_root_fallback_verdict_projects_the_catalogue_action_and_missing_input(tmp_path: Path) -> None:
    leaf = _resolve_real_leaf("app", "modelo", "work", "verify", "revision-id")
    decision = inspect_storage_write_policy(
        "profile-bound",
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )
    assert decision.verdict is not None

    projection = project_cli_policy_refusal(
        requested_leaf=leaf,
        verdict=decision.verdict,
    )
    refusal = attach_cli_policy_refusal_projection(
        CliRefusedBoundaryError(decision.render_refusal_message(locale="en")),
        projection=projection,
    )

    assert projection.requested_leaf is not None
    assert projection.requested_leaf.subject_leaf_key == "modelo.work.verify"
    assert projection.precondition_action.failed_condition_id == "profile.active"
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.model_dump(mode="json") == {
        "action_id": "operator.profile.create",
        "target_command_key": "config.profile.create",
        "cli_path": ["config", "profile", "create"],
    }
    assert projection.precondition_action.missing_argument_names == ("profile_name",)
    assert projection.precondition_action.argument_bindings[0].model_dump(mode="json") == {
        "argument_name": "profile_name",
        "status": "missing",
        "value": None,
        "source": None,
        "source_key": None,
        "source_evidence_id": None,
    }
    assert cli_policy_refusal_projection(refusal) == projection
    assert getattr(refusal, "suggestion", None) is None
    assert getattr(refusal, "context", None) is None


def test_explicit_database_verdict_projects_a_closed_operator_decision(tmp_path: Path) -> None:
    leaf = _resolve_real_leaf("config", "google", "login")
    decision = inspect_storage_write_policy(
        "profile-bound",
        settings=Settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
        ),
    )
    assert decision.verdict is not None

    projection = project_cli_policy_refusal(
        requested_leaf=leaf,
        verdict=decision.verdict,
    )

    assert projection.requested_leaf is not None
    assert projection.requested_leaf.subject_leaf_key == "config.google.login"
    assert projection.precondition_action.failed_condition_id == "storage.route.active_bucket"
    assert projection.precondition_action.action is None
    assert projection.precondition_action.argument_bindings == ()
    assert projection.precondition_action.missing_argument_names == ()
    assert projection.precondition_action.no_recovery_outcome == "operator_decision"
    assert cli_policy_refusal_context(projection) == {
        "explicit_route_setting": "CADRUMO_DATABASE_URL",
        "storage_root_setting": "CADRUMO_LOCAL_STORAGE_ROOT",
    }


def test_real_root_fallback_refusal_attaches_the_typed_projection(tmp_path: Path) -> None:
    """The real root callback, not a manual helper call, owns the handoff."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        error_boundary_under_test(),
        pytest.raises(CliRefusedBoundaryError) as raised,
    ):
        cadrumo_click_command().main(
            args=["app", "modelo", "work", "verify", "revision-id"],
            prog_name="aeat",
            standalone_mode=False,
        )

    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.requested_leaf is not None
    assert projection.requested_leaf.subject_leaf_key == "modelo.work.verify"
    assert projection.precondition_action.failed_condition_id == "profile.active"
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.action_id == "operator.profile.create"


def test_real_explicit_database_refusal_attaches_the_closed_projection(tmp_path: Path) -> None:
    """The actual explicit-route guard attaches the no-recovery decision."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
            cadrumo_active_profile=None,
        ),
        error_boundary_under_test(),
        pytest.raises(CliRefusedBoundaryError) as raised,
    ):
        cadrumo_click_command().main(
            args=["config", "google", "login"],
            prog_name="aeat",
            standalone_mode=False,
        )

    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.requested_leaf is not None
    assert projection.requested_leaf.subject_leaf_key == "config.google.login"
    assert projection.precondition_action.failed_condition_id == "storage.route.active_bucket"
    assert projection.precondition_action.action is None
    assert projection.precondition_action.no_recovery_outcome == "operator_decision"


def test_real_common_guard_projects_profile_create_when_none_are_registered(tmp_path: Path) -> None:
    """A read-shaped leaf reaches the common no-profile producer and keeps its leaf."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        error_boundary_under_test(),
        pytest.raises(CliRefusedBoundaryError) as raised,
    ):
        cadrumo_click_command().main(
            args=["app", "ledger", "list"],
            prog_name="aeat",
            standalone_mode=False,
        )

    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.requested_leaf is not None
    assert projection.requested_leaf.subject_leaf_key == "ledger.list"
    assert projection.precondition_action.failed_condition_id == "profile.active.available"
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.action_id == "operator.profile.create"


def test_real_common_guard_projects_login_when_profiles_are_unselected(tmp_path: Path) -> None:
    """Registered-but-unselected is not collapsed into first-profile creation."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        register_cli_profile(
            label="operator",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "12345678Z",
                "identity.name": "Operator",
                "identity.surnames": "Identity",
                "activities.description": "design",
                "tax_residence.jurisdiction_scope": "common_regime",
            },
        )
        close_active_bucket_session()
        active_pointer = pointer_path(storage_root)
        assert active_pointer.is_file()
        active_pointer.unlink()

        with error_boundary_under_test(), pytest.raises(CliRefusedBoundaryError) as raised:
            cadrumo_click_command().main(
                args=["app", "ledger", "list"],
                prog_name="aeat",
                standalone_mode=False,
            )

    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.requested_leaf is not None
    assert projection.requested_leaf.subject_leaf_key == "ledger.list"
    assert projection.precondition_action.failed_condition_id == "profile.active.available"
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.action_id == "operator.profile.login"
    assert projection.precondition_action.missing_argument_names == ("name",)


@pytest.mark.parametrize(
    ("requested_profile", "condition_id"),
    (
        (" ", "profile.selection.nonblank"),
        ("unknown", "profile.selection.known"),
    ),
)
def test_real_root_profile_override_projects_list_for_unresolved_selection(
    tmp_path: Path,
    requested_profile: str,
    condition_id: str,
) -> None:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        error_boundary_under_test(),
        pytest.raises(CliRefusedBoundaryError) as raised,
    ):
        cadrumo_click_command().main(
            args=["--profile", requested_profile, "app", "ledger", "list"],
            prog_name="aeat",
            standalone_mode=False,
        )

    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.requested_leaf is not None
    assert projection.requested_leaf.subject_leaf_key == "ledger.list"
    assert projection.precondition_action.failed_condition_id == condition_id
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.action_id == "operator.profile.list"


def test_requested_leaf_binding_clears_between_sequential_root_invocations(tmp_path: Path) -> None:
    """A completed root Context cannot donate its leaf to the next refusal."""
    cases = (
        (("app", "ledger", "list"), "ledger.list"),
        (("config", "google", "login"), "config.google.login"),
    )
    with isolated_profile_storage_root(tmp_path=tmp_path):
        for arguments, expected_leaf in cases:
            with error_boundary_under_test(), pytest.raises(CliRefusedBoundaryError) as raised:
                cadrumo_click_command().main(
                    args=list(arguments),
                    prog_name="aeat",
                    standalone_mode=False,
                )

            projection = cli_policy_refusal_projection(raised.value)
            assert projection is not None
            assert projection.requested_leaf is not None
            assert projection.requested_leaf.subject_leaf_key == expected_leaf
            assert current_requested_cli_leaf() is None
