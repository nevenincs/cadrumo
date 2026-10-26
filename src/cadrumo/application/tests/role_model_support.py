"""Shared support naming the synthetic model a test's local runtime holds for a role."""

from __future__ import annotations

from ...core.model_roles import ModelRole


def configured_role_model(role: ModelRole) -> str:
    """Return the synthetic model id a test's local runtime holds for ``role``.

    Cadrumo defines no model: the person selects one per role, and the agent
    service resolves it. A test that serves a local runtime's inventory names
    each role's model with this obviously synthetic id.
    """
    return f"synthetic-{role.value.replace('_', '-')}"
