"""Prove the Modelo action denominator genuinely reds on drift.

This is the anti-vacuity proof for
``dev/quality/modelo_workspace_action_denominator.py``: the closed
classification table is real production data (78 live Modelo commands), so
these tests build REAL denominator instances from the real table and mutate
exactly one fact to prove each rejection path, never a stub or a hand-rolled
double.
"""

from __future__ import annotations

import pytest

from ..quality.modelo_workspace_action_denominator import (
    MODELO_ACTION_CLASSIFICATIONS,
    SCHEMA_VERSION,
    ModeloWorkspaceActionClassificationV1,
    ModeloWorkspaceActionDenominatorV1,
    ModeloWorkspaceActionDisposition,
    build_modelo_workspace_action_denominator,
    discover_live_modelo_action_signatures,
    validate_modelo_workspace_action_denominator,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_current_head_denominator_is_green() -> None:
    denominator = build_modelo_workspace_action_denominator()
    assert validate_modelo_workspace_action_denominator(denominator) == []


def test_every_live_candidate_is_classified_never_omitted() -> None:
    live = discover_live_modelo_action_signatures()
    assert set(live) == set(MODELO_ACTION_CLASSIFICATIONS)
    assert len(live) > 0


def test_unclassified_action_candidate_reds() -> None:
    truncated = {
        identity: classification
        for identity, classification in MODELO_ACTION_CLASSIFICATIONS.items()
        if identity != "modelo.work.review"
    }
    denominator = ModeloWorkspaceActionDenominatorV1(
        schema_version=SCHEMA_VERSION,
        live_action_identities=tuple(sorted(discover_live_modelo_action_signatures())),
        classifications=truncated,
    )
    violations = validate_modelo_workspace_action_denominator(denominator)
    assert any("unclassified action candidate" in message and "modelo.work.review" in message for message in violations)


def test_stale_classification_for_action_no_longer_live_reds() -> None:
    phantom = ModeloWorkspaceActionClassificationV1(
        action_identity="modelo.work.phantom_action",
        disposition=ModeloWorkspaceActionDisposition.DEFERRED,
        command_key="app_modelo_work_phantom_action",
        write_route="none",
        side_effects=("none",),
        has_action_catalogue_entry=False,
        owning_authority="test-fixture",
        reason="a fabricated stale row proving the stale-entry rejection path",
        evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
        reopening_condition="never: this row exists only to prove a rejection path",
    )
    augmented = {**MODELO_ACTION_CLASSIFICATIONS, "modelo.work.phantom_action": phantom}
    denominator = ModeloWorkspaceActionDenominatorV1(
        schema_version=SCHEMA_VERSION,
        live_action_identities=tuple(sorted(discover_live_modelo_action_signatures())),
        classifications=augmented,
    )
    violations = validate_modelo_workspace_action_denominator(denominator)
    assert any("stale classification" in message and "modelo.work.phantom_action" in message for message in violations)


def test_drifted_write_route_signature_reds() -> None:
    real = MODELO_ACTION_CLASSIFICATIONS["modelo.work.review"]
    assert real.write_route == "none"
    drifted = real.model_copy(update={"write_route": "profile-bound"})
    augmented = {**MODELO_ACTION_CLASSIFICATIONS, "modelo.work.review": drifted}
    denominator = ModeloWorkspaceActionDenominatorV1(
        schema_version=SCHEMA_VERSION,
        live_action_identities=tuple(sorted(discover_live_modelo_action_signatures())),
        classifications=augmented,
    )
    violations = validate_modelo_workspace_action_denominator(denominator)
    assert any(
        "drifted signature" in message and "modelo.work.review" in message and "write_route" in message
        for message in violations
    )


def test_drifted_command_key_signature_reds() -> None:
    real = MODELO_ACTION_CLASSIFICATIONS["modelo.work.calculate"]
    drifted = real.model_copy(update={"command_key": "app_modelo_work_calculate_renamed"})
    augmented = {**MODELO_ACTION_CLASSIFICATIONS, "modelo.work.calculate": drifted}
    denominator = ModeloWorkspaceActionDenominatorV1(
        schema_version=SCHEMA_VERSION,
        live_action_identities=tuple(sorted(discover_live_modelo_action_signatures())),
        classifications=augmented,
    )
    violations = validate_modelo_workspace_action_denominator(denominator)
    assert any(
        "drifted signature" in message and "modelo.work.calculate" in message and "command_key" in message
        for message in violations
    )


def test_placeholder_reason_is_refused_at_construction() -> None:
    with pytest.raises(Exception, match="real, bounded reason"):
        ModeloWorkspaceActionClassificationV1(
            action_identity="modelo.work.review",
            disposition=ModeloWorkspaceActionDisposition.C1_BOUNDED_REVIEW,
            command_key="app_modelo_work_review",
            write_route="none",
            side_effects=("none",),
            has_action_catalogue_entry=False,
            owning_authority="tui-architecture",
            reason="n/a",
            evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
            reopening_condition="never",
        )


def test_out_of_scope_identity_is_refused_at_construction() -> None:
    with pytest.raises(Exception, match="outside the Modelo action denominator"):
        ModeloWorkspaceActionClassificationV1(
            action_identity="config.auth.login",
            disposition=ModeloWorkspaceActionDisposition.DEFERRED,
            command_key="config_auth_login",
            write_route="none",
            side_effects=("none",),
            has_action_catalogue_entry=False,
            owning_authority="test-fixture",
            reason="proving the out-of-scope refusal",
            evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
            reopening_condition="never",
        )


def test_two_named_judgement_call_dispositions_are_recorded_correctly() -> None:
    """`modelo.work.create` and the wizard commands are the two hand-authored calls."""
    assert MODELO_ACTION_CLASSIFICATIONS["modelo.work.create"].disposition is ModeloWorkspaceActionDisposition.DEFERRED
    assert (
        MODELO_ACTION_CLASSIFICATIONS["modelo.work.amend_wizard"].disposition
        is ModeloWorkspaceActionDisposition.FLOW_OWNED
    )
    assert (
        MODELO_ACTION_CLASSIFICATIONS["modelo.work.amend"].disposition
        is ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING
    )
    assert (
        MODELO_ACTION_CLASSIFICATIONS["modelo.work.review"].disposition
        is ModeloWorkspaceActionDisposition.C1_BOUNDED_REVIEW
    )
