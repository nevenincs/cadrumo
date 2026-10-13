"""Supervised operation for provisioning the browser build automation launches, from any frontend.

``browser-runtime.provision`` downloads the Chromium builds the installed
Playwright pins when any is missing, then confirms them. It is idempotent: a
complete cache runs nothing.

The installer is injected. The application layer never spawns a process
itself; the entrypoint composition binds the outbound adapter.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..core.time.clock import now
from .local_reader_contracts import (
    LocalReaderFactV1,
    local_reader_public_facts,
    local_reader_verdict_condition,
    local_reader_verdict_facts,
)
from .local_reader_operation import bind_machine_provisioning_access
from .operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from .operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operations.operation_definition import OperationDefinition, OperationExecutorFactory
from .operations.owner import OperationExecutorContext
from .operations.registry import OperationPublicDefinitionRegistrationV1, OperationReconciliationPolicy
from .operations.subject_reference import OperationSubjectReferenceV1
from .provisioning_browser import BrowserInstallerRunner, BrowserInstallOutcome, install_playwright_browser

__all__ = [
    "BROWSER_RUNTIME_EXECUTE_PHASE",
    "BROWSER_RUNTIME_OPERATION_DEFINITION_ID",
    "BROWSER_RUNTIME_OPERATION_SUBJECT",
    "BROWSER_RUNTIME_PREFLIGHT_PHASE",
    "BROWSER_RUNTIME_SETTLEMENT_PHASE",
    "BrowserRuntimeProvisionExecutor",
    "BrowserRuntimeProvisionPublicResultV1",
    "BrowserRuntimeProvisionRequest",
    "browser_runtime_provision_effect",
    "browser_runtime_public_result",
    "build_browser_runtime_operation_definition",
    "build_browser_runtime_operation_registration",
    "project_browser_runtime_result",
    "resolve_browser_runtime_provision_access",
]

BROWSER_RUNTIME_OPERATION_DEFINITION_ID = "browser-runtime.provision"
BROWSER_RUNTIME_OPERATION_SUBJECT = "browser-runtime:chromium"
BROWSER_RUNTIME_PREFLIGHT_PHASE = "browser-runtime.provision.preflight"
BROWSER_RUNTIME_EXECUTE_PHASE = "browser-runtime.provision.execute"
BROWSER_RUNTIME_SETTLEMENT_PHASE = "browser-runtime.provision.settlement"


class BrowserRuntimeProvisionRequest(CredentialFreeOperationRequest):
    """One browser provisioning run; the pinned builds are the whole subject, so the request carries nothing."""


class BrowserRuntimeProvisionPublicResultV1(BaseModel):
    """Public projection of a settled browser provisioning run.

    A refusal is named by its condition and evidence facts, as the reader's
    provisioning results name theirs: every refusal a run can settle with is a
    runtime observation that rebuilds from the two.
    """

    model_config = STRICT_FROZEN_CONFIG

    installed: bool
    already_installed: bool
    installer_exit_code: int | None = None
    facts: tuple[LocalReaderFactV1, ...]
    verdict_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    verdict_facts: tuple[LocalReaderFactV1, ...]


def browser_runtime_provision_effect(outcome: BrowserInstallOutcome) -> OperationEffect:
    """Return the committed extent a settled browser provisioning outcome represents."""
    if outcome.installed:
        return OperationEffect.NONE if outcome.already_installed else OperationEffect.UPDATED
    # An installer that ran and did not finish may have left one of the two
    # builds, or part of an archive, in the cache.
    return OperationEffect.PARTIAL if outcome.facts.get("installer_ran") is True else OperationEffect.NONE


class BrowserRuntimeProvisionExecutor:
    """Supervise the browser install: journal its phases and persist its outcome."""

    def __init__(self, *, run_installer: BrowserInstallerRunner) -> None:
        """Bind the injected vendor installer runner."""
        self._run_installer = run_installer

    async def execute(
        self,
        request: OperationRequest[BrowserRuntimeProvisionRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Provision the pinned builds when any is missing and persist the settled outcome."""
        if request.subject_ref != BROWSER_RUNTIME_OPERATION_SUBJECT:
            raise ValueError("browser-runtime operation subject must name the pinned browser build")
        await context.events.phase(BROWSER_RUNTIME_PREFLIGHT_PHASE)
        await context.events.phase(BROWSER_RUNTIME_EXECUTE_PHASE)
        await context.events.effect(OperationEffect.UNKNOWN)
        outcome = await asyncio.to_thread(install_playwright_browser, run=self._run_installer)
        await context.events.effect(browser_runtime_provision_effect(outcome))
        await context.events.phase(BROWSER_RUNTIME_SETTLEMENT_PHASE)
        return await context.operands.put(outcome, written_at=now())


def build_browser_runtime_operation_definition(*, run_installer: BrowserInstallerRunner) -> OperationDefinition:
    """Bind the injected installer runner to the browser provisioning operation."""

    def build() -> BrowserRuntimeProvisionExecutor:
        return BrowserRuntimeProvisionExecutor(run_installer=run_installer)

    return OperationDefinition(
        definition_id=BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
        request_type=BrowserRuntimeProvisionRequest,
        subject_reference=OperationSubjectReferenceV1.fixed(BROWSER_RUNTIME_OPERATION_SUBJECT),
        result_type=BrowserInstallOutcome,
        executor_factory=OperationExecutorFactory(
            request_type=BrowserRuntimeProvisionRequest,
            executor_type=BrowserRuntimeProvisionExecutor,
            build=build,
        ),
        phase_codes=(
            BROWSER_RUNTIME_PREFLIGHT_PHASE,
            BROWSER_RUNTIME_EXECUTE_PHASE,
            BROWSER_RUNTIME_SETTLEMENT_PHASE,
        ),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            # The install downloads two builds, so a failed run can leave one.
            permitted_effects=frozenset(OperationEffect),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
    )


def resolve_browser_runtime_provision_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind access to the machine's browser build with COMMIT: a run can download and install it."""
    return bind_machine_provisioning_access(
        request,
        context,
        definition_id=BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
        payload_type=BrowserRuntimeProvisionRequest,
        subject_ref=BROWSER_RUNTIME_OPERATION_SUBJECT,
        commits=lambda _payload: True,
    )


def project_browser_runtime_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    """Project a settled browser provisioning outcome into its public result."""
    del terminal_receipt
    return browser_runtime_public_result(BrowserInstallOutcome.model_validate(result, strict=True))


def browser_runtime_public_result(outcome: BrowserInstallOutcome) -> BrowserRuntimeProvisionPublicResultV1:
    """Return the public result of one browser provisioning run, whichever caller ran it."""
    return BrowserRuntimeProvisionPublicResultV1(
        installed=outcome.installed,
        already_installed=outcome.already_installed,
        installer_exit_code=outcome.installer_exit_code,
        facts=local_reader_public_facts(outcome.facts),
        verdict_condition_id=local_reader_verdict_condition(outcome.precondition_verdict),
        verdict_facts=local_reader_verdict_facts(outcome.precondition_verdict),
    )


def build_browser_runtime_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the browser provisioning definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=BrowserRuntimeProvisionPublicResultV1,
        result_projector=project_browser_runtime_result,
        access_resolver=resolve_browser_runtime_provision_access,
    )
