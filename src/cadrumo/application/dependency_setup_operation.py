"""The registered setup operations: status, setup with plan approval, and verification.

``dependencies.status`` reads every item's state through the registry, quickly
(local facts only) or fully (network and exercise). ``dependencies.verify``
runs the full check of named items. ``dependencies.setup`` is the only
operation that downloads or installs anything:

1. It plans the selected items -- every item that is not ready, by default --
   and raises one REVIEW interaction carrying the plan's digest. Nothing moves
   before the person applies exactly that plan.
2. On approval it plans again. A plan whose digest changed refuses, because the
   approval was for something else. Free space on each destination is checked
   against the plan.
3. Items then run one at a time in setup order, each under its own lock: a
   network preflight of its hosts, the item's provisioner, and an independent
   full check that alone decides readiness.

Progress is published per item with the item as its subject, at most once per
500 ms and only on a change of at least one percent. Retries are announced as
notices before their wait. Cancellation is honoured between steps and inside
transfers; a provisioner keeps what it already downloaded. When the supervisor
resumes an approved setup after losing its owner, the downloads had already
begun, so the setup ends as interrupted and leaves Resume to the person.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Callable, Iterable
from contextlib import AbstractAsyncContextManager
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, NonNegativeInt, StringConstraints

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.operation_ids import DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID

from ..core.external_constants import OutputLanguage
from ..core.hashing import content_hash_hex
from ..core.identity.digest import ContentDigest
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_path
from ..core.time.clock import now
from .dependency_activity import DependencyActivityStore, DependencyFailureRecord, DependencyStepRecord
from .dependency_contracts import (
    DEPENDENCY_PROGRESS_UNIT_CODE,
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemFinisher,
    DependencyItemId,
    DependencyItemKind,
    DependencyPartId,
    DependencyPlanEntry,
    DependencyProvisionResult,
    DependencySetupPlan,
    DependencySetupStep,
    DependencySpaceCheck,
    DependencyState,
    DependencyStatusRow,
    dependency_phase_code,
    dependency_plan_digest,
    dependency_progress_subject,
    dependency_retry_notice_code,
    known_download_bytes_of,
    known_part_bytes_of,
    required_free_bytes,
)
from .dependency_receipts import dependency_receipts_root
from .dependency_registry import (
    DependencyRegistry,
    DependencySelectionError,
    build_setup_plan,
    dependency_item_declarations,
    is_setup_complete,
)
from .dependency_transfer import (
    DependencyItemLockedError,
    DependencyTransferError,
    dependency_item_lock,
    measure_free_bytes,
)
from .dependency_wording import DependencyWordingV1, dependency_part_name, dependency_wording_view
from .local_reader_operation import bind_machine_provisioning_access
from .operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from .operations.capabilities import (
    RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .operations.interactions import (
    OperationConsumedInteraction,
    OperationInteractionRequest,
    OperationResponseIntentValue,
)
from .operations.models import (
    CredentialFreeOperationRequest,
    OperationIdentity,
    OperationRequest,
    OperationRevision,
)
from .operations.operation_definition import (
    OperationDefinition,
    OperationExecutorFactory,
    build_single_phase_definition,
)
from .operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from .operations.refusal_evidence import OperationExecutorResult
from .operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
    operation_public_schema_reference,
)
from .operations.subject_reference import OperationSubjectReferenceV1
from .provisioning import model_licence_notice
from .user_profile.access_errors import ProfileAccessRefusedError

__all__ = [
    "DEPENDENCIES_OPERATION_SUBJECT",
    "DEPENDENCIES_SETUP_PLAN_PHASE",
    "DEPENDENCIES_SETUP_RESPONSE_SCHEMA",
    "DEPENDENCIES_SETUP_REVIEW_SCHEMA",
    "DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID",
    "DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID",
    "DEPENDENCY_PROGRESS_INTERVAL_S",
    "DependencyPlanEntryViewV1",
    "DependencyPlanPartViewV1",
    "DependencyRegistryFactory",
    "DependencySetupExecutor",
    "DependencySetupItemResultV1",
    "DependencySetupOutcome",
    "DependencySetupProposal",
    "DependencySetupRequest",
    "DependencySetupResponseV1",
    "DependencySetupResultV1",
    "DependencySetupReviewV2",
    "DependencyStatusRequest",
    "DependencyStatusResultV1",
    "DependencyVerifyRequest",
    "build_dependency_operation_definitions",
    "build_dependency_operation_registrations",
    "dependency_setup_effect",
]

DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID: Final = "dependencies.status"
DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID: Final = "dependencies.verify"
DEPENDENCIES_OPERATION_SUBJECT: Final = "dependencies:installation"
DEPENDENCIES_SETUP_PLAN_PHASE: Final = "dependencies.setup.plan"
DEPENDENCY_PROGRESS_INTERVAL_S: Final = 0.5
_PROGRESS_MIN_PERCENT_CHANGE: Final = 1.0
_REVIEW_LIFETIME: Final = timedelta(hours=1)
_REVIEW_PRESENTATION_CODE: Final = "dependencies.setup.review"

type DependencyRegistryFactory = Callable[[OperationIdentity, asyncio.AbstractEventLoop], DependencyRegistry]
"""Builds the registry for one invocation, binding ports that act on behalf of that operation."""

type _ModelName = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
]


# ── Requests ────────────────────────────────────────────────────────────────


class DependencyStatusRequest(CredentialFreeOperationRequest):
    """One status read: ``quick`` reads local facts only, ``full`` also reaches the network and exercises items.

    ``locale`` names the language of the result's words; without one they
    follow the configured output language. Every request below takes it too.
    """

    mode: DependencyCheckMode = DependencyCheckMode.QUICK
    locale: OutputLanguage | None = None


class DependencyVerifyRequest(CredentialFreeOperationRequest):
    """Fully check the named items, every item when none is named."""

    item_ids: tuple[DependencyItemId, ...] | None = None
    locale: OutputLanguage | None = None


class DependencySetupRequest(CredentialFreeOperationRequest):
    """Set up the named items, every item that is not ready when none is named.

    ``model_name`` asks for one catalogue model instead of the ones Cadrumo
    would choose; it applies to every role's model of the local AI.
    """

    item_ids: tuple[DependencyItemId, ...] | None = None
    model_name: _ModelName | None = None
    locale: OutputLanguage | None = None


# ── Results ─────────────────────────────────────────────────────────────────


class DependencyStatusResultV1(BaseModel):
    """Every requested item's derived row, in setup order, and whether Cadrumo is set up."""

    model_config = STRICT_FROZEN_CONFIG

    mode: DependencyCheckMode
    rows: tuple[DependencyStatusRow, ...]
    complete: bool
    hardware_limited: bool
    wording: DependencyWordingV1 | None = None


class DependencySetupOutcome(StrEnum):
    """How a setup ended as a whole; each item's own result says how it ended."""

    COMPLETED = "completed"
    NOTHING_TO_DO = "nothing_to_do"
    REJECTED = "rejected"
    PLAN_CHANGED = "plan_changed"
    NOT_ENOUGH_SPACE = "not_enough_space"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


class DependencySetupItemResultV1(BaseModel):
    """One item's setup result: what changed, and the failure category when it did not end usable."""

    model_config = STRICT_FROZEN_CONFIG

    item_id: DependencyItemId
    changed: bool
    failure_category: DependencyFailureCategory | None = None
    transferred_bytes: NonNegativeInt = 0


class DependencySetupResultV1(BaseModel):
    """The settled result of one setup.

    ``rows`` is a fresh quick status of every item after the setup, so a
    frontend shows the new state without a second read. ``wording`` words
    them, with the details of this setup's phases and hosts.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: DependencySetupOutcome
    plan_digest: ContentDigest | None = None
    items: tuple[DependencySetupItemResultV1, ...] = ()
    space: DependencySpaceCheck | None = None
    rows: tuple[DependencyStatusRow, ...]
    complete: bool
    wording: DependencyWordingV1 | None = None


# ── Review ──────────────────────────────────────────────────────────────────


class DependencySetupProposal(BaseModel):
    """The exact plan a person approves, bound to one invocation and revision."""

    model_config = STRICT_FROZEN_CONFIG

    identity: OperationIdentity
    revision: OperationRevision
    request: DependencySetupRequest
    plan: DependencySetupPlan

    @property
    def digest(self) -> ContentDigest:
        """Bind the approval to the plan, the request and the operation identity."""
        return content_hash_hex(self.model_dump(mode="json"))


class DependencyPlanPartViewV1(BaseModel):
    """One part of a plan entry as a person reviews it: its plain name and how large it is."""

    model_config = STRICT_FROZEN_CONFIG

    part_id: DependencyPartId
    name: str
    download_bytes: NonNegativeInt | None


class DependencyPlanEntryViewV1(BaseModel):
    """One plan entry as a person reviews it: what, how large, from where, and where it is stored.

    ``parts`` names each part of an item planned in parts, in the order setup
    carries them out; a part sharing an earlier part's download shows no size.
    """

    model_config = STRICT_FROZEN_CONFIG

    entry: DependencyPlanEntry
    destination_path: str | None
    shares_download_with: DependencyItemId | None = None
    licence_notice: str | None = None
    parts: tuple[DependencyPlanPartViewV1, ...] = ()


class DependencySetupReviewV2(BaseModel):
    """The REVIEW projection of a setup plan."""

    model_config = STRICT_FROZEN_CONFIG

    identity: OperationIdentity
    revision: OperationRevision
    plan_digest: ContentDigest
    entries: tuple[DependencyPlanEntryViewV1, ...]
    known_download_bytes: NonNegativeInt
    has_unknown_size: bool
    installs_outside_program: bool
    space: DependencySpaceCheck
    space_sufficient: bool
    reviewed_proposal_digest: ContentDigest
    wording: DependencyWordingV1 | None = None


class DependencySetupResponseV1(BaseModel):
    """The person's answer to a setup plan; only the runtime's consumed response grants authority."""

    model_config = STRICT_FROZEN_CONFIG

    response_version: Literal[1] = 1
    intent: OperationResponseIntentValue


DEPENDENCIES_SETUP_REVIEW_SCHEMA: Final = OperationSchemaBindingV1.bind(
    schema_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID + ".review",
    schema_version=2,
    model_type=DependencySetupReviewV2,
)
DEPENDENCIES_SETUP_RESPONSE_SCHEMA: Final = OperationSchemaBindingV1.bind(
    schema_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID + ".response",
    schema_version=1,
    model_type=DependencySetupResponseV1,
)


# ── Shared reads ────────────────────────────────────────────────────────────


def _activity_store() -> DependencyActivityStore:
    return DependencyActivityStore(dependency_receipts_root())


async def _read_status(
    registry: DependencyRegistry,
    mode: DependencyCheckMode,
    *,
    item_ids: tuple[str, ...] | None = None,
) -> tuple[DependencyStatusRow, ...]:
    store = _activity_store()
    identities = tuple(declaration.item_id for declaration in registry.declarations)
    activities = await asyncio.to_thread(store.activities, identities)
    failures = await asyncio.to_thread(store.failures, identities)
    return await registry.read_rows(mode, item_ids=item_ids, activities=activities, last_failures=failures)


def _locale(language: OutputLanguage | None) -> str | None:
    return None if language is None else language.value


def _status_result(
    registry: DependencyRegistry,
    mode: DependencyCheckMode,
    rows: tuple[DependencyStatusRow, ...],
    language: OutputLanguage | None,
) -> DependencyStatusResultV1:
    return DependencyStatusResultV1(
        mode=mode,
        rows=rows,
        complete=is_setup_complete(rows),
        hardware_limited=any(row.blocked_reason is DependencyBlockedReason.HARDWARE for row in rows),
        wording=dependency_wording_view(rows, registry.declarations, locale=_locale(language)),
    )


def _require_subject(subject_ref: str) -> None:
    if subject_ref != DEPENDENCIES_OPERATION_SUBJECT:
        raise ValueError("dependency operation subject must name the installation")


# ── Status and verify ───────────────────────────────────────────────────────


class DependencyStatusExecutor:
    """Read every item's state; nothing is downloaded, installed or written."""

    def __init__(self, registry_factory: DependencyRegistryFactory) -> None:
        """Bind the per-invocation registry factory."""
        self._registry_factory = registry_factory

    async def execute(
        self, request: OperationRequest[DependencyStatusRequest], context: OperationExecutorContext
    ) -> str:
        """Check every item in the requested mode and persist the rows."""
        _require_subject(request.subject_ref)
        await context.events.phase(DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        registry = self._registry_factory(context.identity, asyncio.get_running_loop())
        mode = request.payload.mode
        rows = await _read_status(registry, mode)
        return await context.operands.put(
            _status_result(registry, mode, rows, request.payload.locale), written_at=now()
        )


class DependencyVerifyExecutor:
    """Fully check the named items; nothing is downloaded, installed or written."""

    def __init__(self, registry_factory: DependencyRegistryFactory) -> None:
        """Bind the per-invocation registry factory."""
        self._registry_factory = registry_factory

    async def execute(
        self, request: OperationRequest[DependencyVerifyRequest], context: OperationExecutorContext
    ) -> str:
        """Run the full check of the named items and persist the rows."""
        _require_subject(request.subject_ref)
        await context.events.phase(DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        registry = self._registry_factory(context.identity, asyncio.get_running_loop())
        rows = await _read_status(registry, DependencyCheckMode.FULL, item_ids=request.payload.item_ids)
        return await context.operands.put(
            _status_result(registry, DependencyCheckMode.FULL, rows, request.payload.locale), written_at=now()
        )


# ── Setup ───────────────────────────────────────────────────────────────────


class _ItemEvents:
    """The per-item event port a provisioner reports through, bound to the journal."""

    def __init__(
        self,
        context: OperationExecutorContext,
        item_id: str,
        store: DependencyActivityStore,
        *,
        phases: list[str] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._context = context
        self._item_id = item_id
        self._store = store
        self._phases: list[str] = [] if phases is None else phases
        self._monotonic = monotonic
        self._last_at: float | None = None
        self._last_percent: float | None = None

    async def step(self, step: DependencySetupStep) -> None:
        await asyncio.to_thread(
            self._store.record_step,
            DependencyStepRecord(item_id=self._item_id, operation_id=self._context.identity.operation_id, step=step),
        )
        phase = dependency_phase_code(self._item_id, step)
        self._phases.append(phase)
        await self._context.events.phase(phase)
        self._last_at = None
        self._last_percent = None

    async def transferred(self, *, completed: int, total: int | None) -> None:
        if total is None or total <= 0:
            return
        completed = max(0, min(completed, total))
        percent = completed * 100.0 / total
        moment = self._monotonic()
        finished = completed == total
        if not finished and self._last_at is not None and self._last_percent is not None:
            if moment - self._last_at < DEPENDENCY_PROGRESS_INTERVAL_S:
                return
            if percent - self._last_percent < _PROGRESS_MIN_PERCENT_CHANGE:
                return
        if finished and self._last_percent == 100.0:
            return
        self._last_at = moment
        self._last_percent = percent
        await self._context.events.progress(
            completed=completed,
            total=total,
            unit_code=DEPENDENCY_PROGRESS_UNIT_CODE,
            subject_code=dependency_progress_subject(self._item_id),
        )

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        await self._context.events.notice(dependency_retry_notice_code(self._item_id, attempt=attempt, delay_s=delay_s))

    @property
    def cancellation_requested(self) -> bool:
        return self._context.cancellation.cancellation_requested

    def irreversible(self) -> AbstractAsyncContextManager[None]:
        return self._context.cancellation.irreversible_section()


def dependency_setup_effect(items: Iterable[DependencySetupItemResultV1]) -> OperationEffect:
    """Return the committed extent of a setup: updated when every changed item ended usable."""
    settled = tuple(items)
    changed = [item for item in settled if item.changed]
    if not changed:
        return OperationEffect.NONE
    if any(item.failure_category is not None for item in changed):
        return OperationEffect.PARTIAL
    return OperationEffect.UPDATED


def _destination_path(category: StorageCategory | None) -> Path | None:
    return None if category is None else storage_path(category)


def _space_check(entries: tuple[DependencyPlanEntry, ...]) -> DependencySpaceCheck:
    """Measure the tightest destination volume against everything the plan downloads.

    Every destination lives under the one storage root unless an operator
    moved it, so the whole plan is held against the destination with the
    least free space: that is the volume most likely to run out.
    """
    destinations = {entry.destination for entry in entries if entry.destination is not None}
    measured = [measure_free_bytes(path) for category in destinations if (path := _destination_path(category))]
    free = (
        None if not measured or any(value is None for value in measured) else min(v for v in measured if v is not None)
    )
    return DependencySpaceCheck(free_bytes=free, required_bytes=required_free_bytes(known_download_bytes_of(entries)))


class DependencySetupExecutor:
    """Plan, ask the person, then set the approved items up one at a time and verify each independently."""

    def __init__(self, registry_factory: DependencyRegistryFactory) -> None:
        """Bind the per-invocation registry factory."""
        self._registry_factory = registry_factory

    def _registry(self, context: OperationExecutorContext) -> DependencyRegistry:
        return self._registry_factory(context.identity, asyncio.get_running_loop())

    async def _plan(
        self, registry: DependencyRegistry, request: DependencySetupRequest, item_ids: tuple[str, ...]
    ) -> DependencySetupPlan:
        entries: list[DependencyPlanEntry] = []
        for item_id in item_ids:
            declaration = registry.declaration(item_id)
            model = request.model_name if declaration.kind is DependencyItemKind.LOCAL_AI else None
            entries.append(await registry.provisioner(item_id).plan(model_name=model))
        space = _space_check(tuple(entries))
        return build_setup_plan(entries, free_bytes=space.free_bytes)

    async def _plan_unless_withheld(
        self,
        registry: DependencyRegistry,
        request: DependencySetupRequest,
        rows: Iterable[DependencyStatusRow],
        item_ids: tuple[str, ...],
    ) -> DependencySetupPlan | tuple[DependencySetupItemResultV1, ...]:
        """Return the plan for ``item_ids``, or a no-change refusal per item when this build cannot set them up."""
        withheld = _withheld_items(rows, item_ids)
        if withheld:
            return withheld
        try:
            return await self._plan(registry, request, item_ids)
        except DependencyTransferError as error:
            if error.category is not DependencyFailureCategory.NOT_IN_THIS_BUILD:
                raise
            return _not_in_this_build(item_ids)

    async def _settled(
        self,
        context: OperationExecutorContext,
        registry: DependencyRegistry,
        outcome: DependencySetupOutcome,
        language: OutputLanguage | None,
        *,
        plan: DependencySetupPlan | None = None,
        items: tuple[DependencySetupItemResultV1, ...] = (),
        effect: OperationEffect | None = None,
        phases: Iterable[str] = (DEPENDENCIES_SETUP_PLAN_PHASE,),
    ) -> str:
        rows = await _read_status(registry, DependencyCheckMode.QUICK)
        wording = dependency_wording_view(
            rows,
            registry.declarations,
            locale=_locale(language),
            operation_id=context.identity.operation_id,
            phases=phases,
            hosts=() if plan is None else (host for entry in plan.entries for host in entry.source_hosts),
        )
        result = DependencySetupResultV1(
            outcome=outcome,
            plan_digest=None if plan is None else dependency_plan_digest(plan),
            items=items,
            space=None if plan is None else plan.space,
            rows=rows,
            complete=is_setup_complete(rows),
            wording=wording,
        )
        await context.events.effect(dependency_setup_effect(items) if effect is None else effect)
        return await context.operands.put(result, written_at=now())

    async def execute(
        self, request: OperationRequest[DependencySetupRequest], context: OperationExecutorContext
    ) -> OperationExecutorResult:
        """Plan the selected items and raise the plan for the person's approval."""
        _require_subject(request.subject_ref)
        await context.events.phase(DEPENDENCIES_SETUP_PLAN_PHASE)
        await context.events.effect(OperationEffect.NONE)
        registry = self._registry(context)
        payload = request.payload
        rows = await _read_status(registry, DependencyCheckMode.QUICK)
        try:
            selected = registry.select_setup_items(rows, requested=payload.item_ids)
        except DependencySelectionError as error:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from error
        if not selected:
            return await self._settled(context, registry, DependencySetupOutcome.NOTHING_TO_DO, payload.locale)
        planned = await self._plan_unless_withheld(
            registry, payload, rows, tuple(declaration.item_id for declaration in selected)
        )
        if not isinstance(planned, DependencySetupPlan):
            return await self._settled(
                context,
                registry,
                DependencySetupOutcome.NOTHING_TO_DO,
                payload.locale,
                items=planned,
                effect=OperationEffect.NONE,
            )
        plan = planned
        proposal = DependencySetupProposal(
            identity=context.identity, revision=context.revision + 1, request=payload, plan=plan
        )
        await context.interactions.publish_review(
            interaction_id=secrets.token_hex(32),
            identity=context.identity,
            revision=proposal.revision,
            presentation_code=_REVIEW_PRESENTATION_CODE,
            response_schema_ref=operation_public_schema_reference(DEPENDENCIES_SETUP_RESPONSE_SCHEMA.identity),
            continuation_digest=proposal.digest,
            expires_at=now() + _REVIEW_LIFETIME,
            reviewed_operand=proposal,
            baseline_digest=content_hash_hex(payload.model_dump(mode="json")),
            proposed_effect_digest=dependency_plan_digest(plan),
        )
        return None

    async def resume(
        self,
        request: OperationRequest[DependencySetupRequest],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> OperationExecutorResult:
        """Carry out the approved plan, or settle without effect when it was rejected or changed."""
        _require_subject(request.subject_ref)
        registry = self._registry(context)
        if type(checkpoint) is not OperationConsumedInteraction:
            # Only owner-loss recovery resumes an unanswered plan. Its answer
            # cannot be transferred to a new session, so this setup ends and
            # a new submit asks again.
            return await self._settled(
                context,
                registry,
                DependencySetupOutcome.INTERRUPTED,
                request.payload.locale,
                effect=OperationEffect.NONE,
            )
        consumed = OperationConsumedInteraction.model_validate(checkpoint.model_dump(mode="python"), strict=True)
        proposal = await context.operands.resolve(consumed.reviewed_proposal_digest, DependencySetupProposal)
        _require_approved(consumed, proposal, request, context)
        language = request.payload.locale
        if consumed.response_action != "apply":
            return await self._settled(context, registry, DependencySetupOutcome.REJECTED, language, plan=proposal.plan)
        store = _activity_store()
        item_ids = tuple(entry.item_id for entry in proposal.plan.entries)
        if not await asyncio.to_thread(store.mark_run, context.identity.operation_id):
            failures = tuple(
                DependencySetupItemResultV1(
                    item_id=item_id, changed=False, failure_category=DependencyFailureCategory.INTERRUPTED
                )
                for item_id in item_ids
            )
            for failure in failures:
                await asyncio.to_thread(
                    store.record_failure,
                    _failure_record(context, failure.item_id, DependencyFailureCategory.INTERRUPTED),
                )
            await asyncio.to_thread(store.clear_run, context.identity.operation_id)
            return await self._settled(
                context,
                registry,
                DependencySetupOutcome.INTERRUPTED,
                language,
                plan=proposal.plan,
                items=failures,
                effect=OperationEffect.UNKNOWN,
            )
        try:
            return await self._carry_out(context, registry, store, proposal)
        finally:
            await asyncio.to_thread(store.clear_run, context.identity.operation_id)

    async def _carry_out(
        self,
        context: OperationExecutorContext,
        registry: DependencyRegistry,
        store: DependencyActivityStore,
        proposal: DependencySetupProposal,
    ) -> OperationExecutorResult:
        approved = proposal.plan
        language = proposal.request.locale
        item_ids = tuple(entry.item_id for entry in approved.entries)
        await context.events.phase(DEPENDENCIES_SETUP_PLAN_PHASE)
        rows = await _read_status(registry, DependencyCheckMode.QUICK)
        current = await self._plan_unless_withheld(registry, proposal.request, rows, item_ids)
        if not isinstance(current, DependencySetupPlan):
            return await self._settled(
                context,
                registry,
                DependencySetupOutcome.NOTHING_TO_DO,
                language,
                plan=approved,
                items=current,
                effect=OperationEffect.NONE,
            )
        if dependency_plan_digest(current) != dependency_plan_digest(approved):
            return await self._settled(context, registry, DependencySetupOutcome.PLAN_CHANGED, language, plan=current)
        if not current.space.sufficient:
            return await self._settled(
                context, registry, DependencySetupOutcome.NOT_ENOUGH_SPACE, language, plan=current
            )
        phases = [DEPENDENCIES_SETUP_PLAN_PHASE]
        results: list[DependencySetupItemResultV1] = []
        for entry in approved.entries:
            if context.cancellation.cancellation_requested:
                break
            result = await self._run_item(context, registry, store, entry, phases)
            results.append(result)
            await context.events.effect(_running_effect(results))
            if result.failure_category is DependencyFailureCategory.CANCELLED:
                break
        if context.cancellation.cancellation_requested:
            await asyncio.to_thread(store.clear_run, context.identity.operation_id)
            await context.events.effect(dependency_setup_effect(results))
            await context.cancellation.acknowledge_cancellation()
            return None
        return await self._settled(
            context,
            registry,
            DependencySetupOutcome.COMPLETED,
            language,
            plan=approved,
            items=tuple(results),
            phases=phases,
        )

    async def _run_item(
        self,
        context: OperationExecutorContext,
        registry: DependencyRegistry,
        store: DependencyActivityStore,
        entry: DependencyPlanEntry,
        phases: list[str],
    ) -> DependencySetupItemResultV1:
        item_id = entry.item_id
        events = _ItemEvents(context, item_id, store, phases=phases)
        try:
            with dependency_item_lock(store.root, item_id):
                try:
                    outcome = await self._provision_and_verify(context, registry, entry, events)
                finally:
                    await asyncio.to_thread(store.clear_step, item_id)
        except DependencyItemLockedError:
            outcome = DependencySetupItemResultV1(
                item_id=item_id, changed=False, failure_category=DependencyFailureCategory.UNEXPECTED
            )
        if outcome.failure_category is None:
            await asyncio.to_thread(store.clear_failure, item_id)
        else:
            await asyncio.to_thread(store.record_failure, _failure_record(context, item_id, outcome.failure_category))
        return outcome

    async def _provision_and_verify(
        self,
        context: OperationExecutorContext,
        registry: DependencyRegistry,
        entry: DependencyPlanEntry,
        events: _ItemEvents,
    ) -> DependencySetupItemResultV1:
        item_id = entry.item_id
        await events.step(DependencySetupStep.PREFLIGHT)
        failure = await registry.preflight(entry.source_hosts)
        if failure is not None:
            return DependencySetupItemResultV1(item_id=item_id, changed=False, failure_category=failure)
        await context.events.effect(OperationEffect.UNKNOWN)
        try:
            provisioned = await registry.provisioner(item_id).provision(entry, events)
        except DependencyTransferError as error:
            provisioned = DependencyProvisionResult(item_id=item_id, changed=True, failure_category=error.category)
        if provisioned.item_id != item_id:
            raise ValueError("provisioner answered for another setup item")
        if provisioned.failure_category is not None:
            return _item_result(provisioned, provisioned.failure_category)
        await events.step(DependencySetupStep.VERIFY)
        (row,) = await registry.read_rows(DependencyCheckMode.FULL, item_ids=(item_id,))
        failure = _verification_failure(row)
        provisioner = registry.provisioner(item_id)
        if failure is None and isinstance(provisioner, DependencyItemFinisher):
            if context.cancellation.cancellation_requested:
                return _item_result(provisioned, None)
            await events.step(DependencySetupStep.CLEANUP)
            async with context.cancellation.irreversible_section():
                await provisioner.after_verified(entry)
        return _item_result(provisioned, failure)


def _item_result(
    provisioned: DependencyProvisionResult, failure: DependencyFailureCategory | None
) -> DependencySetupItemResultV1:
    return DependencySetupItemResultV1(
        item_id=provisioned.item_id,
        changed=provisioned.changed,
        failure_category=failure,
        transferred_bytes=provisioned.transferred_bytes,
    )


def _withheld_items(
    rows: Iterable[DependencyStatusRow], item_ids: tuple[str, ...]
) -> tuple[DependencySetupItemResultV1, ...]:
    """Return a refusal for each of ``item_ids`` this build cannot set up, which nothing may plan or download."""
    blocked = {row.item_id for row in rows if row.blocked_reason is DependencyBlockedReason.NOT_IN_THIS_BUILD}
    return _not_in_this_build(tuple(item_id for item_id in item_ids if item_id in blocked))


def _not_in_this_build(item_ids: tuple[str, ...]) -> tuple[DependencySetupItemResultV1, ...]:
    """Return a no-change refusal for each of ``item_ids``, for an item this build cannot set up."""
    return tuple(
        DependencySetupItemResultV1(
            item_id=item_id, changed=False, failure_category=DependencyFailureCategory.NOT_IN_THIS_BUILD
        )
        for item_id in item_ids
    )


def _verification_failure(row: DependencyStatusRow) -> DependencyFailureCategory | None:
    """Readiness comes from the independent full check alone; an installer's word never decides it."""
    if row.state in {DependencyState.READY, DependencyState.STALE}:
        return None
    if row.failure_category is not None:
        return row.failure_category
    if row.blocked_reason is DependencyBlockedReason.OFFLINE:
        return DependencyFailureCategory.OFFLINE
    if row.blocked_reason is DependencyBlockedReason.NOT_IN_THIS_BUILD:
        return DependencyFailureCategory.NOT_IN_THIS_BUILD
    if row.blocked_reason is DependencyBlockedReason.HARDWARE:
        return DependencyFailureCategory.NOT_ENOUGH_MEMORY
    if row.state is DependencyState.ABSENT:
        return DependencyFailureCategory.DAMAGED_DOWNLOAD
    return DependencyFailureCategory.UNEXPECTED


def _running_effect(results: list[DependencySetupItemResultV1]) -> OperationEffect:
    return dependency_setup_effect(results)


def _failure_record(
    context: OperationExecutorContext, item_id: str, category: DependencyFailureCategory
) -> DependencyFailureRecord:
    return DependencyFailureRecord(
        item_id=item_id, operation_id=context.identity.operation_id, category=category, recorded_at=now()
    )


def _require_approved(
    consumed: OperationConsumedInteraction,
    proposal: DependencySetupProposal,
    request: OperationRequest[DependencySetupRequest],
    context: OperationExecutorContext,
) -> None:
    """Refuse a substituted proposal or a checkpoint that does not belong to this invocation."""
    pending = consumed.checkpoint
    if (
        proposal.identity != context.identity
        or proposal.request != request.payload
        or pending.request.identity != proposal.identity
        or pending.request.revision != proposal.revision
        or proposal.revision > context.revision
        or pending.request.continuation_digest != proposal.digest
        or pending.proposed_effect_digest != dependency_plan_digest(proposal.plan)
        or pending.baseline_digest != content_hash_hex(request.payload.model_dump(mode="json"))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)


# ── Definitions and registrations ───────────────────────────────────────────


def _setup_phase_codes() -> tuple[str, ...]:
    codes = [DEPENDENCIES_SETUP_PLAN_PHASE]
    for declaration in dependency_item_declarations():
        codes.extend(dependency_phase_code(declaration.item_id, step) for step in DependencySetupStep)
    return tuple(codes)


_SETUP_CAPABILITIES: Final = OperationCapabilities(
    durability=OperationDurability.RESUMABLE,
    cancellation=OperationCancellation.COOPERATIVE,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.RESUMABLE,
    baseline=OperationBaselinePolicy.EXACT_APPROVAL,
    request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    # Several items install in turn, so a failed run can leave some installed.
    permitted_effects=frozenset(OperationEffect),
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)


def build_dependency_operation_definitions(
    registry_factory: DependencyRegistryFactory,
) -> tuple[OperationDefinition, OperationDefinition, OperationDefinition]:
    """Bind the registry factory to the setup, status and verify operations, in definition-id order."""
    subject = OperationSubjectReferenceV1.fixed(DEPENDENCIES_OPERATION_SUBJECT)
    status = build_single_phase_definition(
        definition_id=DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
        request_type=DependencyStatusRequest,
        subject_reference=subject,
        result_type=DependencyStatusResultV1,
        executor_type=DependencyStatusExecutor,
        build=lambda: DependencyStatusExecutor(registry_factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )
    verify = build_single_phase_definition(
        definition_id=DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID,
        request_type=DependencyVerifyRequest,
        subject_reference=subject,
        result_type=DependencyStatusResultV1,
        executor_type=DependencyVerifyExecutor,
        build=lambda: DependencyVerifyExecutor(registry_factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )
    setup = OperationDefinition(
        definition_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
        request_type=DependencySetupRequest,
        subject_reference=subject,
        result_type=DependencySetupResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=DependencySetupRequest,
            executor_type=DependencySetupExecutor,
            build=lambda: DependencySetupExecutor(registry_factory),
        ),
        phase_codes=_setup_phase_codes(),
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=_SETUP_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
    )
    return setup, status, verify


def _resolve_status_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    return bind_machine_provisioning_access(
        request,
        context,
        definition_id=DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
        payload_type=DependencyStatusRequest,
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
        commits=lambda _payload: False,
    )


def _resolve_verify_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    return bind_machine_provisioning_access(
        request,
        context,
        definition_id=DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID,
        payload_type=DependencyVerifyRequest,
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
        commits=lambda _payload: False,
    )


_REVIEW_ACTIONS: Final = frozenset({AccessAction.REVIEW, AccessAction.RESPOND})


def _resolve_setup_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind machine access with COMMIT, REVIEW and RESPOND; any admitted session may answer the plan.

    The plan carries no taxpayer data. An agent session answers the same
    review a person does, through the same interaction, so the agent column
    refuses nothing the command line can do; in the desktop the person's
    approval of that tool call is the gesture.
    """
    resolved = bind_machine_provisioning_access(
        request,
        context,
        definition_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
        payload_type=DependencySetupRequest,
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
        commits=lambda _payload: True,
    )
    disclosures = resolved.policy.disclosures
    if context.action in _REVIEW_ACTIONS:
        schema = context.contract.review_projection_schema
        if schema is None or context.contract.interaction_response_schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            )
        )
    policy = OperationAccessPolicy.model_validate(
        {
            **dict(resolved.policy),
            "actions": resolved.policy.actions | _REVIEW_ACTIONS,
            "disclosures": disclosures,
        }
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def _licence_notice(entry: DependencyPlanEntry, locale: str | None) -> str | None:
    """Return the licence notices of every model the entry plans, each said once."""
    if not entry.parts:
        return model_licence_notice(entry.target_version, entry.advisories, locale=locale)
    notices = (model_licence_notice(part.target_version, part.advisories, locale=locale) for part in entry.parts)
    said = tuple(dict.fromkeys(notice for notice in notices if notice is not None))
    return " ".join(said) if said else None


def _part_views(entry: DependencyPlanEntry, locale: str | None) -> tuple[DependencyPlanPartViewV1, ...]:
    views: list[DependencyPlanPartViewV1] = []
    for index, part in enumerate(entry.parts):
        before = known_part_bytes_of(entry.parts[:index])
        own = known_part_bytes_of(entry.parts[: index + 1]) - before
        views.append(
            DependencyPlanPartViewV1(
                part_id=part.part_id,
                name=dependency_part_name(part.part_id, locale=locale),
                download_bytes=None if part.download_bytes is None else own,
            )
        )
    return tuple(views)


def _project_setup_review(value: BaseModel, interaction: OperationInteractionRequest, /) -> BaseModel:
    if type(value) is not DependencySetupProposal:
        raise ValueError("invalid setup proposal")
    proposal = DependencySetupProposal.model_validate(value.model_dump(mode="python"), strict=True)
    if (
        proposal.identity != interaction.identity
        or proposal.revision != interaction.revision
        or proposal.digest != interaction.continuation_digest
    ):
        raise ValueError("setup proposal differs from its interaction")
    plan = proposal.plan
    locale = _locale(proposal.request.locale)
    first_by_download: dict[tuple[str, str], str] = {}
    views: list[DependencyPlanEntryViewV1] = []
    for entry in plan.entries:
        destination = _destination_path(entry.destination)
        shared_with = None
        if entry.target_version is not None and entry.destination is not None:
            key = (entry.destination.value, entry.target_version)
            shared_with = first_by_download.get(key)
            first_by_download.setdefault(key, entry.item_id)
        views.append(
            DependencyPlanEntryViewV1(
                entry=entry,
                destination_path=None if destination is None else str(destination),
                shares_download_with=shared_with,
                licence_notice=_licence_notice(entry, locale),
                parts=_part_views(entry, locale),
            )
        )
    return DependencySetupReviewV2(
        identity=proposal.identity,
        revision=proposal.revision,
        plan_digest=dependency_plan_digest(plan),
        entries=tuple(views),
        known_download_bytes=plan.known_download_bytes,
        has_unknown_size=plan.has_unknown_size,
        installs_outside_program=plan.installs_outside_program,
        space=plan.space,
        space_sufficient=plan.space.sufficient,
        reviewed_proposal_digest=proposal.digest,
        wording=dependency_wording_view(
            (),
            dependency_item_declarations(),
            locale=locale,
            operation_id=proposal.identity.operation_id,
            phases=(DEPENDENCIES_SETUP_PLAN_PHASE,),
            hosts=(host for entry in plan.entries for host in entry.source_hosts),
        ),
    )


def build_dependency_operation_registrations(
    definitions: tuple[OperationDefinition, OperationDefinition, OperationDefinition],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind the setup, status and verify definitions to their public schemas, in definition-id order."""
    setup, status, verify = definitions
    return (
        OperationPublicDefinitionRegistrationV1.compose(
            definition=setup,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID + ".request",
                schema_version=1,
                model_type=DependencySetupRequest,
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID + ".result",
                schema_version=1,
                model_type=DependencySetupResultV1,
            ),
            review_projection_schema=DEPENDENCIES_SETUP_REVIEW_SCHEMA,
            interaction_response_schema=DEPENDENCIES_SETUP_RESPONSE_SCHEMA,
            access_resolver=_resolve_setup_access,
            review_projector=_project_setup_review,
            reviewed_operand_type=DependencySetupProposal,
        ),
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=status,
            public_result_type=DependencyStatusResultV1,
            access_resolver=_resolve_status_access,
        ),
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=verify,
            public_result_type=DependencyStatusResultV1,
            access_resolver=_resolve_verify_access,
        ),
    )
