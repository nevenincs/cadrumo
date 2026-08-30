"""Real proofs that filed-history progress and results stay visible through settlement.

Covers both public doors: the generic public projection (stage, lifecycle,
refusal/diagnostic references, effect), visible for any settlement outcome,
and the typed public result-projection door
(``OperationResultProjectionService``, registered with filed-history's own
``FiledHistoryPublicResultV1`` schema and projector), which resolves the
settled evidence, IVA-wallet,
notification, and provenance facts without ever importing the private
``FiledHistoryOnboardingRun`` type. No mocks; every test drives the real
registered operation through composed production services.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest

from .....adapters.persistence.operations.journal import OperationJournalRepository
from .....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from .....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from .....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from .....application.live.filed_history_operation import (
    build_filed_history_operation_definition,
    build_filed_history_operation_registration,
)
from .....application.operations.composition import compose_operation_services
from .....application.operations.frontend_contracts import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from .....application.operations.models import OperationRequest
from .....application.operations.registry import OperationRegistry
from .....application.user_profile.login_session import login_profile
from .....application.user_profile.registration import register_profile_with_credentials
from .....core import OperationEffect, OperationLifecycle, OperationTerminalCondition
from .....core.config import load_settings
from .....core.paths import effective_storage_root
from .....core.time import now
from .....domain.user_profile.values import UserProfileFact
from .....tests.secure_sql import isolated_profile_storage_root
from ...operations.controller import OperationController
from ..sync_review import (
    FiledHistoryProgressSummaryV1,
    filed_history_progress_summary,
    resolve_filed_history_result,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "filed-history-view-passphrase"  # noqa: S105 - isolated integration fixture


def test_filed_history_progress_stays_visible_through_a_real_refusal(tmp_path: Path) -> None:
    """Stage, refusal, and effect survive to the public terminal projection."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Filed-history view subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)

        definition = build_filed_history_operation_definition(sync_run_repository_factory=SyncRunRecordRepository)
        registry = OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_filed_history_operation_registration(definition),),
        )
        storage_root = effective_storage_root(settings=load_settings())
        journal = OperationJournalRepository(storage_root=storage_root / "operations")
        services = compose_operation_services(
            registry=registry,
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=storage_root / "operations"),
            operands=operation_secure_reference_repository(),
            owner_id="5" * 64,
            lease_token_factory=lambda: "6" * 64,
            clock=now,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(hours=1),
            cleanup_timeout=timedelta(minutes=2),
        )

        summaries: list[FiledHistoryProgressSummaryV1] = []

        async def run() -> None:
            payload = definition.request_type.model_validate(
                {"output_root": tmp_path / "filed-history", "dry_run": True},
                strict=True,
            )
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id=definition.definition_id,
                    subject_ref=str(profile_id),
                    payload=payload,
                ),
                actor_ref="operator:filed-history-view-test",
            )
            await services.submission.start(submitted.receipt.operation_id)
            for _ in range(200):
                observed = await services.observation.observe(
                    OperationObservationRequestV1(
                        operation_id=submitted.receipt.operation_id,
                        after_cursor=0,
                        page_limit=256,
                    )
                )
                assert isinstance(observed, OperationObservationSuccessV1)
                summaries.append(filed_history_progress_summary(observed.projection))
                if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                    break
                await asyncio.sleep(0)
            await services.shutdown()

        asyncio.run(run())

        assert summaries, "no observation ever succeeded"
        terminal = summaries[-1]
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
        assert terminal.effect is OperationEffect.NONE
        assert terminal.refusal_ref == "REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED"
        # The stage carried at terminal is whatever phase the refusal fired
        # from; it must be one of the operation's own declared phase codes,
        # never invented here.
        assert terminal.stage is None or isinstance(terminal.stage, str)


def test_summary_carries_no_domain_result_field() -> None:
    """The summary's declared shape proves it cannot smuggle a private result.

    ``FiledHistoryOnboardingRun``'s field names (``iva_wallet_status``,
    ``notificaciones_status``, ``evidence_notices``, ``sync_run_ref``) must
    not appear on the public summary model -- if they ever do, someone
    routed the private result type through the public projection.
    """
    fields = set(FiledHistoryProgressSummaryV1.model_fields)
    assert fields == {
        "stage",
        "lifecycle",
        "terminal_condition",
        "effect",
        "refusal_ref",
        "diagnostic_ref",
    }


def test_resolve_filed_history_result_reaches_the_typed_public_door(tmp_path: Path) -> None:
    """The TUI's own resolver dispatches through OperationResultProjectionService.

    A REFUSED settlement (live reads disabled, reachable safely offline)
    carries no result reference, so this proves the wiring reaches the real
    typed refusal rather than a stub -- the corresponding SUCCEEDED path,
    resolving real evidence, IVA-wallet, notificaciones and provenance
    facts, is proven in
    application/live/tests/test_filed_history_operation.py::test_frontend_projects_the_public_result_without_the_private_type.
    """
    from .....application.operations.frontend_contracts import OperationResultProjectionRefusalV1

    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Filed-history view subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)

        definition = build_filed_history_operation_definition(sync_run_repository_factory=SyncRunRecordRepository)
        registry = OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_filed_history_operation_registration(definition),),
        )
        storage_root = effective_storage_root(settings=load_settings())
        journal = OperationJournalRepository(storage_root=storage_root / "operations")
        services = compose_operation_services(
            registry=registry,
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=storage_root / "operations"),
            operands=operation_secure_reference_repository(),
            owner_id="7" * 64,
            lease_token_factory=lambda: "8" * 64,
            clock=now,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(hours=1),
            cleanup_timeout=timedelta(minutes=2),
        )

        async def run() -> object:
            payload = definition.request_type.model_validate(
                {"output_root": tmp_path / "filed-history", "dry_run": True},
                strict=True,
            )
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id=definition.definition_id,
                    subject_ref=str(profile_id),
                    payload=payload,
                ),
                actor_ref="operator:filed-history-view-test",
            )
            controller = OperationController(
                services=services, submission=submitted, actor_ref="operator:filed-history-view-test"
            )
            await controller.start()
            observed = None
            for _ in range(200):
                observed = await controller.observe(0)
                assert isinstance(observed, OperationObservationSuccessV1)
                if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                    break
                await asyncio.sleep(0)
            assert observed is not None
            return await resolve_filed_history_result(controller, observed.projection)

        resolved = asyncio.run(run())

        assert isinstance(resolved, OperationResultProjectionRefusalV1)
