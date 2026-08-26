"""Real proofs that census field review dispatches typed responses without policy.

Every assertion drives a real registered profile-maintenance operation
through the composed production services to genuinely move
``record_revision``, and drives the real Textual :class:`CensalFieldReviewScreen`
through :meth:`textual.app.App.run_test`. No mocks, fakes, or stubs.
"""

from __future__ import annotations

import ast
import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from textual.app import App

from .....adapters.persistence.operations.journal import OperationJournalRepository
from .....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from .....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from .....application.operations.composition import compose_operation_services
from .....application.operations.frontend_contracts import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from .....application.operations.models import OperationRequest
from .....application.operations.registry import OperationRegistry
from .....application.user_profile.censal_operation import (
    CensalFieldIntent,
    CensalOperationRequest,
    CensalProfileBaseline,
    build_censal_operation_request,
)
from .....application.user_profile.login_session import login_profile
from .....application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.registration import register_profile_with_credentials
from .....core.config import load_settings
from .....core.paths import effective_storage_root
from .....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from .....core.time import now
from .....domain.user_profile.values import UserProfileFact
from .....tests.secure_sql import isolated_profile_storage_root
from .. import sync_review
from ..sync_review import (
    CensalFieldReviewRowV1,
    CensalFieldReviewScreen,
    censal_baseline_is_stale,
    censal_field_review_rows,
    censal_operation_request_from_selection,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "census-sync-review-passphrase"  # noqa: S105 - isolated integration fixture


def _rows_from_request(request: CensalOperationRequest) -> tuple[CensalFieldReviewRowV1, ...]:
    return tuple(
        CensalFieldReviewRowV1(path=item.path, persisted_value=None, suggested_intent=item.intent, observed_value=None)
        for item in request.field_intents
    )


def test_rows_reproduce_the_suggested_intent_without_recomputation(tmp_path: Path) -> None:
    """Every row's suggested intent is exactly the request's, not re-derived."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Census sync review subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)
        record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        request = build_censal_operation_request(record)

        rows = censal_field_review_rows(request, record)

        assert tuple(row.path for row in rows) == tuple(item.path for item in request.field_intents)
        assert tuple(row.suggested_intent for row in rows) == tuple(item.intent for item in request.field_intents)
        assert all(row.observed_value is None for row in rows)


def test_stale_detection_is_a_pure_revision_comparison(tmp_path: Path) -> None:
    """Staleness flips only after a real mutation advances record_revision."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Census sync review subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)
        repository = ProfileRecordRepository.for_current_session(profile_id)
        record = repository.load(profile_id)
        baseline = CensalProfileBaseline.from_record(record)
        assert censal_baseline_is_stale(baseline, record) is False

        definitions = build_user_profile_operation_definitions()
        registrations = build_user_profile_operation_registrations(definitions)
        registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
        storage_root = effective_storage_root(settings=load_settings())
        journal = OperationJournalRepository(storage_root=storage_root / "operations")
        services = compose_operation_services(
            registry=registry,
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=storage_root / "operations"),
            operands=operation_secure_reference_repository(),
            owner_id="3" * 64,
            lease_token_factory=lambda: "4" * 64,
            clock=now,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(hours=1),
            cleanup_timeout=timedelta(minutes=2),
        )

        async def mutate() -> None:
            definition = registry.lookup("user-profile.field-mutation")
            payload = definition.request_type.model_validate(
                {"profile_id": profile_id, "path": PROFILE_OUTPUT_LANGUAGE_PATH, "value": "es"},
                strict=True,
            )
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id="user-profile.field-mutation",
                    subject_ref=f"profile:{profile_id}",
                    payload=payload,
                ),
                actor_ref="operator:census-sync-review-test",
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
                if observed.projection.lifecycle.value == "terminal":
                    break
                await asyncio.sleep(0)
            await services.shutdown()

        asyncio.run(mutate())

        mutated_record = repository.load(profile_id)
        assert mutated_record.record_revision == record.record_revision + 1
        assert censal_baseline_is_stale(baseline, mutated_record) is True


def test_selection_dispatches_exactly_what_the_operator_picked(tmp_path: Path) -> None:
    """The rebuilt request encodes the selection verbatim, never a recomputed merge."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Census sync review subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)
        record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        request = build_censal_operation_request(record)
        rows = _rows_from_request(request)
        chosen_path = request.field_intents[0].path

        rebuilt = censal_operation_request_from_selection(request.baseline, rows, frozenset({chosen_path}))

        assert rebuilt.baseline == request.baseline
        for item in rebuilt.field_intents:
            expected = CensalFieldIntent.ADOPT if item.path == chosen_path else CensalFieldIntent.PRESERVE
            assert item.intent is expected


async def _drive_screen(request: CensalOperationRequest, button_id: str) -> object:
    rows = _rows_from_request(request)

    class _Host(App[None]):
        outcome: object = "unset"

        async def _present(self) -> None:
            self.outcome = await self.push_screen_wait(
                CensalFieldReviewScreen(
                    request.baseline,
                    rows,
                    stale=False,
                    title="Review",
                    stale_message="Stale",
                    apply_all_label="Apply all",
                    reject_label="Reject",
                    confirm_label="Confirm",
                )
            )
            self.exit()

        def on_mount(self) -> None:
            self.run_worker(self._present())

    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        if button_id == "#btn-censal-apply-all":
            await pilot.click("#btn-censal-apply-all")
            await pilot.click("#btn-censal-confirm")
        else:
            await pilot.click(button_id)
        for _ in range(200):
            if app.outcome != "unset":
                break
            await pilot.pause()
    return app.outcome


def test_screen_apply_all_dispatches_the_suggested_request(tmp_path: Path) -> None:
    """Pressing apply-all then confirm reproduces the suggested intents exactly."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Census sync review subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)
        record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        request = build_censal_operation_request(record)

    outcome = asyncio.run(_drive_screen(request, "#btn-censal-apply-all"))

    assert isinstance(outcome, CensalOperationRequest)
    assert outcome.baseline == request.baseline
    assert outcome.field_intents == request.field_intents


def test_screen_reject_dismisses_with_none(tmp_path: Path) -> None:
    """Pressing reject dismisses with ``None`` -- no request is dispatched."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Census sync review subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)
        record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        request = build_censal_operation_request(record)

    outcome = asyncio.run(_drive_screen(request, "#btn-censal-reject"))

    assert outcome is None


def test_module_never_imports_the_merge_reconciliation_policy() -> None:
    """A structural proof: this module cannot recompute the adopt/preserve merge.

    ``reconcile_censal_read`` and ``censal_facts_from_read`` are the
    application layer's own merge-policy functions; importing either into
    the presentation module would let it silently re-derive a decision the
    application already made.
    """
    source_path = Path(sync_review.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_names = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert "reconcile_censal_read" not in imported_names
    assert "censal_facts_from_read" not in imported_names
