"""One real encrypted profile and the composed supervisor, over a registry a test names.

The profile, its session, the journal, the lease store and the encrypted
operand custody are the production ones. Only the registry is the test's: it
holds the definitions under test, composed as their owning packages compose
them, so an operation that the production registry does not hold yet runs
through the same supervisor every registered operation runs through.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.operations.typed_financial_operand_custody import (
    OperationTypedFinancialOperandCustodyFilesystemRepository,
)
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from ...adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.operations.composition import OperationComposedServices, compose_operation_services
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest, OperationTerminalReceipt
from ...application.operations.operation_definition import OperationDefinition
from ...application.operations.registry import OperationPublicDefinitionRegistrationV1, OperationRegistry
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.login_session import authenticate_profile_for_invocation
from ...application.user_profile.registration import register_profile_with_credentials
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.user_profile.values import UserProfileFact

PROFILE_INPUT = "a-sufficiently-long-operator-passphrase"
_ACTOR = "operator:profile-operation-test"


@dataclass(frozen=True, slots=True)
class SettledOperation:
    """One settled invocation: its terminal receipt and the revision it settled at."""

    operation_id: str
    receipt: OperationTerminalReceipt
    revision: int


@dataclass(frozen=True, slots=True)
class SupervisedProfile:
    """The profile, its storage root and the supervisor composed over the test's registry."""

    root: Path
    profile_id: UUID
    registry: OperationRegistry
    services: OperationComposedServices
    decode_context: ProfileDecodeContext

    def run(
        self, *, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytearray | None = None
    ) -> SettledOperation:
        """Submit, deliver the declared secret when one is declared, start and wait for settlement."""
        return asyncio.run(self._run(definition_id, subject_ref, payload, secret))

    async def _run(
        self, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytearray | None
    ) -> SettledOperation:
        submission = self.services.submission
        submitted = await submission.submit(
            OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload), actor_ref=_ACTOR
        )
        requirement = submitted.receipt.secret_requirement
        assert (requirement is None) == (secret is None)
        if requirement is not None and secret is not None:
            await submission.submit_secret(requirement, secret)
        operation_id = submitted.receipt.operation_id
        await submission.start(operation_id)
        await submission.settled(operation_id)
        observed = await self.services.observation.observe(
            OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1)
        )
        assert isinstance(observed, OperationObservationSuccessV1)
        snapshot = await submission.supervisor.inspect(operation_id)
        assert snapshot.terminal_receipt is not None
        return SettledOperation(operation_id, snapshot.terminal_receipt, observed.projection.revision)

    def result[ProjectionT: BaseModel](
        self, settled: SettledOperation, projection_type: type[ProjectionT]
    ) -> ProjectionT:
        """Read the settled result through the registered projector and encrypted operand custody."""
        contract = self.registry.lookup_public_contract(settled.receipt.identity.definition_id)
        assert contract.result_schema is not None
        resolved = asyncio.run(
            self.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=settled.operation_id,
                    terminal_revision=settled.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                projection_type,
            )
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        assert isinstance(resolved.projection, projection_type)
        return resolved.projection

    def error_detail(self, settled: SettledOperation) -> OperationErrorDetailV1:
        """Read the public detail a refused or failed invocation recorded."""
        contract = self.registry.lookup_public_contract(settled.receipt.identity.definition_id)
        resolved = asyncio.run(
            self.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=settled.operation_id,
                    terminal_revision=settled.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        assert isinstance(resolved.projection, OperationErrorDetailV1)
        return resolved.projection


@contextmanager
def supervised_profile(
    tmp_path: Path,
    composed: Sequence[tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1]],
) -> Generator[SupervisedProfile]:
    """Register and sign in to one profile, and compose the supervisor over ``composed``."""
    create_context, decode_context = profile_authority_contexts()
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        enrolled = register_profile_with_credentials(
            label="Profile operation subject",
            passphrase=PROFILE_INPUT,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            profile_create_context=create_context,
            profile_decode_context=decode_context,
        )
        profile_id = UUID(enrolled.profile_id)
        authenticate_profile_for_invocation(
            name=enrolled.profile_id,
            passphrase_callback=lambda: PROFILE_INPUT,
            profile_decode_context=decode_context,
        )
        registry = OperationRegistry(
            definitions=tuple(sorted((item[0] for item in composed), key=lambda item: item.definition_id)),
            public_registrations=tuple(
                sorted((item[1] for item in composed), key=lambda item: item.contract.definition_id)
            ),
        )
        journal = OperationJournalRepository(storage_root=root / "operations")
        with (
            profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects,
            bundled_indexed_authority().operation() as authority_operation,
        ):
            services = compose_operation_services(
                registry=registry,
                authority_operation=authority_operation,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
                operands=operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects)),
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=now,
                lease_duration=timedelta(minutes=10),
                execution_timeout=timedelta(hours=1),
                cleanup_timeout=timedelta(minutes=2),
                typed_financial_operand_custody=OperationTypedFinancialOperandCustodyFilesystemRepository(
                    root=root / "operations" / "typed_financial_operand_custody",
                ),
            )
            try:
                yield SupervisedProfile(
                    root=root,
                    profile_id=profile_id,
                    registry=registry,
                    services=services,
                    decode_context=decode_context,
                )
            finally:
                asyncio.run(services.shutdown())
                # The sign-in above binds this process's live session; leaving it
                # open would hand every later test a profile it never created.
                reset_test_profile_session()
