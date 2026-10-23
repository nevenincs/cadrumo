"""Exact-session dispatch and receipt correlation for every installed categorisation door.

Each door is taken from the production composer and observed through the
operation's real definition and public registration, so the definition id,
the request schema and the registered result type are the ones the runtime
host enrols. A result for another profile, a receipt with the wrong effect, a
refusal receipt and a lapsed session are each refused.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.ledger.allocate_operation import (
    LedgerAllocateOperationResult,
    LedgerAllocateRequest,
    build_ledger_allocate_definition,
    build_ledger_allocate_registration,
)
from cadrumo.application.ledger.bulk_classify_operation import (
    LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LedgerBulkClassifyProjection,
    LedgerBulkClassifyRequest,
    build_ledger_bulk_classify_definition,
    build_ledger_bulk_classify_registration,
)
from cadrumo.application.ledger.classify_result_contracts import LedgerClassifyOperationResult
from cadrumo.application.ledger.counterparty_operation import (
    CounterpartyResolutionProjection,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
    build_ledger_counterparty_definition,
    build_ledger_counterparty_registration,
)
from cadrumo.application.ledger.list_operation import (
    LedgerListProjection,
    LedgerListRequest,
    build_ledger_list_definition,
    build_ledger_list_registration,
)
from cadrumo.application.ledger.llm_diagnostics_operation import (
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsReportSnapshot,
    LedgerLlmDiagnosticsRequest,
    build_ledger_llm_diagnostics_definition,
    build_ledger_llm_diagnostics_registration,
)
from cadrumo.application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    LedgerLlmReviewRequest,
)
from cadrumo.application.ledger.llm_review_operation import (
    build_ledger_llm_review_definition,
    build_ledger_llm_review_registration,
)
from cadrumo.application.ledger.llm_review_results import LedgerLlmOperationResult
from cadrumo.application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from cadrumo.application.ledger.models import BulkClassifyResult
from cadrumo.application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest, LedgerOperatorIvaResult
from cadrumo.application.ledger.operator_iva_operation import (
    build_ledger_operator_iva_definition,
    build_ledger_operator_iva_registration,
)
from cadrumo.application.ledger.participation_operation import (
    LedgerParticipationProjection,
    LedgerParticipationRequest,
    build_ledger_participation_definition,
    build_ledger_participation_registration,
)
from cadrumo.application.ledger.participation_rebuild_operation import (
    LedgerParticipationRebuildProjection,
    LedgerParticipationRebuildRequest,
    build_ledger_participation_rebuild_definition,
    build_ledger_participation_rebuild_registration,
)
from cadrumo.application.ledger.ratios_contracts import (
    LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE,
    LedgerRatiosEligibleProjection,
    LedgerRatiosEligibleRequest,
    LedgerRatiosListProjection,
    LedgerRatiosListRequest,
    LedgerRatiosSetProjection,
    LedgerRatiosSetRequest,
    LedgerRatiosUnsetProjection,
    LedgerRatiosUnsetRequest,
    LedgerRatiosValidateProjection,
    LedgerRatiosValidateRequest,
)
from cadrumo.application.ledger.ratios_operation import (
    build_ledger_ratios_eligible_definition,
    build_ledger_ratios_eligible_registration,
    build_ledger_ratios_list_definition,
    build_ledger_ratios_list_registration,
    build_ledger_ratios_set_definition,
    build_ledger_ratios_set_registration,
    build_ledger_ratios_unset_definition,
    build_ledger_ratios_unset_registration,
    build_ledger_ratios_validate_definition,
    build_ledger_ratios_validate_registration,
)
from cadrumo.application.ledger.rule_contracts import (
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
    LedgerRuleRowProjection,
)
from cadrumo.application.ledger.rule_operation import (
    build_ledger_rule_add_definition,
    build_ledger_rule_add_registration,
    build_ledger_rule_apply_definition,
    build_ledger_rule_apply_registration,
    build_ledger_rule_list_definition,
    build_ledger_rule_list_registration,
)
from cadrumo.application.ledger.split_operation import (
    LedgerSplitChildRequest,
    LedgerSplitOperationResult,
    LedgerSplitRequest,
    build_ledger_split_definition,
    build_ledger_split_registration,
)
from cadrumo.application.ledger.transaction_projection import LedgerTransactionProjection
from cadrumo.application.operations.error_detail import OperationErrorDetailV1
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.operation_definition import OperationDefinition
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.application.review.filter import LedgerReviewStatus
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.transactions.classification_rule import LedgerClassificationRule
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.categorisation_doors import LedgerCategorisationDoorsV1
from cadrumo.entrypoints.tui.operations.outcome import (
    OperationOutcomeUnknownError,
    SessionExpiredOutcomeUnknownError,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController

from ....frontend.tui.runtime_ledger_categorisation import (
    compose_categorisation_tools,
    compose_runtime_categorisation_doors,
)
from .unsupported_result import raises_unsupported_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000d2")
_OTHER_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000ff")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000d2")
_OPERATION_ID = "a" * 64
_TX = "b" * 64
_NOW = datetime(2026, 10, 22, tzinfo=UTC)
_UNUSED: Any = cast(object, lambda **_kwargs: None)


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID
        self.session_read_threads: list[int] = []
        """The thread of each blocking session read: at composition, then around each operation."""


class _Controller:
    operation_id = _OPERATION_ID
    client: _Client

    def __init__(self, observation: OperationObservationSuccessV1, result: BaseModel | None) -> None:
        self.observation = observation
        self.result = result
        self.result_reads: list[tuple[type[BaseModel], bool]] = []

    async def start(self) -> str:
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        del after_cursor, page_limit
        return self.observation

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> BaseModel:
        assert projection.operation_id == self.operation_id
        assert result_version == 1
        self.result_reads.append((result_type, allow_refusal_detail))
        assert self.result is not None
        return self.result

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        del projection
        return None


def _transaction(
    classification: BusinessClassification = BusinessClassification.BUSINESS,
) -> LedgerTransactionProjection:
    stamp = "2026-03-01T09:00:00+00:00"
    return LedgerTransactionProjection(
        transaction_id=_TX,
        date="2026-03-14",
        booked_date="2026-03-14",
        value_date=None,
        amount="100.00",
        currency="EUR",
        direction="outgoing",
        counterparty="Suministros Delta SL",
        description="Material de oficina",
        business_classification=classification.value,
        business_pct="0.5" if classification is BusinessClassification.MIXED else None,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        irpf_category=None,
        m210_income_classification=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        purchase_invoice_evidence_id=None,
        invoice_id=None,
        attachment_ids=(),
        notes="",
        lifecycle_state="ACTIVE",
        classified_by="operator",
        classified_at=None,
        classification_reason="",
        classification_confidence=None,
        source_jurisdiction=None,
        value_in_eur=None,
        fx_rate=None,
        created_at=stamp,
        modified_at=stamp,
    )


def _classified(profile_id: UUID) -> LedgerClassifyOperationResult:
    return LedgerClassifyOperationResult(
        outcome="classified",
        profile_id=profile_id,
        transaction=_transaction(),
        review_status=LedgerReviewStatus.REVIEWED,
        bucket_event_ids=("c" * 64,),
    )


def _rule(profile_id: UUID) -> LedgerRuleAddProjection:
    rule = LedgerClassificationRule.create(
        description_pattern="papelería",
        classification=BusinessClassification.BUSINESS,
        category_id=None,
        priority=100,
        actor="operator",
    )
    return LedgerRuleAddProjection(profile_id=profile_id, outcome="added", rule=LedgerRuleRowProjection.from_rule(rule))


def _diagnostics(profile_id: UUID) -> LedgerLlmDiagnosticsProjection:
    threshold = PublicDecimal(decimal="0.5")
    return LedgerLlmDiagnosticsProjection(
        profile_id=profile_id,
        operation_id="ledger.llm-diagnostics",
        outcome="completed",
        effect=OperationEffect.NONE,
        since=date(2026, 1, 1),
        until=None,
        low_confidence_threshold=threshold,
        report=LedgerLlmDiagnosticsReportSnapshot(
            since=date(2026, 1, 1),
            until=None,
            low_confidence_threshold=threshold,
            usage_providers=(),
            total_calls=0,
            total_cache_hits=0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_cost_estimate_usd=None,
            total_unpriced_calls=0,
            confidence_providers=(),
            total_classified=0,
            total_low_confidence=0,
        ),
    )


@dataclass(frozen=True)
class _Case:
    """One categorisation door, the operation behind it and one request it answers."""

    door: str
    definition: Callable[[], OperationDefinition]
    registration: Callable[[OperationDefinition], OperationPublicDefinitionRegistrationV1]
    request: BaseModel
    result: Callable[[UUID], BaseModel]
    effect: OperationEffect
    refusal_code: str = "REFUSED_CLI_VALIDATION_BOUNDARY"


_CASES: tuple[_Case, ...] = (
    _Case(
        "selection",
        lambda: build_ledger_list_definition(_UNUSED),
        build_ledger_list_registration,
        LedgerListRequest(profile_id=_PROFILE_ID, limit=200),
        lambda profile: LedgerListProjection(
            profile_id=profile, rows=(), total=0, truncated=False, offset=0, limit=200, by_group=False
        ),
        OperationEffect.NONE,
    ),
    _Case(
        "bulk_classify",
        lambda: build_ledger_bulk_classify_definition(_UNUSED),
        build_ledger_bulk_classify_registration,
        LedgerBulkClassifyRequest(profile_id=_PROFILE_ID, csv_text=f"transaction_id,classification\n{_TX},BUSINESS\n"),
        lambda profile: LedgerBulkClassifyProjection(
            profile_id=profile,
            outcome="classified",
            result=BulkClassifyResult(total=1, applied=1, skipped=0, bucket_event_ids=("c" * 64,)),
        ),
        OperationEffect.UPDATED,
        LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE,
    ),
    _Case(
        "operator_iva",
        lambda: build_ledger_operator_iva_definition(_UNUSED),
        build_ledger_operator_iva_registration,
        LedgerOperatorIvaRequest(profile_id=_PROFILE_ID, transaction_id=_TX[:12], iva_category="GENERAL"),
        lambda profile: LedgerOperatorIvaResult(
            profile_id=profile,
            transaction_id=_TX,
            iva_category="GENERAL",
            derivable=True,
            iva_rate="0.21",
            taxable_base="82.64",
            iva_amount="17.36",
            classification=_classified(profile),
        ),
        OperationEffect.UPDATED,
    ),
    _Case(
        "rule_list",
        lambda: build_ledger_rule_list_definition(_UNUSED),
        build_ledger_rule_list_registration,
        LedgerRuleListRequest(profile_id=_PROFILE_ID),
        lambda profile: LedgerRuleListProjection(profile_id=profile, rules=()),
        OperationEffect.NONE,
    ),
    _Case(
        "rule_add",
        lambda: build_ledger_rule_add_definition(_UNUSED),
        build_ledger_rule_add_registration,
        LedgerRuleAddRequest(
            profile_id=_PROFILE_ID, description_pattern="papelería", classification=BusinessClassification.BUSINESS
        ),
        _rule,
        OperationEffect.UPDATED,
    ),
    _Case(
        "rule_apply",
        lambda: build_ledger_rule_apply_definition(_UNUSED, _UNUSED),
        build_ledger_rule_apply_registration,
        LedgerRuleApplyRequest(profile_id=_PROFILE_ID, dry_run=True),
        lambda profile: LedgerRuleApplyProjection(
            profile_id=profile, outcome="dry_run", dry_run=True, would_match=(), count=0
        ),
        OperationEffect.NONE,
    ),
    _Case(
        "counterparty",
        lambda: build_ledger_counterparty_definition(_UNUSED),
        build_ledger_counterparty_registration,
        LedgerCounterpartyRequest(profile_id=_PROFILE_ID, action="view", tax_identifier="B00000000"),
        lambda profile: LedgerCounterpartyResult(
            profile_id=profile,
            action="view",
            tax_identifier="B00000000",
            resolution=CounterpartyResolutionProjection(),
        ),
        OperationEffect.NONE,
    ),
    _Case(
        "split",
        lambda: build_ledger_split_definition(_UNUSED),
        build_ledger_split_registration,
        LedgerSplitRequest(
            profile_id=_PROFILE_ID,
            transaction_id=_TX[:12],
            children=(
                LedgerSplitChildRequest(amount="60", description="Ordenador"),
                LedgerSplitChildRequest(amount="40", description="Monitor"),
            ),
        ),
        lambda profile: LedgerSplitOperationResult(
            profile_id=profile,
            parent_transaction_id=_TX,
            split_group_id="d" * 64,
            child_transaction_ids=("e" * 64, "f" * 64),
            bucket_event_id="c" * 64,
            parent_business_classification=BusinessClassification.BUSINESS,
            child_business_classification=BusinessClassification.NOT_YET_PROCESSED,
            remerged_by=("ledger.merge",),
        ),
        OperationEffect.UPDATED,
    ),
    _Case(
        "allocate",
        lambda: build_ledger_allocate_definition(_UNUSED),
        build_ledger_allocate_registration,
        LedgerAllocateRequest(profile_id=_PROFILE_ID, transaction_id=_TX[:12], business_pct="0.5"),
        lambda profile: LedgerAllocateOperationResult(
            profile_id=profile,
            transaction=_transaction(BusinessClassification.MIXED),
            review_status=LedgerReviewStatus.REVIEWED,
            bucket_event_ids=("c" * 64,),
        ),
        OperationEffect.UPDATED,
    ),
    _Case(
        "participation",
        lambda: build_ledger_participation_definition(_UNUSED, _UNUSED),
        build_ledger_participation_registration,
        LedgerParticipationRequest(profile_id=_PROFILE_ID, transaction_prefix=_TX[:12]),
        lambda profile: LedgerParticipationProjection(
            profile_id=profile, transaction_prefix=_TX[:12], transaction_id=_TX, participations=()
        ),
        OperationEffect.NONE,
    ),
    _Case(
        "participation_rebuild",
        lambda: build_ledger_participation_rebuild_definition(_UNUSED),
        build_ledger_participation_rebuild_registration,
        LedgerParticipationRebuildRequest(profile_id=_PROFILE_ID),
        lambda profile: LedgerParticipationRebuildProjection(
            profile_id=profile, transaction_count=1, participation_count=0, revision_count=0, stale_removed_count=0
        ),
        OperationEffect.UPDATED,
    ),
    _Case(
        "llm_diagnostics",
        lambda: build_ledger_llm_diagnostics_definition(_UNUSED),
        build_ledger_llm_diagnostics_registration,
        LedgerLlmDiagnosticsRequest(
            profile_id=_PROFILE_ID, since=date(2026, 1, 1), low_confidence_threshold=PublicDecimal(decimal="0.5")
        ),
        _diagnostics,
        OperationEffect.NONE,
    ),
    _Case(
        "ratios_list",
        build_ledger_ratios_list_definition,
        build_ledger_ratios_list_registration,
        LedgerRatiosListRequest(profile_id=_PROFILE_ID, year=2026),
        lambda profile: LedgerRatiosListProjection(profile_id=profile, year=2026, outcome="available", count=0),
        OperationEffect.NONE,
    ),
    _Case(
        "ratios_eligible",
        build_ledger_ratios_eligible_definition,
        build_ledger_ratios_eligible_registration,
        LedgerRatiosEligibleRequest(profile_id=_PROFILE_ID, year=2026),
        lambda profile: LedgerRatiosEligibleProjection(profile_id=profile, year=2026, rows=(), count=0),
        OperationEffect.NONE,
    ),
    _Case(
        "ratios_validate",
        build_ledger_ratios_validate_definition,
        build_ledger_ratios_validate_registration,
        LedgerRatiosValidateRequest(profile_id=_PROFILE_ID),
        lambda profile: LedgerRatiosValidateProjection(
            profile_id=profile, profile_present=False, eligible_count=0, overrides_count=0
        ),
        OperationEffect.NONE,
    ),
    _Case(
        "ratios_set",
        build_ledger_ratios_set_definition,
        build_ledger_ratios_set_registration,
        LedgerRatiosSetRequest(profile_id=_PROFILE_ID, category="vehiculo", ratio="0.5", year=2026),
        lambda profile: LedgerRatiosSetProjection(
            profile_id=profile, requested_category="vehiculo", category="vehiculo", ratio="0.5"
        ),
        OperationEffect.UPDATED,
    ),
    _Case(
        "ratios_unset",
        build_ledger_ratios_unset_definition,
        build_ledger_ratios_unset_registration,
        LedgerRatiosUnsetRequest(profile_id=_PROFILE_ID, category="vehiculo"),
        lambda profile: LedgerRatiosUnsetProjection(
            profile_id=profile, requested_category="vehiculo", category="vehiculo", outcome="cleared", prior_ratio="0.5"
        ),
        OperationEffect.UPDATED,
        LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE,
    ),
)


def _observation(
    case: _Case,
    *,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect | None = None,
) -> OperationObservationSuccessV1:
    definition = case.definition()
    registry = OperationRegistry(definitions=(definition,), public_registrations=(case.registration(definition),))
    contract = registry.lookup_public_contract(definition.definition_id)
    refused = condition is OperationTerminalCondition.REFUSED
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=registry.public_contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        effect=case.effect if effect is None else effect,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None if refused else "f" * 64,
        refusal_ref=case.refusal_code if refused else None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=state,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


def _install(monkeypatch: pytest.MonkeyPatch, client: _Client, controller: _Controller) -> list[dict[str, object]]:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        assert profile_label == "Fixture profile"
        client.session_read_threads.append(threading.get_ident())
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    submissions: list[dict[str, object]] = []

    async def submit(_type: type[OperationController], received: FrontendClient, **kwargs: object) -> _Controller:
        assert received is client
        submissions.append(kwargs)
        controller.client = client
        return controller

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    return submissions


def _doors(client: _Client) -> LedgerCategorisationDoorsV1:
    return compose_runtime_categorisation_doors(cast(FrontendClient, client), "Fixture profile")


def _call(doors: LedgerCategorisationDoorsV1, case: _Case) -> BaseModel:
    door = getattr(doors, case.door)
    result = asyncio.run(door(case.request))
    assert isinstance(result, BaseModel)
    return result


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.door)
def test_each_door_submits_the_exact_request_and_reads_its_registered_result(
    monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    client = _Client()
    result = case.result(_PROFILE_ID)
    controller = _Controller(_observation(case), result)
    submissions = _install(monkeypatch, client, controller)

    assert _call(_doors(client), case) == result
    assert submissions[0]["definition_id"] == case.definition().definition_id
    assert submissions[0]["payload"] == case.request
    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert [read for read, _detail in controller.result_reads] == [type(result)]


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.door)
def test_each_door_refuses_a_result_for_another_profile(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    receipt = _observation(case)
    _install(monkeypatch, client, _Controller(receipt, case.result(_OTHER_PROFILE_ID)))

    with raises_unsupported_result(receipt.projection.effect, receipt.projection.definition_contract):
        _call(_doors(client), case)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.door)
def test_each_door_refuses_a_receipt_with_the_wrong_effect(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    wrong = OperationEffect.NONE if case.effect is OperationEffect.UPDATED else OperationEffect.UPDATED
    receipt = _observation(case, effect=wrong)
    _install(monkeypatch, client, _Controller(receipt, case.result(_PROFILE_ID)))

    with raises_unsupported_result(receipt.projection.effect, receipt.projection.definition_contract):
        _call(_doors(client), case)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.door)
def test_each_door_refuses_a_refusal_receipt_carrying_a_success_result(
    monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    client = _Client()
    observation = _observation(case, condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.NONE)
    _install(monkeypatch, client, _Controller(observation, case.result(_PROFILE_ID)))

    with pytest.raises((RefusalError, FrontendRefusedError)) as raised:
        _call(_doors(client), case)

    if isinstance(raised.value, RefusalError):
        assert raised.value.reason is RefusalCode.INVALID_FRAME
    else:
        assert raised.value.reason == case.refusal_code


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.door)
def test_each_door_fails_closed_when_its_session_lapses(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    submissions = _install(monkeypatch, client, _Controller(_observation(case), case.result(_PROFILE_ID)))
    doors = _doors(client)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        _call(doors, case)

    assert submissions == []


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.door)
def test_each_door_reads_its_session_off_the_event_loop_thread(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    """The session read is a blocking IPC exchange; a door awaited on the loop never runs it there."""
    client = _Client()
    _install(monkeypatch, client, _Controller(_observation(case), case.result(_PROFILE_ID)))
    doors = _doors(client)
    client.session_read_threads.clear()

    _call(doors, case)

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads


def test_a_declared_refusal_is_read_with_its_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    case = next(item for item in _CASES if item.door == "bulk_classify")
    client = _Client()
    refusal = LedgerBulkClassifyProjection(
        profile_id=_PROFILE_ID, outcome="validation_error", validation_messages=("row 1: unknown column",)
    )
    observation = _observation(case, condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.NONE)
    controller = _Controller(observation, refusal)
    _install(monkeypatch, client, controller)

    assert _call(_doors(client), case) == refusal
    assert controller.result_reads == [(LedgerBulkClassifyProjection, True)]


def test_the_composer_builds_every_tool_on_one_pinned_session(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    reads: list[UUID] = []
    from ....frontend.tui.operations import runtime_profile_session as bridge

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        del profile_id, profile_label
        reads.append(session_id)
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)

    tools = compose_categorisation_tools(cast(FrontendClient, client), "Fixture profile")

    assert tuple(tool.key for tool in tools) == (
        "ledger.tool.categorisation.bulk",
        "ledger.tool.categorisation.iva",
        "ledger.tool.categorisation.review",
        "ledger.tool.categorisation.rules",
        "ledger.tool.categorisation.counterparties",
        "ledger.tool.categorisation.split",
        "ledger.tool.categorisation.allocate",
        "ledger.tool.categorisation.participation",
        "ledger.tool.categorisation.ratios",
        "ledger.tool.categorisation.diagnostics",
    )
    assert reads == [_SESSION_ID]


# -- The review doors --------------------------------------------------------


def _review_request(*, split: bool = False, profile_id: UUID = _PROFILE_ID) -> LedgerLlmReviewRequest:
    return LedgerLlmReviewRequest(
        profile_id=profile_id,
        transaction_id=_TX[:12],
        mode="split" if split else "classification",
        origin=LlmReviewInvocationOrigin.SPLIT_LLM if split else LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
    )


def _review_case(definition_id: str) -> _Case:
    return _Case(
        "classify_review" if definition_id == LEDGER_CLASSIFY_REVIEW_DEFINITION_ID else "split_review",
        lambda: build_ledger_llm_review_definition(definition_id, _UNUSED),
        build_ledger_llm_review_registration,
        _review_request(split=definition_id == LEDGER_SPLIT_REVIEW_DEFINITION_ID),
        lambda profile: LedgerLlmOperationResult(
            profile_id=profile,
            reviewed_proposal_digest="9" * 64,
            outcome="classified",
            transaction_id=_TX,
            classification=_classified(profile),
            provenance="llm:lector-local",
        ),
        OperationEffect.UPDATED,
    )


@dataclass
class _ReviewLog:
    submissions: list[dict[str, object]]
    started: list[str]


def _install_review(monkeypatch: pytest.MonkeyPatch, client: _Client, result: BaseModel) -> _ReviewLog:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        del profile_label
        client.session_read_threads.append(threading.get_ident())
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    submissions: list[dict[str, object]] = []
    started: list[str] = []

    async def submit(_type: type[OperationController], received: FrontendClient, **kwargs: object) -> object:
        assert received is client
        submissions.append(kwargs)

        class _Started:
            operation_id = _OPERATION_ID

            async def start(self) -> str:
                started.append(_OPERATION_ID)
                return _OPERATION_ID

        return _Started()

    async def read_settled_result(
        self: OperationController,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> BaseModel:
        assert self.operation_id == projection.operation_id
        assert result_type is LedgerLlmOperationResult
        assert result_version == 1
        assert not allow_refusal_detail
        return result

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    monkeypatch.setattr(OperationController, "read_settled_result", read_settled_result)
    return _ReviewLog(submissions=submissions, started=started)


def test_the_review_door_starts_the_exact_review_and_refuses_another_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    case = _review_case(LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
    log = _install_review(monkeypatch, client, case.result(_PROFILE_ID))
    doors = _doors(client)

    asyncio.run(doors.classify_review.submit(_review_request()))
    submitted = log.submissions[0]
    assert log.started == [_OPERATION_ID]
    assert submitted["definition_id"] == LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
    assert submitted["payload"] == _review_request()
    assert submitted["expected_session_id"] == _SESSION_ID

    with pytest.raises(RefusalError):
        asyncio.run(doors.classify_review.submit(_review_request(split=True)))
    with pytest.raises(RefusalError):
        asyncio.run(doors.split_review.submit(_review_request()))


@pytest.mark.parametrize("definition_id", [LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, LEDGER_SPLIT_REVIEW_DEFINITION_ID])
def test_the_review_door_reads_a_settled_outcome_only_when_its_receipt_agrees(
    monkeypatch: pytest.MonkeyPatch, definition_id: str
) -> None:
    case = _review_case(definition_id)
    request = cast(LedgerLlmReviewRequest, case.request)
    good = case.result(_PROFILE_ID)
    if definition_id == LEDGER_SPLIT_REVIEW_DEFINITION_ID:
        good = LedgerLlmOperationResult(
            profile_id=_PROFILE_ID,
            reviewed_proposal_digest="9" * 64,
            outcome="split",
            transaction_id=_TX,
            split_group_id="d" * 64,
            child_transaction_ids=("e" * 64, "f" * 64),
            classified_child_count=2,
            provenance="llm:lector-local",
        )
    door_name = case.door

    def read(result: BaseModel, observation: OperationObservationSuccessV1, client: _Client) -> BaseModel:
        _install_review(monkeypatch, client, result)
        door = getattr(_doors(client), door_name)
        read_back: object = asyncio.run(door.read_result(request, observation.projection))
        assert isinstance(read_back, BaseModel)
        return read_back

    assert read(good, _observation(case), _Client()) == good

    # A result for another profile cannot correlate; the receipt still reported its effect.
    other = good.model_copy(update={"profile_id": _OTHER_PROFILE_ID})
    receipt = _observation(case)
    with raises_unsupported_result(receipt.projection.effect, receipt.projection.definition_contract):
        read(other, receipt, _Client())

    with pytest.raises(RefusalError):
        read(good, _observation(case, effect=OperationEffect.NONE), _Client())

    # A receipt that did not succeed is not this door's to read. One that committed nothing is a refusal;
    # one that reports an effect may have saved the change, so its outcome is unknown.
    with pytest.raises(RefusalError) as refused:
        read(
            good,
            _observation(case, condition=OperationTerminalCondition.REFUSED, effect=OperationEffect.NONE),
            _Client(),
        )
    assert not isinstance(refused.value, OperationOutcomeUnknownError)
    refused_with_effect = _observation(case, condition=OperationTerminalCondition.REFUSED)
    with raises_unsupported_result(
        refused_with_effect.projection.effect, refused_with_effect.projection.definition_contract
    ):
        read(good, refused_with_effect, _Client())

    lapsed = _Client()
    _install_review(monkeypatch, lapsed, good)
    door = getattr(_doors(lapsed), door_name)
    lapsed.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")
    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door.read_result(request, _observation(case).projection))


@pytest.mark.parametrize("definition_id", [LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, LEDGER_SPLIT_REVIEW_DEFINITION_ID])
def test_the_review_door_reads_its_session_off_the_event_loop_thread(
    monkeypatch: pytest.MonkeyPatch, definition_id: str
) -> None:
    """Starting a review and reading its outcome each check the session without blocking the loop."""
    case = _review_case(definition_id)
    request = cast(LedgerLlmReviewRequest, case.request)
    client = _Client()
    result = case.result(_PROFILE_ID)
    if definition_id == LEDGER_SPLIT_REVIEW_DEFINITION_ID:
        result = LedgerLlmOperationResult(
            profile_id=_PROFILE_ID,
            reviewed_proposal_digest="9" * 64,
            outcome="split",
            transaction_id=_TX,
            split_group_id="d" * 64,
            child_transaction_ids=("e" * 64, "f" * 64),
            classified_child_count=2,
            provenance="llm:lector-local",
        )
    _install_review(monkeypatch, client, result)
    door = getattr(_doors(client), case.door)
    client.session_read_threads.clear()

    asyncio.run(door.submit(request))

    assert client.session_read_threads, "starting a review reads the session"
    assert threading.get_ident() not in client.session_read_threads

    client.session_read_threads.clear()
    asyncio.run(door.read_result(request, _observation(case).projection))

    assert client.session_read_threads, "reading a settled review reads the session"
    assert threading.get_ident() not in client.session_read_threads


def test_a_review_whose_start_reply_is_lost_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runtime accepted the review; a lost start reply does not say it never ran."""
    client = _Client()
    case = _review_case(LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
    contract = _observation(case).projection.definition_contract
    _install_review(monkeypatch, client, case.result(_PROFILE_ID))

    async def submit(_type: type[OperationController], _received: FrontendClient, **_kwargs: object) -> object:
        class _Accepted:
            operation_id = _OPERATION_ID
            definition_contract = contract

            async def start(self) -> str:
                raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)

        return _Accepted()

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    door = _doors(client).classify_review

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(door.submit(_review_request()))

    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is None


def test_a_settled_review_whose_result_cannot_be_read_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """The receipt reported the classification applied; failing to read it does not unapply it."""
    client = _Client()
    case = _review_case(LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
    _install_review(monkeypatch, client, case.result(_PROFILE_ID))

    async def refused_read(
        _self: OperationController,
        _projection: OperationPublicProjectionV1,
        _result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> BaseModel:
        raise FrontendRefusedError("result_unavailable")

    monkeypatch.setattr(OperationController, "read_settled_result", refused_read)
    receipt = _observation(case, effect=OperationEffect.UPDATED)
    door = _doors(client).classify_review

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        asyncio.run(door.read_result(cast(LedgerLlmReviewRequest, case.request), receipt.projection))

    assert raised.value.effect is OperationEffect.UPDATED
    assert isinstance(raised.value.reason, FrontendRefusedError)


def test_a_review_whose_session_lapses_before_its_saved_result_is_read_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The receipt reported the classification applied; a session lost before the read does not unapply it."""
    client = _Client()
    case = _review_case(LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
    _install_review(monkeypatch, client, case.result(_PROFILE_ID))
    door = _doors(client).classify_review
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")
    receipt = _observation(case, effect=OperationEffect.UPDATED)

    with pytest.raises(SessionExpiredOutcomeUnknownError) as raised:
        asyncio.run(door.read_result(cast(LedgerLlmReviewRequest, case.request), receipt.projection))

    assert raised.value.outcome.operation_id == _OPERATION_ID
    assert raised.value.outcome.effect is OperationEffect.UPDATED


def test_a_review_whose_session_lapses_after_a_receipt_that_saved_nothing_reports_the_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A receipt that committed nothing leaves nothing unknown: the lost session names that receipt."""
    client = _Client()
    case = _review_case(LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
    _install_review(monkeypatch, client, case.result(_PROFILE_ID))
    door = _doors(client).classify_review
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")
    receipt = _observation(case, effect=OperationEffect.NONE)

    with pytest.raises(AccountSessionExpiredError) as raised:
        asyncio.run(door.read_result(cast(LedgerLlmReviewRequest, case.request), receipt.projection))

    assert not isinstance(raised.value, SessionExpiredOutcomeUnknownError)
    assert raised.value.context is not None
    assert raised.value.context["operation_id"] == _OPERATION_ID
    assert raised.value.context["effect"] == OperationEffect.NONE.value
