"""An invoice book only the column-naming model reads settles REFUSED with the local AI setup in its detail.

The registered ``ledger.invoice.import`` runs through the production registry,
the real supervisor, journal and encrypted operand store, and its production
port composition, against a real loopback runtime that answers its inventory
with no model and records every read it is sent. The refusal is then read back
the way a frontend in another process reads it: as the operation's recorded
error detail. That detail must carry the verdict naming the local AI setup,
must not carry a value from the book, and no read may be sent first.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import override
from uuid import UUID

import pytest

from ...application.invoices.catalogue_intake_contracts import (
    INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    InvoiceImportRequest,
)
from ...application.operations.error_detail import (
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from ...application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.registry import OperationRegistry
from ...application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from ...core.config import override_settings
from ...core.model_roles import ModelRole
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.iva.schema import InvoiceKind
from ...tests.inventory import FIXTURES_DIR
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from . import registered_executor_case_support as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A sales book whose column names no exact header vocabulary reads, so only the column-naming model reads it.
_LIBRO = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"
#: Cell values of that book; none may reach the published detail.
_BOOK_VALUES = ("2025/0142", "Talleres Berrocal", "A82645177", "4272.00")
_READER_REFUSAL_CODE = "REFUSED_LEDGER_IMPORT_READER"


@contextmanager
def _runtime_holding_nothing(posts: list[str]) -> Generator[None]:
    """Serve a real runtime that answers its inventory with no model and records every read it is sent."""

    class _EmptyRuntime(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            write_json_response(self, {"models": []}, status=HTTPStatus.OK)

        @override
        def do_POST(self) -> None:
            posts.append(self.path)
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)

    with (
        serving_loopback(_EmptyRuntime, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield


def _settle_and_read_detail(
    driver: conformance._ExecutionDriver, registry: OperationRegistry, profile_id: UUID, book: Path
) -> tuple[OperationObservationSuccessV1, OperationErrorDetailV1]:
    contract = registry.lookup_public_contract(INVOICE_IMPORT_OPERATION_DEFINITION_ID)

    async def run() -> tuple[OperationObservationSuccessV1, OperationErrorDetailV1]:
        submitted, _observed = await driver.run(
            definition_id=INVOICE_IMPORT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=InvoiceImportRequest(profile_id=profile_id, kind=InvoiceKind.ISSUED, source_path=str(book)),
        )
        observed = await driver.observe(submitted.receipt.operation_id)
        resolved = await driver.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=observed.projection.operation_id,
                terminal_revision=observed.projection.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=operation_error_detail_schema(),
            ),
            OperationErrorDetailV1,
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
        detail = resolved.projection
        assert isinstance(detail, OperationErrorDetailV1)
        return observed, detail

    return asyncio.run(run())


def test_an_invoice_book_whose_column_model_is_missing_settles_with_the_local_ai_setup(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    del operation
    book = tmp_path / "libro.csv"
    book.write_bytes(_LIBRO.read_bytes())
    posts: list[str] = []
    with (
        _runtime_holding_nothing(posts),
        conformance.conformance_operation_runtime(
            tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
        ) as (driver, registry, profile_id),
    ):
        observed, detail = _settle_and_read_detail(driver, registry, profile_id, book)

    projection = observed.projection
    assert projection.terminal_condition is OperationTerminalCondition.REFUSED, projection
    assert projection.effect is OperationEffect.NONE
    assert projection.refusal_ref == _READER_REFUSAL_CODE
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == _READER_REFUSAL_CODE
    verdict = detail.precondition_verdict()
    assert verdict is not None, "the settled refusal lost the reader probe's verdict"
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert {str(item.values.get("role")) for item in verdict.evidence} == {ModelRole.COLUMN_ROLE_MAPPING.value}
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    published = detail.model_dump_json()
    assert not [value for value in _BOOK_VALUES if value in published], "the published detail carries book values"
    assert posts == [], "a read was sent before the reader was checked"
