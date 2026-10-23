"""The Ledger categorisation tools, bound to the installed TUI's retained runtime session.

Every door pins the one admitted profile and session the workbench holds and
refuses a result its terminal receipt does not support: another profile, an
unexpected effect, a refusal it was not declared to carry, or records other
than the ones the request named. The two review operations pause for the
operator's decision, so their door returns the started operation for the
operation modal and reads the settled outcome afterwards under the same checks.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.ledger.allocate_operation import (
    LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
    LedgerAllocateOperationResult,
    LedgerAllocateRequest,
)
from cadrumo.application.ledger.bulk_classify_operation import (
    LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
    LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LedgerBulkClassifyProjection,
    LedgerBulkClassifyRequest,
)
from cadrumo.application.ledger.classify_result_contracts import LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
from cadrumo.application.ledger.counterparty_operation import (
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from cadrumo.application.ledger.list_operation import (
    LEDGER_LIST_OPERATION_DEFINITION_ID,
    LedgerListProjection,
    LedgerListRequest,
)
from cadrumo.application.ledger.llm_diagnostics_operation import (
    LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from cadrumo.application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    LedgerLlmReviewRequest,
    ledger_llm_review_definition_id,
)
from cadrumo.application.ledger.llm_review_results import LedgerLlmOperationResult
from cadrumo.application.ledger.operator_iva_contracts import (
    LEDGER_OPERATOR_IVA_DEFINITION_ID,
    LedgerOperatorIvaRequest,
    LedgerOperatorIvaResult,
)
from cadrumo.application.ledger.participation_operation import (
    LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID,
    LedgerParticipationProjection,
    LedgerParticipationRequest,
)
from cadrumo.application.ledger.participation_rebuild_operation import (
    LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
    LedgerParticipationRebuildProjection,
    LedgerParticipationRebuildRequest,
)
from cadrumo.application.ledger.ratios_contracts import (
    LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE,
    LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID,
    LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
    LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE,
    LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
    LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
    LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID,
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
from cadrumo.application.ledger.rule_contracts import (
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
)
from cadrumo.application.ledger.rule_operation import (
    LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
    LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
    LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
)
from cadrumo.application.ledger.rule_results import LEDGER_RULE_VALIDATION_REFUSAL_CODE
from cadrumo.application.ledger.split_operation import (
    LEDGER_SPLIT_OPERATION_DEFINITION_ID,
    LedgerSplitOperationResult,
    LedgerSplitRequest,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.entrypoints.tui.ledger.categorisation_doors import LedgerCategorisationDoorsV1
from cadrumo.entrypoints.tui.ledger.categorisation_tools import categorisation_tools
from cadrumo.entrypoints.tui.ledger.tools import LedgerToolV1
from cadrumo.entrypoints.tui.operations.controller_port import OperationControllerPort
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

from .operations.runtime_profile_session import RuntimeProfileSession

type ResultMatcher[RequestT: BaseModel, ResultT: BaseModel] = Callable[
    [ResultT, RequestT, OperationTerminalCondition, OperationPublicProjectionV1], bool
]
"""Whether a read result answers exactly the request under its settled receipt."""


def _succeeded(
    condition: OperationTerminalCondition, terminal: OperationPublicProjectionV1, effect: OperationEffect
) -> bool:
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.failure_error_code is None
        and terminal.effect is effect
    )


def _refused_with(
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
    code: str,
    effects: frozenset[OperationEffect] = frozenset({OperationEffect.NONE}),
) -> bool:
    return (
        condition is OperationTerminalCondition.REFUSED
        and terminal.refusal_ref == code
        and terminal.failure_error_code is None
        and terminal.effect in effects
    )


def _effect_of(changed: bool) -> OperationEffect:
    return OperationEffect.UPDATED if changed else OperationEffect.NONE


def _names_entry(resolved: str, prefix: str) -> bool:
    return resolved.startswith(prefix.strip().lower())


def selection_matches(
    result: LedgerListProjection,
    request: LedgerListRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """One page of the requested window, read without effect."""
    return (
        result.profile_id == request.profile_id
        and result.offset == request.offset
        and result.limit == request.limit
        and _succeeded(condition, terminal, OperationEffect.NONE)
    )


def bulk_classify_matches(
    result: LedgerBulkClassifyProjection,
    request: LedgerBulkClassifyRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """A complete batch outcome, or the declared pre-write refusal with its findings."""
    if result.profile_id != request.profile_id:
        return False
    if result.outcome == "validation_error":
        return _refused_with(condition, terminal, LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE)
    batch = result.result
    return batch is not None and _succeeded(condition, terminal, _effect_of(bool(batch.bucket_event_ids)))


def operator_iva_matches(
    result: LedgerOperatorIvaResult,
    request: LedgerOperatorIvaRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The derivation of the requested entry and category, or its declared refusal."""
    if (
        result.profile_id != request.profile_id
        or not _names_entry(result.transaction_id, request.transaction_id)
        or result.iva_category != request.iva_category
    ):
        return False
    if result.outcome == "validation_error":
        return _refused_with(condition, terminal, LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE)
    written = result.classification is not None and bool(result.classification.bucket_event_ids)
    return _succeeded(condition, terminal, _effect_of(written))


def rule_list_matches(
    result: LedgerRuleListProjection,
    request: LedgerRuleListRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The profile's rules, read without effect."""
    return result.profile_id == request.profile_id and _succeeded(condition, terminal, OperationEffect.NONE)


def rule_add_matches(
    result: LedgerRuleAddProjection,
    request: LedgerRuleAddRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The saved rule the request described, or the declared refusal with its findings."""
    if result.profile_id != request.profile_id:
        return False
    if result.outcome == "validation_error":
        return _refused_with(condition, terminal, LEDGER_RULE_VALIDATION_REFUSAL_CODE)
    rule = result.rule
    return (
        rule is not None
        and rule.description_pattern == request.description_pattern
        and rule.classification is request.classification
        and rule.priority == request.priority
        and _succeeded(condition, terminal, OperationEffect.UPDATED)
    )


def rule_apply_matches(
    result: LedgerRuleApplyProjection,
    request: LedgerRuleApplyRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """A dry run only for a dry-run request, an applied run otherwise, or the declared refusal."""
    if result.profile_id != request.profile_id:
        return False
    if result.outcome == "validation_error":
        return _refused_with(
            condition,
            terminal,
            LEDGER_RULE_VALIDATION_REFUSAL_CODE,
            frozenset({OperationEffect.NONE, OperationEffect.PARTIAL}),
        )
    if (result.outcome == "dry_run") != request.dry_run:
        return False
    if result.outcome == "dry_run":
        return _succeeded(condition, terminal, OperationEffect.NONE)
    return _succeeded(condition, terminal, _effect_of(bool(result.bucket_event_count)))


def counterparty_matches(
    result: LedgerCounterpartyResult,
    request: LedgerCounterpartyRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The requested action on the requested counterparty; a lookup never changes anything."""
    return (
        result.profile_id == request.profile_id
        and result.action == request.action
        and result.tax_identifier == request.tax_identifier
        and not (request.action == "view" and result.changed)
        and _succeeded(condition, terminal, _effect_of(result.changed))
    )


def split_matches(
    result: LedgerSplitOperationResult,
    request: LedgerSplitRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The requested entry split into exactly the requested number of children."""
    return (
        result.profile_id == request.profile_id
        and _names_entry(result.parent_transaction_id, request.transaction_id)
        and len(result.child_transaction_ids) == len(request.children)
        and _succeeded(condition, terminal, OperationEffect.UPDATED)
    )


def allocate_matches(
    result: LedgerAllocateOperationResult,
    request: LedgerAllocateRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The requested entry carrying the requested business share."""
    return (
        result.profile_id == request.profile_id
        and _names_entry(result.transaction.transaction_id, request.transaction_id)
        and _succeeded(condition, terminal, _effect_of(bool(result.bucket_event_ids)))
    )


def participation_matches(
    result: LedgerParticipationProjection,
    request: LedgerParticipationRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The participations of the requested entry, read without effect."""
    return (
        result.profile_id == request.profile_id
        and result.transaction_prefix == request.transaction_prefix
        and _names_entry(result.transaction_id, request.transaction_prefix)
        and _succeeded(condition, terminal, OperationEffect.NONE)
    )


def participation_rebuild_matches(
    result: LedgerParticipationRebuildProjection,
    request: LedgerParticipationRebuildRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The replaced index of the requested profile."""
    return result.profile_id == request.profile_id and _succeeded(condition, terminal, OperationEffect.UPDATED)


def llm_diagnostics_matches(
    result: LedgerLlmDiagnosticsProjection,
    request: LedgerLlmDiagnosticsRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The report for exactly the requested range and threshold, read without effect."""
    return (
        result.profile_id == request.profile_id
        and result.since == request.since
        and result.until == request.until
        and result.low_confidence_threshold == request.low_confidence_threshold
        and _succeeded(condition, terminal, OperationEffect.NONE)
    )


def ratios_list_matches(
    result: LedgerRatiosListProjection,
    request: LedgerRatiosListRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The overrides of the requested year, or the declared census mismatch."""
    if result.profile_id != request.profile_id or result.year != request.year:
        return False
    if result.outcome == "censo_mismatch":
        return _refused_with(condition, terminal, LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE)
    return _succeeded(condition, terminal, OperationEffect.NONE)


def ratios_eligible_matches(
    result: LedgerRatiosEligibleProjection,
    request: LedgerRatiosEligibleRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The eligible categories of the requested year, read without effect."""
    return (
        result.profile_id == request.profile_id
        and result.year == request.year
        and _succeeded(condition, terminal, OperationEffect.NONE)
    )


def ratios_validate_matches(
    result: LedgerRatiosValidateProjection,
    request: LedgerRatiosValidateRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The validation report of the requested profile, read without effect."""
    return result.profile_id == request.profile_id and _succeeded(condition, terminal, OperationEffect.NONE)


def ratios_set_matches(
    result: LedgerRatiosSetProjection,
    request: LedgerRatiosSetRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The requested category now carrying the requested ratio."""
    return (
        result.profile_id == request.profile_id
        and result.requested_category == request.category
        and result.ratio == request.ratio
        and _succeeded(condition, terminal, OperationEffect.UPDATED)
    )


def ratios_unset_matches(
    result: LedgerRatiosUnsetProjection,
    request: LedgerRatiosUnsetRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """The requested category cleared, or the declared refusal that it had no override."""
    if result.profile_id != request.profile_id or result.requested_category != request.category:
        return False
    if result.outcome == "no_override":
        return _refused_with(condition, terminal, LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE)
    return _succeeded(condition, terminal, OperationEffect.UPDATED)


class RuntimeCategorisationTuiDoorV1[RequestT: BaseModel, ResultT: BaseModel]:
    """Submit one registered operation for the exact TUI profile and session this door was built for."""

    def __init__(
        self,
        session: RuntimeProfileSession,
        *,
        definition_id: str,
        result_type: type[ResultT],
        matches: ResultMatcher[RequestT, ResultT],
        allow_refusal_detail: bool = False,
    ) -> None:
        """Bind the pinned session, the operation and the receipt correlation its results must pass."""
        self._session = session
        self._definition_id = definition_id
        self._result_type = result_type
        self._matches = matches
        self._allow_refusal_detail = allow_refusal_detail

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def __call__(self, request: RequestT, /) -> ResultT:
        """Run one request and refuse a result its terminal receipt does not support."""

        def settle(
            result: ResultT,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not self._matches(result, request, condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=self._definition_id,
            result_type=self._result_type,
            settle=settle,
            allow_refusal_detail=self._allow_refusal_detail,
            explain_failure=True,
        )


def review_result_matches(
    result: LedgerLlmOperationResult,
    request: LedgerLlmReviewRequest,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """A decided review of the requested entry, its effect agreeing with what it wrote."""
    condition = terminal.terminal_condition
    unchanged = result.classification is not None and not result.classification.bucket_event_ids
    return (
        condition is not None
        and result.profile_id == request.profile_id
        and _names_entry(result.transaction_id, request.transaction_id)
        and result.outcome != "preview"
        and _succeeded(condition, terminal, OperationEffect.NONE if unchanged else OperationEffect.UPDATED)
    )


class RuntimeSuggestionReviewTuiDoorV1:
    """Start one review operation for the operation modal, and read its settled outcome."""

    def __init__(self, client: FrontendClient, session: RuntimeProfileSession, *, definition_id: str) -> None:
        """Bind the client, the pinned session and the one review definition this door submits."""
        if definition_id not in {LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, LEDGER_SPLIT_REVIEW_DEFINITION_ID}:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._client = client
        self._session = session
        self._definition_id = definition_id

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    def _subject(self) -> str:
        return profile_operation_subject(str(self._session.profile_id))

    async def submit(self, request: LedgerLlmReviewRequest) -> OperationControllerPort:
        """Submit and start one review of the admitted profile, still pinned to its session."""
        # The binding check reads the session over IPC; it never runs on the event loop.
        await asyncio.to_thread(self._session.require_binding)
        if request.profile_id != self._session.profile_id or ledger_llm_review_definition_id(request) != (
            self._definition_id
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        controller = await OperationController.submit(
            self._client,
            definition_id=self._definition_id,
            subject_ref=self._subject(),
            payload=request,
            expected_session_id=self._session.session_id,
        )
        try:
            await controller.start()
        except Exception as error:
            # The runtime accepted the review, so a lost start reply does not say it never ran.
            failure = await self._session.failure_after_submission(
                error,
                operation_id=str(controller.operation_id),
                contract=controller.definition_contract,
                terminal=None,
            )
            if failure is error:
                raise
            raise failure from error
        return controller

    async def read_result(
        self, request: LedgerLlmReviewRequest, projection: OperationPublicProjectionV1
    ) -> LedgerLlmOperationResult:
        """Read a settled review this door submitted and refuse one its receipt does not support.

        A result that cannot be read, or that its receipt does not support, is
        judged against that receipt: one that saved something leaves the
        outcome unknown rather than refused. The session and the receipt's
        identity are checked inside that judgement too: a session lost after a
        receipt that saved something leaves the outcome unknown as well.
        """
        try:
            await asyncio.to_thread(self._session.require_binding)
            if (
                projection.definition_id != self._definition_id
                or projection.subject_ref != self._subject()
                or projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            controller = OperationController(
                client=self._client, operation_id=projection.operation_id, session_id=self._session.session_id
            )
            result = await controller.read_settled_result(projection, LedgerLlmOperationResult, result_version=1)
            await asyncio.to_thread(self._session.require_binding)
            if not review_result_matches(result, request, projection):
                raise RefusalError(RefusalCode.INVALID_FRAME)
        except Exception as error:
            failure = await self._session.failure_after_submission(
                error,
                operation_id=projection.operation_id,
                contract=projection.definition_contract,
                terminal=projection,
            )
            if failure is error:
                raise
            raise failure from error
        return result


def compose_runtime_categorisation_doors(client: FrontendClient, profile_label: str) -> LedgerCategorisationDoorsV1:
    """Bind every categorisation door to one pinned session of the workbench's client."""
    session = RuntimeProfileSession(client, profile_label=profile_label)
    return LedgerCategorisationDoorsV1(
        selection=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_LIST_OPERATION_DEFINITION_ID,
            result_type=LedgerListProjection,
            matches=selection_matches,
        ),
        bulk_classify=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
            result_type=LedgerBulkClassifyProjection,
            matches=bulk_classify_matches,
            allow_refusal_detail=True,
        ),
        operator_iva=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_OPERATOR_IVA_DEFINITION_ID,
            result_type=LedgerOperatorIvaResult,
            matches=operator_iva_matches,
            allow_refusal_detail=True,
        ),
        classify_review=RuntimeSuggestionReviewTuiDoorV1(
            client, session, definition_id=LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
        ),
        split_review=RuntimeSuggestionReviewTuiDoorV1(client, session, definition_id=LEDGER_SPLIT_REVIEW_DEFINITION_ID),
        rule_list=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
            result_type=LedgerRuleListProjection,
            matches=rule_list_matches,
        ),
        rule_add=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
            result_type=LedgerRuleAddProjection,
            matches=rule_add_matches,
            allow_refusal_detail=True,
        ),
        rule_apply=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
            result_type=LedgerRuleApplyProjection,
            matches=rule_apply_matches,
            allow_refusal_detail=True,
        ),
        counterparty=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
            result_type=LedgerCounterpartyResult,
            matches=counterparty_matches,
        ),
        split=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_SPLIT_OPERATION_DEFINITION_ID,
            result_type=LedgerSplitOperationResult,
            matches=split_matches,
        ),
        allocate=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
            result_type=LedgerAllocateOperationResult,
            matches=allocate_matches,
        ),
        participation=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID,
            result_type=LedgerParticipationProjection,
            matches=participation_matches,
        ),
        participation_rebuild=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
            result_type=LedgerParticipationRebuildProjection,
            matches=participation_rebuild_matches,
        ),
        llm_diagnostics=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
            result_type=LedgerLlmDiagnosticsProjection,
            matches=llm_diagnostics_matches,
        ),
        ratios_list=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
            result_type=LedgerRatiosListProjection,
            matches=ratios_list_matches,
            allow_refusal_detail=True,
        ),
        ratios_eligible=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID,
            result_type=LedgerRatiosEligibleProjection,
            matches=ratios_eligible_matches,
        ),
        ratios_validate=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID,
            result_type=LedgerRatiosValidateProjection,
            matches=ratios_validate_matches,
        ),
        ratios_set=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
            result_type=LedgerRatiosSetProjection,
            matches=ratios_set_matches,
        ),
        ratios_unset=RuntimeCategorisationTuiDoorV1(
            session,
            definition_id=LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
            result_type=LedgerRatiosUnsetProjection,
            matches=ratios_unset_matches,
            allow_refusal_detail=True,
        ),
    )


def compose_categorisation_tools(client: FrontendClient, profile_label: str) -> tuple[LedgerToolV1, ...]:
    """The categorisation tools of the workbench's admitted profile, every door on one pinned session."""
    return categorisation_tools(compose_runtime_categorisation_doors(client, profile_label))


__all__ = [
    "RuntimeCategorisationTuiDoorV1",
    "RuntimeSuggestionReviewTuiDoorV1",
    "allocate_matches",
    "bulk_classify_matches",
    "compose_categorisation_tools",
    "compose_runtime_categorisation_doors",
    "counterparty_matches",
    "llm_diagnostics_matches",
    "operator_iva_matches",
    "participation_matches",
    "participation_rebuild_matches",
    "ratios_eligible_matches",
    "ratios_list_matches",
    "ratios_set_matches",
    "ratios_unset_matches",
    "ratios_validate_matches",
    "review_result_matches",
    "rule_add_matches",
    "rule_apply_matches",
    "rule_list_matches",
    "selection_matches",
    "split_matches",
]
