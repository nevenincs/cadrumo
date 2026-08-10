"""Real contract tests for the canonical operator action catalogue."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from .._catalogue import (
    OPERATOR_ACTION_CATALOGUE,
    ActionArgumentBindingSpecification,
    ActionCatalogue,
    ActionCatalogueEntry,
    build_action_catalogue,
    lookup_action,
)
from .._models import ActionArgumentSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _entry(action_id: str, *, argument_name: str = "profile_name") -> ActionCatalogueEntry:
    return ActionCatalogueEntry(
        action_id=action_id,
        target_command_key="config.profile.create",
        argument_specifications=(
            ActionArgumentBindingSpecification(
                argument_name=argument_name,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=argument_name,
            ),
        ),
    )


def test_initial_actions_are_deterministic_and_lookup_by_stable_identity() -> None:
    action_by_id = {entry.action_id: entry for entry in OPERATOR_ACTION_CATALOGUE.entries}

    assert {
        action_id: (entry.target_command_key, entry.argument_specifications)
        for action_id, entry in action_by_id.items()
    } == {
        "operator.ledger.evidence.review.list": ("ledger.evidence.review.list", ()),
        "operator.live.notifications.list": ("app.live.notifications.list", ()),
        "operator.modelo.export": ("modelo.export", ()),
        "operator.modelo.verification_report.list": (
            "modelo.verification_report.list",
            (
                ActionArgumentBindingSpecification(
                    argument_name="calculation_revision_id",
                    source=ActionArgumentSource.CONDITION_EVIDENCE,
                    source_key="calculation_revision_id",
                    source_evidence_id="workflow.calculation_revision.addressing",
                ),
            ),
        ),
        "operator.modelo.work.calculate": (
            "modelo.work.calculate",
            (
                ActionArgumentBindingSpecification(
                    argument_name="work_unit_id",
                    source=ActionArgumentSource.CONDITION_EVIDENCE,
                    source_key="work_unit_id",
                    source_evidence_id="workflow.work_unit.addressing",
                ),
            ),
        ),
        "operator.modelo.work.status": ("modelo.work.status", ()),
        "operator.overview.explain": (
            "overview.explain",
            (
                ActionArgumentBindingSpecification(
                    argument_name="modelo",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="modelo",
                ),
            ),
        ),
        "operator.overview.status": ("overview.status", ()),
        "operator.profile.create": (
            "config.profile.create",
            (
                ActionArgumentBindingSpecification(
                    argument_name="profile_name",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="profile_name",
                ),
            ),
        ),
        "operator.profile.edit": (
            "config.profile.edit",
            (
                ActionArgumentBindingSpecification(
                    argument_name="profile_name",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="profile_name",
                ),
            ),
        ),
        "operator.profile.login": (
            "config.login",
            (
                ActionArgumentBindingSpecification(
                    argument_name="name",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="name",
                ),
            ),
        ),
        "operator.profile.list": ("config.profile.list", ()),
        "operator.profile.repair_clear_active": (
            "config.repair.profile",
            (
                ActionArgumentBindingSpecification(
                    argument_name="clear_active",
                    source=ActionArgumentSource.REQUEST_CONTEXT,
                    source_key="clear_active",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="profile",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="profile",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="yes",
                    source=ActionArgumentSource.REQUEST_CONTEXT,
                    source_key="yes",
                ),
            ),
        ),
        "operator.profile.status": ("config.profile.status", ()),
        "operator.ledger.link": ("ledger.link", ()),
        "operator.ledger.attach": ("ledger.attach", ()),
        "operator.ledger.classify": ("ledger.classify", ()),
        "operator.maintenance.reconcile": ("app.maintenance.reconcile", ()),
        "operator.live.filed.pull_all": ("app.live.filed.pull_all", ()),
        "operator.profile.import": ("config.profile.import", ()),
        "operator.profile.export": ("config.profile.export", ()),
        "operator.profile.archive.import": ("config.profile.archive.import", ()),
        "operator.profile.sandbox.restore": ("config.profile.sandbox.restore", ()),
        "operator.profile.sandbox.prune": ("config.profile.sandbox.prune", ()),
    }
    assert lookup_action("operator.profile.create") is action_by_id["operator.profile.create"]

    reversed_catalogue = build_action_catalogue(reversed(OPERATOR_ACTION_CATALOGUE.entries))
    assert reversed_catalogue.model_dump(mode="json") == OPERATOR_ACTION_CATALOGUE.model_dump(mode="json")


def test_catalogue_fails_closed_for_unknown_action_identity() -> None:
    with pytest.raises(KeyError, match="unknown operator action ID"):
        lookup_action("operator.profile.unknown")


def test_catalogue_rejects_duplicate_action_and_argument_declarations() -> None:
    with pytest.raises(ValidationError, match="action IDs must be unique"):
        ActionCatalogue(entries=(_entry("operator.profile.create"), _entry("operator.profile.create")))

    with pytest.raises(ValidationError, match="specification names must be unique"):
        ActionCatalogueEntry(
            action_id="operator.profile.create",
            target_command_key="config.profile.create",
            argument_specifications=(
                ActionArgumentBindingSpecification(
                    argument_name="profile_name",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="profile_name",
                ),
                ActionArgumentBindingSpecification(
                    argument_name="profile_name",
                    source=ActionArgumentSource.REQUEST_CONTEXT,
                    source_key="profile_name",
                ),
            ),
        )


def test_argument_source_specification_requires_exact_evidence_identity_only_when_needed() -> None:
    evidence_specification = ActionArgumentBindingSpecification(
        argument_name="work_unit_id",
        source=ActionArgumentSource.CONDITION_EVIDENCE,
        source_key="work_unit_id",
        source_evidence_id="workflow.work_unit.addressing",
    )
    assert evidence_specification.source_evidence_id == "workflow.work_unit.addressing"

    with pytest.raises(ValidationError, match="require source_evidence_id"):
        ActionArgumentBindingSpecification(
            argument_name="work_unit_id",
            source=ActionArgumentSource.CONDITION_EVIDENCE,
            source_key="work_unit_id",
        )
    with pytest.raises(ValidationError, match="only condition-evidence"):
        ActionArgumentBindingSpecification(
            argument_name="profile_name",
            source=ActionArgumentSource.VERDICT_CONTEXT,
            source_key="profile_name",
            source_evidence_id="workflow.work_unit.addressing",
        )


def test_catalogue_declarations_cannot_carry_predicates_text_paths_or_runtime_values() -> None:
    assert set(ActionCatalogueEntry.model_fields) == {
        "action_id",
        "target_command_key",
        "argument_specifications",
    }
    assert set(ActionArgumentBindingSpecification.model_fields) == {
        "argument_name",
        "source",
        "source_key",
        "source_evidence_id",
    }
    assert all("aeat " not in entry.target_command_key for entry in OPERATOR_ACTION_CATALOGUE.entries)


def test_catalogue_contains_only_local_canonical_action_declarations() -> None:
    declaration = OPERATOR_ACTION_CATALOGUE.model_dump_json()

    assert "external" not in declaration
    assert "database" not in declaration
    assert "aeat " not in declaration
    assert "`" not in declaration


def test_catalogue_rejects_noncanonical_action_and_argument_identifiers() -> None:
    with pytest.raises(ValidationError, match="action_id"):
        ActionCatalogueEntry(
            action_id="operator profile create",
            target_command_key="config.profile.create",
        )

    with pytest.raises(ValidationError, match="argument_name"):
        ActionArgumentBindingSpecification(
            argument_name="profile name",
            source=ActionArgumentSource.VERDICT_CONTEXT,
            source_key="profile_name",
        )


@pytest.mark.parametrize(
    ("invalid_record", "match"),
    (
        pytest.param(
            lambda: ActionCatalogueEntry(
                action_id="operator.profile.create",
                target_command_key="config profile create",
            ),
            "target_command_key",
            id="target-command-key",
        ),
        pytest.param(
            lambda: ActionArgumentBindingSpecification(
                argument_name="profile_name",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="profile name",
            ),
            "source_key",
            id="catalogue-source-key",
        ),
        pytest.param(
            lambda: ActionArgumentBindingSpecification(
                argument_name="profile_name",
                source=ActionArgumentSource.CONDITION_EVIDENCE,
                source_key="profile_name",
                source_evidence_id="workflow work unit addressing",
            ),
            "source_evidence_id",
            id="catalogue-source-evidence-id",
        ),
    ),
)
def test_catalogue_models_reject_noncanonical_identifier_fields(
    invalid_record: Callable[[], object],
    match: str,
) -> None:
    with pytest.raises(ValidationError, match=match):
        invalid_record()


def test_catalogue_records_are_immutable() -> None:
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        OPERATOR_ACTION_CATALOGUE.entries[0].target_command_key = "config.profile.edit"
