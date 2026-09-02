"""Config command-spec policy authority stays framework-free and complete."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...command_spec import ExecutionPolicySpec
from .. import _spec_policies

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_every_exported_spec_policy_is_typed_and_validated() -> None:
    policies = {
        name: value
        for name, value in vars(_spec_policies).items()
        if name.isupper() and isinstance(value, ExecutionPolicySpec)
    }

    assert policies
    assert set(_spec_policies.__all__) == set(policies)
    assert all(policy.capabilities and policy.side_effects for policy in policies.values())


def test_config_spec_policy_module_imports_no_cli_framework() -> None:
    module_path = Path(_spec_policies.__file__).resolve()
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
        "PROFILE_WRITE",
        "PROFILE_DESTRUCTIVE",
        "ENCRYPTED_WRITE",
        "ENCRYPTED_DESTRUCTIVE",
        "GOOGLE_WRITE",
        "GOOGLE_DESTRUCTIVE",
        "GOOGLE_HANDOFF",
        "CALCULATION_WRITE",
        "GOOGLE_CALCULATION_WRITE",
        "GOOGLE_CALCULATION_HANDOFF",
        "LIVE_PROFILE_WRITE",
    ],
)
def test_profile_bound_policies_explicitly_carry_custody_authority(name: str) -> None:
    policy = getattr(_spec_policies, name)

    assert policy.write_route == "profile-bound"
    assert "profile-custody" in policy.capabilities
    assert "local-state" in policy.side_effects
