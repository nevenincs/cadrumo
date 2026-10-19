"""The shared execution-policy vocabulary stays framework-free, complete and custody-bound."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .. import execution_policies
from ..spec import ExecutionPolicySpec

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_every_exported_policy_is_typed_and_validated() -> None:
    policies = {
        name: value
        for name, value in vars(execution_policies).items()
        if name.isupper() and isinstance(value, ExecutionPolicySpec)
    }

    assert policies
    assert {name for name in execution_policies.__all__ if name.isupper()} == set(policies)
    assert all(policy.capabilities and policy.side_effects for policy in policies.values())


def test_policy_module_imports_no_cli_framework() -> None:
    module_path = Path(execution_policies.__file__).resolve()
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    )

    assert imported_roots.isdisjoint({"typer", "click", "pydantic"})


@pytest.mark.parametrize(
    "name",
    [
        "PROFILE_DESTRUCTIVE",
        "ENCRYPTED_WRITE",
        "ENCRYPTED_DESTRUCTIVE",
        "GOOGLE_WRITE",
        "GOOGLE_DESTRUCTIVE",
        "AEAT_SESSION_WRITE",
        "LIVE_PROFILE_WRITE",
    ],
)
def test_profile_bound_policies_explicitly_carry_custody_authority(name: str) -> None:
    policy = getattr(execution_policies, name)

    assert policy.write_route == "profile-bound"
    assert "profile-custody" in policy.capabilities
    assert "local-state" in policy.side_effects


def test_state_free_group_spec_holds_subcommands_without_handler_or_parameters() -> None:
    group = execution_policies.state_free_group_spec("config_google", "config", "google", "cli.config.google.help")

    assert group.kind == "group"
    assert group.policy is execution_policies.STATE_FREE
    assert group.handler is None
    assert group.parameters == ()
    assert group.invocation.no_args_is_help
