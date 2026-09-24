"""Every context that builds an MCP server serves composed adapter ports."""

from __future__ import annotations

from contextvars import Context

import pytest

from cadrumo.application.user_profile.custody_ports import profile_custody_port
from cadrumo.core.errors.hierarchy import InternalInvariantError

from .. import server as server_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _custody_is_composed() -> bool:
    try:
        profile_custody_port()
    except InternalInvariantError:
        return False
    return True


def _compose_and_observe() -> bool:
    server_module._ensure_adapter_composition()
    return _custody_is_composed()


def test_a_context_that_never_saw_an_earlier_binding_composes_its_own() -> None:
    """A binding made in one context does not stop another from binding.

    The in-process transport builds each server inside a task, so a binding is
    visible to that task alone. Two fresh contexts stand for two such servers:
    the second must not take the first one's binding as its own.
    """
    assert not Context().run(_custody_is_composed), "a fresh context must start uncomposed"

    assert Context().run(_compose_and_observe)
    assert Context().run(_compose_and_observe)


def test_composing_again_where_the_binding_is_visible_is_a_no_op() -> None:
    """Within one context the composition is entered once, not once per server."""

    def bound_port_across_two_builds() -> tuple[object, object]:
        server_module._ensure_adapter_composition()
        first = profile_custody_port()
        server_module._ensure_adapter_composition()
        return first, profile_custody_port()

    first, second = Context().run(bound_port_across_two_builds)

    assert first is second
