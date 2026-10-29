"""An invoice book only the column-naming model reads settles REFUSED with the missing model in its detail.

The registered ``ledger.invoice.import`` runs through the production registry,
the real supervisor, journal and encrypted operand store, and its production
port composition. Its model runs reach a recording stand-in for the agent
service through an execution authority, as the runtime host's authority
relays them, and the service reports the column-mapping selection's model is
not installed. The refusal is then read back the way a frontend in another
process reads it: as the operation's recorded error detail. That detail must
carry the verdict naming the missing model, must not carry a value from the
book, and no run may reach the service.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

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
from ...application.probe_outcomes import ProbePreconditionCondition
from ...core.model_roles import ModelRole
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.iva.schema import InvoiceKind
from ...tests.inventory import FIXTURES_DIR
from . import registered_executor_case_support as conformance
from .dependency_operation_gating_support import operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A sales book whose column names no exact header vocabulary reads, so only the column-naming model reads it.
_LIBRO = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"
#: Cell values of that book; none may reach the published detail.
_BOOK_VALUES = ("2025/0142", "Talleres Berrocal", "A82645177", "4272.00")
_READER_REFUSAL_CODE = "REFUSED_LEDGER_IMPORT_READER"


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


def test_an_invoice_book_whose_column_model_is_missing_settles(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    del operation
    book = tmp_path / "libro.csv"
    book.write_bytes(_LIBRO.read_bytes())
    with operation_runtime(tmp_path, ModelRunRefusalCode.MODEL_NOT_INSTALLED) as runtime:
        observed, detail = _settle_and_read_detail(runtime.driver, runtime.registry, runtime.profile_id, book)

    projection = observed.projection
    assert projection.terminal_condition is OperationTerminalCondition.REFUSED, projection
    assert projection.effect is OperationEffect.NONE
    assert projection.refusal_ref == _READER_REFUSAL_CODE
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == _READER_REFUSAL_CODE
    verdict = detail.precondition_verdict()
    assert verdict is not None, "the settled refusal lost the service's verdict"
    assert verdict.failed_condition_id == ProbePreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert {str(item.values.get("role")) for item in verdict.evidence} == {ModelRole.COLUMN_ROLE_MAPPING.value}
    assert verdict.action is None
    published = detail.model_dump_json()
    assert not [value for value in _BOOK_VALUES if value in published], "the published detail carries book values"
    assert runtime.service.lookups == [ModelRole.COLUMN_ROLE_MAPPING]
    assert runtime.service.runs == [], "a run was sent for a role whose model is not installed"
