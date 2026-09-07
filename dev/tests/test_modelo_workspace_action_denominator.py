"""Prove the Modelo action denominator genuinely reds on drift.

This is the anti-vacuity proof for
``dev/quality/modelo_workspace_action_denominator.py``: the closed
classification table is real production data (79 live Modelo commands), so
these tests build REAL denominator instances from the real table and mutate
exactly one fact to prove each rejection path, never a stub or a hand-rolled
double.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.entrypoints.cli.command_spec import TuiCapability

from ..quality.modelo_workspace_action_classification import (
    ModeloWorkspaceActionClassificationV1,
    ModeloWorkspaceActionDisposition,
)
from ..quality.modelo_workspace_action_classification_table import MODELO_ACTION_CLASSIFICATIONS
from ..quality.modelo_workspace_action_denominator import (
    SCHEMA_VERSION,
    ModeloWorkspaceActionDenominatorV1,
    build_modelo_workspace_action_denominator,
    discover_dispatchable_modelo_action_identities,
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
    # The equality above catches a ONE-SIDED collapse: discovery returning
    # nothing no longer matches a populated table. It cannot catch the two
    # sides shrinking together, which is what happens when discovery narrows
    # and the table is trimmed to make this pass. `> 0` allowed that down to
    # a single surviving action. A floor, not a pinned count: live the
    # denominator holds 79 classified action signatures.
    assert len(live) > 60, (
        f"the modelo action denominator has fallen to {len(live)} signatures, so the "
        "classification coverage below is measured over a fraction of the surface"
    )


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
        tui_capability=TuiCapability.NOT_IMPLEMENTED,
        is_surface_dispatchable=False,
        owning_authority="test-fixture",
        reason="a fabricated stale row proving the stale-entry rejection path",
        evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
        reopening_condition="reopens only if a future accepted decision moves this into scope",
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
    # `Exception` accepted a TypeError from a wrong keyword just as readily
    # as the model's own refusal, so the validation under test could stop
    # running without this case noticing.
    with pytest.raises(ValidationError, match="real, bounded reason"):
        ModeloWorkspaceActionClassificationV1(
            action_identity="modelo.work.review",
            disposition=ModeloWorkspaceActionDisposition.C1_BOUNDED_REVIEW,
            command_key="app_modelo_work_review",
            write_route="none",
            side_effects=("none",),
            has_action_catalogue_entry=False,
            tui_capability=TuiCapability.NOT_IMPLEMENTED,
            is_surface_dispatchable=False,
            owning_authority="tui-architecture",
            reason="n/a",
            evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
            reopening_condition="never reopens: terminal C1 disposition",
        )


def test_out_of_scope_identity_is_refused_at_construction() -> None:
    with pytest.raises(ValidationError, match="outside the Modelo action denominator"):
        ModeloWorkspaceActionClassificationV1(
            action_identity="config.auth.login",
            disposition=ModeloWorkspaceActionDisposition.DEFERRED,
            command_key="config_auth_login",
            write_route="none",
            side_effects=("none",),
            has_action_catalogue_entry=False,
            tui_capability=TuiCapability.NOT_IMPLEMENTED,
            is_surface_dispatchable=False,
            owning_authority="test-fixture",
            reason="proving the out-of-scope refusal",
            evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
            reopening_condition="reopens only if a future accepted decision moves this into scope",
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


def test_the_dispatch_stream_and_the_command_graph_stream_have_different_denominators() -> None:
    """The two candidate streams are not the same set, and the check must not assume they are.

    The classification table is keyed to command-graph candidates; the
    dispatch table is keyed to registered operations. Recorded as a test
    rather than a comment because a future change that made them coincide
    would silently widen the enforceable rule below.
    """
    dispatchable = discover_dispatchable_modelo_action_identities()
    live = set(discover_live_modelo_action_signatures())

    assert dispatchable, "no dispatchable actions were discovered; the proofs below would be vacuous"
    assert dispatchable - live, (
        "every dispatchable action is now also a command-graph candidate; the denominators have "
        "converged and the intersection-only rule should be widened deliberately rather than by accident"
    )


def test_a_dispatchable_command_graph_action_missing_from_the_table_is_refused() -> None:
    """Anti-tautology: prove the dispatch rule fires when its subject is removed.

    Driven through the validator's own injectable classification table, so
    nothing on disk is mutated -- this worktree is shared and a broad landing
    commit could otherwise capture a deliberately broken table.
    """
    denominator = build_modelo_workspace_action_denominator()
    both = discover_dispatchable_modelo_action_identities() & set(discover_live_modelo_action_signatures())
    subject = sorted(both)[0]
    trimmed = {key: row for key, row in denominator.classifications.items() if key != subject}

    errors = validate_modelo_workspace_action_denominator(denominator.model_copy(update={"classifications": trimmed}))

    assert any("dispatchable from a surface" in error and subject in error for error in errors), (
        f"removing {subject!r} from the table did not raise the dispatch violation: {errors}"
    )


def test_the_taxonomy_offers_an_arm_a_delivered_mutation_can_occupy() -> None:
    """The delivered arms accept a wired row, which the pending-only taxonomy could not.

    Before the delivered arms existed, an action whose surface had shipped had
    nowhere in the closed taxonomy to say so and stayed recorded as pending.
    This proves the arms are occupiable by a row carrying the observed shape of
    a wired action -- available routing posture and surface dispatchability --
    rather than merely present in the enumeration.
    """
    for disposition in (
        ModeloWorkspaceActionDisposition.READ_DELIVERED,
        ModeloWorkspaceActionDisposition.MUTATION_DELIVERED,
    ):
        row = ModeloWorkspaceActionClassificationV1(
            action_identity="modelo.work.review",
            disposition=disposition,
            command_key="app_modelo_work_review",
            write_route="none",
            side_effects=("none",),
            has_action_catalogue_entry=False,
            tui_capability=TuiCapability.AVAILABLE,
            is_surface_dispatchable=True,
            owning_authority="test-fixture",
            reason="proving the delivered arm accepts a wired row",
            evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
            reopening_condition=(
                "reopens once the C3/C4 conformance suites are green and this is "
                "enrolled as a C4 action"
            ),
        )
        assert row.disposition is disposition
        assert row.tui_capability is TuiCapability.AVAILABLE
        assert row.is_surface_dispatchable


def _contradiction(
    *, capability: TuiCapability, dispatchable: bool, disposition: ModeloWorkspaceActionDisposition
) -> str | None:
    """Drive the pure contradiction helper across one quadrant."""
    from ..quality.modelo_workspace_action_denominator import _disposition_contradiction

    def row(recorded_disposition: ModeloWorkspaceActionDisposition) -> ModeloWorkspaceActionClassificationV1:
        return ModeloWorkspaceActionClassificationV1(
            action_identity="modelo.work.file",
            disposition=recorded_disposition,
            command_key="app_modelo_work_file",
            write_route="profile-bound",
            side_effects=("local-state",),
            has_action_catalogue_entry=False,
            tui_capability=capability,
            is_surface_dispatchable=dispatchable,
            owning_authority="test-fixture",
            reason="driving one quadrant of the contradiction rule",
            evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
            reopening_condition=(
                "reopens once the C3/C4 conformance suites are green and this is "
                "enrolled as a C4 action"
            ),
        )

    return _disposition_contradiction(row(ModeloWorkspaceActionDisposition.NOT_VISUAL), row(disposition))


def test_a_wired_mutation_recorded_as_pending_is_contradicted() -> None:
    """Teeth for the stale-pending arm: shipping a surface must not leave the row pending."""
    message = _contradiction(
        capability=TuiCapability.AVAILABLE,
        dispatchable=True,
        disposition=ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
    )

    assert message is not None
    assert "recorded as a pending mutation" in message


def test_an_available_but_undispatchable_mutation_is_not_contradicted() -> None:
    """The negative control that makes the conjunction non-arbitrary.

    A declared routing posture alone is NOT delivery. Were the predicate a
    disjunction this quadrant would red, and every action carrying an
    available posture with no dispatch entry would be pushed toward a
    delivered label it has not earned.
    """
    assert (
        _contradiction(
            capability=TuiCapability.AVAILABLE,
            dispatchable=False,
            disposition=ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
        )
        is None
    )


def test_a_delivered_mutation_claim_inside_the_intersection_is_contradicted() -> None:
    """A dispatchable row claiming delivery while its posture says otherwise reds."""
    denominator = build_modelo_workspace_action_denominator()
    subject = "modelo.export"
    claimed = denominator.classifications[subject].model_copy(
        update={"disposition": ModeloWorkspaceActionDisposition.MUTATION_DELIVERED},
    )
    table = {**denominator.classifications, subject: claimed}

    errors = validate_modelo_workspace_action_denominator(
        denominator.model_copy(update={"classifications": table}),
    )

    assert any("contradicted disposition" in error and subject in error for error in errors), errors
    assert not any("drifted signature" in error and subject in error for error in errors), (
        f"the contradiction must not be reported as signature drift: {errors}"
    )


def test_a_delivered_mutation_claim_outside_the_intersection_is_contradicted() -> None:
    """The load-bearing proof that the false-delivery arm is not intersection-scoped.

    A row claiming delivery while dispatchable by nothing sits OUTSIDE the
    command-graph and dispatch intersection by construction. Scoping this arm
    to the intersection would exclude from the rule exactly the input the rule
    exists to catch, so this case is what proves the escape hatch is closed.
    """
    denominator = build_modelo_workspace_action_denominator()
    subject = "modelo.work.calculate"
    assert not denominator.classifications[subject].is_surface_dispatchable, (
        f"{subject} must be undispatchable for this proof to mean anything"
    )
    claimed = denominator.classifications[subject].model_copy(
        update={"disposition": ModeloWorkspaceActionDisposition.MUTATION_DELIVERED},
    )
    table = {**denominator.classifications, subject: claimed}

    errors = validate_modelo_workspace_action_denominator(
        denominator.model_copy(update={"classifications": table}),
    )

    assert any("contradicted disposition" in error and subject in error for error in errors), errors
    assert not any("drifted signature" in error and subject in error for error in errors), errors


def test_a_delivered_read_claim_is_refused_until_read_routing_is_observable() -> None:
    """The read arm fails closed rather than being judged against a mutation fact."""
    denominator = build_modelo_workspace_action_denominator()
    subject = "modelo.work.review"
    claimed = denominator.classifications[subject].model_copy(
        update={"disposition": ModeloWorkspaceActionDisposition.READ_DELIVERED},
    )
    table = {**denominator.classifications, subject: claimed}

    errors = validate_modelo_workspace_action_denominator(
        denominator.model_copy(update={"classifications": table}),
    )

    assert any("not yet observable" in error and subject in error for error in errors), errors


def test_a_reopening_condition_from_another_arm_is_refused_at_construction() -> None:
    """Teeth for the arm-coherence rule, using the defect that motivated it.

    A row reclassified from read to mutation once kept the read arm's
    reopening condition, so it was scheduled behind the read migration while
    recorded as a mutation. Nothing detected it, because only the reason was
    validated. This proves the contradiction is now refused where it is
    written rather than surviving until someone counts arms against
    conditions.
    """
    with pytest.raises(ValidationError, match="belongs to a different disposition"):
        ModeloWorkspaceActionClassificationV1(
            action_identity="modelo.review_package.encrypt_for_recipient",
            disposition=ModeloWorkspaceActionDisposition.C4_MUTATION_PENDING,
            command_key="app_modelo_review_package_encrypt_for_recipient",
            write_route="profile-bound",
            side_effects=("local-state",),
            has_action_catalogue_entry=False,
            tui_capability=TuiCapability.NOT_IMPLEMENTED,
            is_surface_dispatchable=False,
            owning_authority="test-fixture",
            reason="a mutation row carrying the read arm's reopening condition",
            evidence_reference="dev/tests/test_modelo_workspace_action_denominator.py",
            reopening_condition="reopens on migration to a numbered C1/C2 destination in the same commit",
        )


def test_every_recorded_row_carries_the_reopening_condition_of_its_own_arm() -> None:
    """The whole table satisfies the rule, so the teeth above bite a real invariant."""
    conditions_by_arm: dict[ModeloWorkspaceActionDisposition, set[str]] = {}
    for row in MODELO_ACTION_CLASSIFICATIONS.values():
        conditions_by_arm.setdefault(row.disposition, set()).add(row.reopening_condition)

    inconsistent = {arm: sorted(conditions) for arm, conditions in conditions_by_arm.items() if len(conditions) > 1}
    assert not inconsistent, f"an arm carries more than one reopening condition: {inconsistent}"
