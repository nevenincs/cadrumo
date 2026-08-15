"""Wiring proof: the persona-scoped tool boundary is enforced by the live server.

``_persona_scope.py`` declares the per-persona ``(family, mutability)`` scope
and the pure predicate ``is_tool_in_persona_scope``; this module proves that
declaration is actually wired into ``_server.py``'s ``_list_tools`` /
``_call_tool`` behaviour, not merely defined and unused. ``_run_server`` is
``# pragma: no cover`` (it blocks on the stdio transport), so the two SDK-side
callbacks are proven indirectly through the SDK-independent functions they
delegate to: :func:`~cadrumo_harness.mcp._server.filter_descriptors_for_persona`
(the ``_list_tools`` half) and
:func:`~cadrumo_harness.mcp._server.persona_scope_refusal` (the ``_call_tool``
half, which the server calls BEFORE ``confirmation_for_tool``).

KNOWN LIMITATION (see ``_persona_scope.py``'s module docstring): the scope is
family-granular. ``modelo-preparer``, ``verifier``, and ``reconciler`` all
declare ``families={"modelo"}``, so this gate cannot structurally distinguish
between them - it cannot, for example, stop the preparer from calling
``modelo.export``. That boundary stays prose-level, not enforced here.
"""

from __future__ import annotations

import pytest

from .._persona_scope import PERSONA_ENV_VAR, AgentPersona, active_persona
from .._server import filter_descriptors_for_persona, persona_scope_refusal
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# --- active_persona() env resolution -----------------------------------------


def test_active_persona_is_none_when_env_var_is_absent() -> None:
    assert active_persona({}) is None


def test_active_persona_is_none_when_env_var_is_blank() -> None:
    assert active_persona({PERSONA_ENV_VAR: ""}) is None
    assert active_persona({PERSONA_ENV_VAR: "   "}) is None


def test_active_persona_resolves_a_declared_member() -> None:
    assert active_persona({PERSONA_ENV_VAR: "cadrumo-verifier"}) is AgentPersona.VERIFIER
    assert active_persona({PERSONA_ENV_VAR: "cadrumo-modelo-preparer"}) is AgentPersona.MODELO_PREPARER


def test_active_persona_raises_instructively_on_an_unrecognised_value() -> None:
    with pytest.raises(ValueError, match=r"not a recognised persona") as exc:
        active_persona({PERSONA_ENV_VAR: "not-a-real-persona"})
    # The accepted set is enumerated in the message per the CLI-boundary
    # instructive-refusal discipline - never a bare "value invalid".
    for member in AgentPersona:
        assert member.value in str(exc.value)


# --- filter_descriptors_for_persona() (the _list_tools half) -----------------


def test_no_active_persona_leaves_the_full_surface_unfiltered() -> None:
    descriptors = build_tool_descriptors()
    scoped = filter_descriptors_for_persona(descriptors, persona=None)
    assert scoped == descriptors


def test_coordinator_tool_list_is_filtered_to_its_declared_families() -> None:
    descriptors = build_tool_descriptors()
    scoped = filter_descriptors_for_persona(descriptors, persona=AgentPersona.COORDINATOR)
    assert 0 < len(scoped) < len(descriptors)
    scoped_keys = {d.command_key for d in scoped}
    # Every scoped tool's family token is one of the coordinator's declared
    # families (overview), never a ledger or modelo verb. The capability
    # manifest it also reads is the MCP-native ``contract`` meta-tool, which
    # carries no command key and is therefore never persona-filtered here.
    assert "ledger.add" not in scoped_keys
    assert "modelo.work.calculate" not in scoped_keys
    assert any(key.startswith("overview.") for key in scoped_keys)


def test_ledger_groomer_tool_list_excludes_modelo_tools() -> None:
    descriptors = build_tool_descriptors()
    scoped = filter_descriptors_for_persona(descriptors, persona=AgentPersona.LEDGER_GROOMER)
    scoped_keys = {d.command_key for d in scoped}
    assert "ledger.add" in scoped_keys
    assert not any(key.startswith("modelo.") for key in scoped_keys)
    assert not any(key.startswith("config.") for key in scoped_keys)


# --- persona_scope_refusal() (the _call_tool half) ----------------------------


def test_unset_persona_never_refuses_on_scope_grounds() -> None:
    assert persona_scope_refusal(persona=None, command_key="ledger.add") is None
    assert persona_scope_refusal(persona=None, command_key="modelo.export") is None


def test_in_scope_call_is_not_refused() -> None:
    assert persona_scope_refusal(persona=AgentPersona.LEDGER_GROOMER, command_key="ledger.add") is None
    assert persona_scope_refusal(persona=AgentPersona.VERIFIER, command_key="modelo.work.verify") is None


def test_out_of_scope_call_is_refused_with_a_structured_message() -> None:
    message = persona_scope_refusal(persona=AgentPersona.COORDINATOR, command_key="ledger.add")
    assert message is not None
    assert "refused" in message
    assert "ledger.add" in message
    assert "cadrumo-coordinator" in message


def test_coordinator_cannot_call_a_mutating_ledger_or_modelo_tool() -> None:
    # The coordinator's declared ceiling is READ_ONLY over {overview, contract}
    # only - it must be refused for every mutating family, proving the gate
    # enforces both the family AND the mutability-ceiling axis end to end.
    # Each refusal is pinned to its OWN command_key, not just truthiness --
    # a generic or copy-pasted refusal shared across the three calls would
    # still pass under bare ``is not None``.
    ledger_add = persona_scope_refusal(persona=AgentPersona.COORDINATOR, command_key="ledger.add")
    assert ledger_add is not None and "ledger.add" in ledger_add and "cadrumo-coordinator" in ledger_add
    modelo_calculate = persona_scope_refusal(persona=AgentPersona.COORDINATOR, command_key="modelo.work.calculate")
    assert modelo_calculate is not None and "modelo.work.calculate" in modelo_calculate
    modelo_export = persona_scope_refusal(persona=AgentPersona.COORDINATOR, command_key="modelo.export")
    assert modelo_export is not None and "modelo.export" in modelo_export


def test_ledger_groomer_cannot_call_a_modelo_tool() -> None:
    modelo_calculate = persona_scope_refusal(persona=AgentPersona.LEDGER_GROOMER, command_key="modelo.work.calculate")
    assert modelo_calculate is not None and "modelo.work.calculate" in modelo_calculate
    modelo_export = persona_scope_refusal(persona=AgentPersona.LEDGER_GROOMER, command_key="modelo.export")
    assert modelo_export is not None and "modelo.export" in modelo_export


# --- documented family-granularity limitation ---------------------------------


def test_modelo_lifecycle_personas_are_not_distinguished_by_this_gate() -> None:
    # This is the honestly-documented limitation, pinned as a regression test
    # rather than left as prose alone: modelo-preparer, verifier, and
    # reconciler all share families={"modelo"}, so none of them is refused
    # from any other's verb by this gate. If a future manifest split narrows
    # the family boundary, this test should start failing and must be
    # revisited (it would then be provable, and should be tightened).
    for persona in (AgentPersona.MODELO_PREPARER, AgentPersona.VERIFIER, AgentPersona.RECONCILER):
        assert persona_scope_refusal(persona=persona, command_key="modelo.export") is None
        assert persona_scope_refusal(persona=persona, command_key="modelo.work.create") is None
        assert persona_scope_refusal(persona=persona, command_key="modelo.work.verify") is None
