"""The recorded action targets say of every catalogue action's command what the command graph says.

A process that holds no command graph resolves a recovery action against the
record. These tests hold the record to the graph for every action in the
catalogue, and hold the resolver that reads the record to the one the command
line uses.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo_client.contracts.command_program import CommandProgram

from ....application.modelo.action_errors import ModeloProfileReadinessError
from ....application.modelo.iva_wallet_refusal import (
    ModeloIvaWalletReconciliationBlockedError,
    raise_iva_wallet_precondition,
)
from ....application.modelo.preconditions import IVA_WALLET_OPENING_BALANCE_SCENARIOS, IVA_WALLET_OVERRIDE_SCENARIOS
from ....application.modelo.profile_readiness_gate import require_existing_profile_baseline_ready_for_modelo_work
from ....application.modelo.work_profile import ModeloWorkProfile
from ....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogueEntry, lookup_action
from ....application.operator_actions.models import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ....application.operator_surface.action_targets import (
    ACTION_TARGETS,
    ActionTarget,
    recorded_action_target_reconciliation,
    resolve_recorded_precondition_action,
)
from ....application.operator_surface.manifest import ReconciledOperatorLeaf
from ....application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from ....core.errors.hierarchy import InternalInvariantError
from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality, ActionEvidenceProvenance
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.user_profile.values import ProfileSetupState, create_user_profile_record
from ..common import resolve_cli_precondition_action
from ..operator_surface_reconciliation import operator_surface_target_reconciliation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CONDITION = "synthetic.condition.holds"


def _targets() -> tuple[str, ...]:
    return tuple(sorted({entry.target_command_key for entry in OPERATOR_ACTION_CATALOGUE.entries}))


def _tax_targets() -> tuple[str, ...]:
    return tuple(target.command_key for target in ACTION_TARGETS if target.program is CommandProgram.AEAT)


def _graph_leaf(command_key: str) -> ReconciledOperatorLeaf:
    (leaf,) = operator_surface_target_reconciliation(command_key).leaves
    return leaf


def _facts(leaf: ReconciledOperatorLeaf) -> object:
    """Return everything a leaf says apart from where each row was read from."""

    def without_provenance(value: object) -> object:
        if isinstance(value, dict):
            return {key: without_provenance(item) for key, item in value.items() if key != "provenance"}
        if isinstance(value, list):
            return [without_provenance(item) for item in value]
        return value

    return without_provenance(leaf.model_dump(mode="json"))


def _verdict(entry: ActionCatalogueEntry) -> PreconditionVerdict:
    """Build a verdict that recommends ``entry`` and leaves every declared argument to the operator."""
    names = tuple(sorted({specification.argument_name for specification in entry.argument_specifications}))
    return PreconditionVerdict(
        failed_condition_id=_CONDITION,
        evidence=(
            ConditionEvidence(
                condition_id=_CONDITION,
                evidence_id="synthetic.condition.observed",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"holds": False},
            ),
        ),
        action=ActionReference(action_id=entry.action_id),
        argument_bindings=tuple(
            ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING) for name in names
        ),
        missing_argument_names=names,
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS if names else ActionConditionality.IMMEDIATE,
    )


def test_the_record_is_exactly_what_the_command_graph_declares_for_each_tax_owned_target() -> None:
    derived = tuple(ActionTarget.of_leaf(_graph_leaf(command_key)) for command_key in _tax_targets())

    assert derived
    assert derived == tuple(target for target in ACTION_TARGETS if target.program is CommandProgram.AEAT), (
        "the recorded action targets no longer match the command graph; record these instead:\n"
        + "\n".join(repr(target) for target in derived)
    )


def test_a_recorded_leaf_reconciles_to_the_leaf_the_command_graph_reconciles() -> None:
    for command_key in _tax_targets():
        (recorded,) = recorded_action_target_reconciliation(command_key).leaves

        assert _facts(recorded) == _facts(_graph_leaf(command_key)), command_key


def test_runtime_owned_records_keep_their_program_root_outside_reconciliation_paths() -> None:
    runtime_targets = tuple(target for target in ACTION_TARGETS if target.program is CommandProgram.AUTHENTICATION)
    assert runtime_targets

    for target in runtime_targets:
        (recorded,) = recorded_action_target_reconciliation(
            target.command_key,
            canonical_cli_path=(target.program.executable_name, *target.cli_path),
        ).leaves

        assert recorded.live_leaf.canonical_cli_path == target.cli_path
        assert recorded.live_leaf.program is target.program
        assert ActionTarget.of_leaf(recorded).program is target.program

        with pytest.raises(ValueError, match="command graph executable contradicts recorded action target"):
            recorded_action_target_reconciliation(target.command_key, canonical_cli_path=("aeat", *target.cli_path))


def test_the_recorded_resolver_prints_the_action_the_command_line_prints_for_every_catalogue_action() -> None:
    for entry in OPERATOR_ACTION_CATALOGUE.entries:
        verdict = _verdict(entry)

        recorded = resolve_recorded_precondition_action(verdict)
        printed = resolve_cli_precondition_action(verdict)

        assert recorded == printed, entry.action_id
        assert recorded.action is not None and (recorded.action.cli_path is not None and recorded.action.cli_path), (
            entry.action_id
        )
        assert recorded.action.target_command_key == entry.target_command_key


def test_the_opening_balance_action_resolves_to_the_live_leaf_with_its_required_inputs() -> None:
    entry = lookup_action("operator.modelo.iva_wallet.seed")
    served = resolve_recorded_precondition_action(_verdict(entry))
    (leaf,) = operator_surface_target_reconciliation(entry.target_command_key).leaves

    assert served.action is not None
    assert served.action.target_command_key == "modelo.iva_wallet.seed"
    assert served.action.cli_path == (leaf.live_leaf.program.executable_name, *leaf.live_leaf.canonical_cli_path)
    assert leaf.input_schema is not None
    assert set(served.missing_argument_names) == set(leaf.input_schema.required_input_names)


def _refused_wallet_verdict(reason_code: str, carry_period: Period) -> PreconditionVerdict:
    """Raise the real 303 wallet gate refusal for ``reason_code`` and return the verdict it records."""
    with pytest.raises(ModeloIvaWalletReconciliationBlockedError) as refused:
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code=reason_code,
            translated_message="application.modelo.errors.iva_wallet_not_seeded",
            evidence_values={"reason": reason_code},
            carry_period=carry_period,
        )
    return refused.value.precondition_failure.verdict


def test_each_real_opening_balance_refusal_records_an_action_that_resolves_to_the_live_leaf(
    operation: PinnedAuthorityOperation,
) -> None:
    assert operation is not None
    envelope = published_supported_filing_years()
    assert envelope is not None
    carry_period = Period.from_year_and_code(envelope.horizon, "1T")

    for reason_code in sorted(IVA_WALLET_OPENING_BALANCE_SCENARIOS):
        served = resolve_recorded_precondition_action(_refused_wallet_verdict(reason_code, carry_period))
        (leaf,) = operator_surface_target_reconciliation("modelo.iva_wallet.seed").leaves

        assert served.action is not None, reason_code
        assert served.action.action_id == "operator.modelo.iva_wallet.seed", reason_code
        assert served.action.cli_path == (leaf.live_leaf.program.executable_name, *leaf.live_leaf.canonical_cli_path)
        bound = {item.argument_name: item for item in served.argument_bindings}
        assert bound["filing_year"].value == carry_period.filing_year
        assert bound["period"].value == carry_period.registry_token
        assert bound["amount"].status is ActionArgumentStatus.MISSING
        assert served.missing_argument_names == ("amount",)
        assert leaf.input_schema is not None
        assert set(bound) == set(leaf.input_schema.required_input_names)


def test_each_real_override_refusal_records_an_action_prefilled_with_the_period_and_local_amount(
    operation: PinnedAuthorityOperation,
) -> None:
    assert operation is not None
    envelope = published_supported_filing_years()
    assert envelope is not None
    carry_period = Period.from_year_and_code(envelope.horizon, "4T")
    local_amount = Decimal("325.50")

    for reason_code in sorted(IVA_WALLET_OVERRIDE_SCENARIOS):
        with pytest.raises(ModeloIvaWalletReconciliationBlockedError) as refused:
            raise_iva_wallet_precondition(
                subject_leaf_key="modelo.work.calculate",
                reason_code=reason_code,
                translated_message=f"application.iva_wallet.decision_reason.{reason_code}",
                evidence_values={"reason": reason_code},
                carry_period=carry_period,
                local_amount=local_amount,
            )
        served = resolve_recorded_precondition_action(refused.value.precondition_failure.verdict)
        (leaf,) = operator_surface_target_reconciliation("modelo.iva_wallet.override").leaves

        assert served.action is not None, reason_code
        assert served.action.action_id == "operator.modelo.iva_wallet.override", reason_code
        assert served.action.cli_path == (leaf.live_leaf.program.executable_name, *leaf.live_leaf.canonical_cli_path)
        bound = {item.argument_name: item for item in served.argument_bindings}
        assert bound["filing_year"].value == carry_period.filing_year
        assert bound["period"].value == carry_period.registry_token
        assert bound["amount"].value == local_amount
        assert bound["reason"].status is ActionArgumentStatus.MISSING
        assert bound["evidence_locator"].status is ActionArgumentStatus.MISSING
        assert set(served.missing_argument_names) == {"reason", "evidence_locator"}
        assert leaf.input_schema is not None
        assert set(bound) == set(leaf.input_schema.required_input_names)


def test_an_override_refusal_without_a_local_amount_leaves_the_amount_to_supply() -> None:
    envelope = published_supported_filing_years()
    assert envelope is not None
    carry_period = Period.from_year_and_code(envelope.horizon, "4T")
    with pytest.raises(ModeloIvaWalletReconciliationBlockedError) as refused:
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="local_recurrence_requires_override",
            translated_message="application.iva_wallet.decision_reason.local_recurrence_requires_override",
            evidence_values={"reason": "local_recurrence_requires_override"},
            carry_period=carry_period,
        )
    verdict = refused.value.precondition_failure.verdict
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.iva_wallet.override"
    assert set(verdict.missing_argument_names) == {"amount", "reason", "evidence_locator"}


def test_an_override_refusal_without_its_period_is_an_invariant_breach() -> None:
    with pytest.raises(InternalInvariantError):
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="local_recurrence_requires_override",
            translated_message="application.iva_wallet.decision_reason.local_recurrence_requires_override",
            evidence_values={"reason": "local_recurrence_requires_override"},
            local_amount=Decimal("325.50"),
        )


def test_a_real_missing_profile_facts_refusal_records_an_action_that_resolves_to_the_live_leaf(
    operation: PinnedAuthorityOperation,
) -> None:
    profile_id = "44444444-4444-4444-8444-444444444444"
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=profile_id,
        setup_state=ProfileSetupState.COMPLETE,
        facts=persona_facts_beneath(without=("activities.",)),
    )
    period = Period.from_year_and_code(operation.supported_filing_years().horizon, "1T")
    with pytest.raises(ModeloProfileReadinessError) as refused:
        require_existing_profile_baseline_ready_for_modelo_work(
            bucket_id=profile_id,
            modelo="303",
            filing_year=period.filing_year,
            period=period,
            enforce_applicability=False,
            profile_decode_context=operation.profile_decode_context(),
            operation=operation,
            profile=ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context()),
        )
    verdict = refused.value.terminal_precondition_verdict
    assert verdict is not None

    served = resolve_recorded_precondition_action(verdict)

    assert served.action is not None, "the refusal names no action"
    assert served.action.action_id == "operator.profile.edit"
    assert served.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    (leaf,) = operator_surface_target_reconciliation(served.action.target_command_key).leaves
    assert served.action.cli_path == (leaf.live_leaf.program.executable_name, *leaf.live_leaf.canonical_cli_path)
    assert served == resolve_cli_precondition_action(verdict)


def test_the_record_refuses_a_command_no_catalogue_action_targets() -> None:
    with pytest.raises(LookupError, match=r"unknown command schema identity: config\.no_such_verb"):
        recorded_action_target_reconciliation("config.no_such_verb")


def test_a_leaf_the_record_cannot_hold_is_refused_rather_than_recorded_in_part() -> None:
    leaf = _graph_leaf(_targets()[0])
    aliased = leaf.model_copy(
        update={"live_leaf": leaf.live_leaf.model_copy(update={"alias_cli_paths": (("synthetic", "alias"),)})}
    )
    unaccounted = leaf.model_copy(update={"input_schema": None})

    for unrecordable in (aliased, unaccounted):
        with pytest.raises(ValueError, match="action target leaf cannot be recorded"):
            ActionTarget.of_leaf(unrecordable)
