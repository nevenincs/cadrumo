"""Pinning tests for the persona-scoped tool boundary.

The persona -> ``(family, mutability)`` declaration in ``_persona_scope.py``
is not itself the source of truth - the live operator-surface manifest is.
These tests assert every declared persona scope still RESOLVES against the
live manifest, so a manifest change (a family renamed, retired, or its
mutability changed) fails here loudly instead of silently widening or
narrowing a stale persona boundary.

Every family named below already exists on the live manifest at HEAD (verified
by ``test_every_declared_family_resolves_against_the_live_manifest``), so no
persona scope is pending today. If a future persona document names a family
the manifest does not yet expose, that gap must be visible as a named,
commented pending item in ``_persona_scope.py`` (never a bare
``xfail``/``skip``) and this test module must assert against the FAMILIES THE
CONTRACT CURRENTLY EXPOSES, carving the pending family out explicitly with a
comment - not weakening the assertion for every family.
"""

from __future__ import annotations

import pytest

from cadrumo.application.operator_surface import OperatorMutability

from .._persona_scope import (
    PERSONA_TOOL_SCOPES,
    AgentPersona,
    is_handoff_denied,
    is_tool_in_persona_scope,
    live_family_mutability,
    scope_for_persona,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_persona_has_exactly_one_declared_scope() -> None:
    declared = {scope.persona for scope in PERSONA_TOOL_SCOPES}
    assert declared == set(AgentPersona)
    assert len(PERSONA_TOOL_SCOPES) == len(AgentPersona)


def test_every_declared_family_resolves_against_the_live_manifest() -> None:
    """Every persona-scoped family child token exists as a live mounted family.

    This is the D1 pinning proof: a manifest edit that renames or retires a
    family this module names fails here, not silently at runtime.
    """
    live_families = live_family_mutability()
    for scope in PERSONA_TOOL_SCOPES:
        for family_token in scope.families:
            assert family_token in live_families, (
                f"{scope.persona}: declared family {family_token!r} is absent from the "
                "live manifest - update the persona scope or the persona document"
            )


def test_declared_family_mutability_never_exceeds_its_own_ceiling() -> None:
    """A persona must never declare a family whose live mutability it cannot reach.

    Catches the self-contradictory declaration where a family is granted but
    the ceiling would refuse every call to it - a dead grant that
    ``is_tool_in_persona_scope`` would silently never satisfy.
    """
    live_families = live_family_mutability()
    rank = {OperatorMutability.READ_ONLY: 0, OperatorMutability.LOCAL_STATE_MUTATING: 1}
    for scope in PERSONA_TOOL_SCOPES:
        for family_token in scope.families:
            family_mutability = live_families[family_token]
            assert rank[family_mutability] <= rank[scope.mutability_ceiling], (
                f"{scope.persona}: family {family_token!r} is {family_mutability} but the "
                f"declared ceiling is {scope.mutability_ceiling} - every call to it would "
                "be refused"
            )


def test_coordinator_holds_no_mutating_family() -> None:
    """Per D1: the coordinator delegates every mutating step and mutates nothing itself."""
    scope = scope_for_persona(AgentPersona.COORDINATOR)
    assert scope.mutability_ceiling is OperatorMutability.READ_ONLY
    live_families = live_family_mutability()
    for family_token in scope.families:
        assert live_families[family_token] is OperatorMutability.READ_ONLY, (
            f"coordinator scope grants mutating family {family_token!r}"
        )


def test_coordinator_is_confined_to_orchestration_reads() -> None:
    assert scope_for_persona(AgentPersona.COORDINATOR).families == {"overview"}


def test_onboarding_scope_excludes_ledger_and_modelo() -> None:
    scope = scope_for_persona(AgentPersona.ONBOARDING)
    assert "ledger" not in scope.families
    assert "modelo" not in scope.families
    assert "live" not in scope.families


def test_ledger_personas_are_confined_to_the_ledger_family() -> None:
    for persona in (AgentPersona.LEDGER_GROOMER, AgentPersona.CLASSIFIER):
        scope = scope_for_persona(persona)
        assert scope.families == {"ledger"}
        assert "modelo" not in scope.families


def test_modelo_lifecycle_personas_are_confined_to_the_modelo_family() -> None:
    for persona in (AgentPersona.MODELO_PREPARER, AgentPersona.VERIFIER, AgentPersona.RECONCILER):
        scope = scope_for_persona(persona)
        assert scope.families == {"modelo"}
        assert "ledger" not in scope.families
        assert "live" not in scope.families


def test_no_persona_is_granted_the_live_aeat_family() -> None:
    # Per every persona document's "What you do not do": no role touches the
    # live AEAT read tree directly; the reconciler pulls official evidence
    # through `modelo reconcile`, not the `live` family.
    for scope in PERSONA_TOOL_SCOPES:
        assert "live" not in scope.families


def test_is_tool_in_persona_scope_allows_declared_family_commands() -> None:
    assert is_tool_in_persona_scope(persona=AgentPersona.COORDINATOR, command_key="overview.status") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.COORDINATOR, command_key="overview.status") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.ONBOARDING, command_key="config.profile.create") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.ONBOARDING, command_key="config.auth.configure") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.LEDGER_GROOMER, command_key="ledger.add") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.CLASSIFIER, command_key="ledger.classify") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.MODELO_PREPARER, command_key="modelo.work.calculate") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.VERIFIER, command_key="modelo.work.verify") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.VERIFIER, command_key="modelo.export") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.RECONCILER, command_key="modelo.reconcile.pull") is True
    assert is_tool_in_persona_scope(persona=AgentPersona.RECONCILER, command_key="modelo.reconcile.history") is True


def test_is_tool_in_persona_scope_refuses_out_of_family_commands() -> None:
    # The coordinator never issues a mutating verb directly.
    assert is_tool_in_persona_scope(persona=AgentPersona.COORDINATOR, command_key="ledger.add") is False
    assert is_tool_in_persona_scope(persona=AgentPersona.COORDINATOR, command_key="modelo.work.calculate") is False
    # Onboarding never touches the ledger or modelo families.
    assert is_tool_in_persona_scope(persona=AgentPersona.ONBOARDING, command_key="ledger.add") is False
    assert is_tool_in_persona_scope(persona=AgentPersona.ONBOARDING, command_key="modelo.work.create") is False
    # The bookkeeper and classifier never prepare a modelo.
    assert is_tool_in_persona_scope(persona=AgentPersona.LEDGER_GROOMER, command_key="modelo.work.calculate") is False
    assert is_tool_in_persona_scope(persona=AgentPersona.CLASSIFIER, command_key="modelo.export") is False
    # The modelo-preparer never touches custody, auth, or the ledger.
    assert is_tool_in_persona_scope(persona=AgentPersona.MODELO_PREPARER, command_key="config.profile.create") is False
    assert is_tool_in_persona_scope(persona=AgentPersona.MODELO_PREPARER, command_key="ledger.add") is False
    # No persona is ever granted the live AEAT read tree.
    for persona in AgentPersona:
        assert is_tool_in_persona_scope(persona=persona, command_key="app.live.justificante.pull") is False


def test_is_tool_in_persona_scope_fails_closed_on_an_unknown_family() -> None:
    # A command key whose family is neither declared for the persona nor
    # mounted on the live manifest is refused, never treated as in scope.
    assert is_tool_in_persona_scope(persona=AgentPersona.COORDINATOR, command_key="not_a_real_family.status") is False
    # The same family is genuinely absent from the live manifest today, which
    # is what would trigger the "granted but unmounted" fail-closed branch in
    # `is_tool_in_persona_scope` if a persona ever declared it.
    assert "not_a_real_family" not in live_family_mutability()


def test_handoff_denial_fires_for_the_modelo_filing_leaves() -> None:
    # The R6(iii) irreversible-boundary denial: the modelo-preparer and the
    # reconciler are structurally barred from the modelo export and record marker.
    for persona in (AgentPersona.MODELO_PREPARER, AgentPersona.RECONCILER):
        assert is_handoff_denied(persona=persona, command_key="modelo.export") is True
        assert is_handoff_denied(persona=persona, command_key="modelo.work.file") is True
    # The verifier owns the handoff and is never denied it.
    assert is_handoff_denied(persona=AgentPersona.VERIFIER, command_key="modelo.export") is False


def test_handoff_denial_is_scoped_to_the_modelo_family_not_any_export_leaf() -> None:
    # Precision guard: the deny rule matches the modelo filing boundary, not a
    # same-named `export` / `file` leaf in another family. A future
    # ledger-exporting verb (`ledger.export`) must NOT trip a spurious refusal
    # for a modelo persona — the family guard keeps the rule exact rather than
    # relying on persona scope to mask the bare leaf-name match.
    assert is_handoff_denied(persona=AgentPersona.MODELO_PREPARER, command_key="ledger.export") is False
    assert is_handoff_denied(persona=AgentPersona.RECONCILER, command_key="app.ledger.file") is False
    # A persona with no denial rows is never denied anything.
    assert is_handoff_denied(persona=AgentPersona.VERIFIER, command_key="ledger.export") is False
