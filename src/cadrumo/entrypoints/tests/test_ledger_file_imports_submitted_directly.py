"""A client that submits the two import operations itself needs nothing a frontend prepares for it.

The production registry and the real executors run over a stored profile, with
synthetic files in a temporary directory. A directory handed to the statement
import is planned into its files by the operation, exactly as a caller that
listed those files would have submitted them. An invoice book handed over with
no digest is hashed by the operation from the bytes it parses, and a digest
that does not match the file is refused with nothing stored.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...application.invoices.catalogue_intake_contracts import (
    INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    InvoiceImportProjection,
    InvoiceImportRequest,
)
from ...application.ledger.actions_import import LedgerProviderID, plan_ledger_import_sources
from ...application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    MAX_LEDGER_IMPORT_FILES,
    LedgerImportRequest,
    LedgerImportResultProjection,
)
from ...application.operations.frontend_requests import OperationObservationSuccessV1
from ...application.operations.registry import OperationRegistry
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.iva.classification import InvoiceKind
from ..ledger_action_composition import compose_ledger_action_ports
from . import test_registered_executor_conformance as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_STATEMENT = (
    "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda\n"
    "08/04/2026;08/04/2026;Transferencia recibida CLIENTE UNO;1500,25;4300,75;EUR\n"
    "09/04/2026;09/04/2026;Pago alquiler oficina;-800,00;3500,75;EUR\n"
)
_LATER_STATEMENT = (
    "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda\n"
    "12/05/2026;12/05/2026;Transferencia recibida CLIENTE DOS;640,10;4140,85;EUR\n"
)
_NOT_A_STATEMENT = "colonna_a,colonna_b\nvalore,altro\n"
_INVOICE_BOOK = (
    b"counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate,currency,country_code\n"
    b"B12345674,Synthetic Supplier,BOOK-2025-001,2025-02-03,100.00,21,EUR,ES\n"
    b"B12345674,Synthetic Supplier,BOOK-2025-002,2025-02-10,200.00,21,EUR,ES\n"
)


def _submit(
    driver: conformance._ExecutionDriver, *, definition_id: str, profile_id: UUID, payload: BaseModel
) -> OperationObservationSuccessV1:
    async def run() -> OperationObservationSuccessV1:
        submitted, _observed = await driver.run(
            definition_id=definition_id, subject_ref=profile_operation_subject(str(profile_id)), payload=payload
        )
        return await driver.observe(submitted.receipt.operation_id)

    return asyncio.run(run())


def _statement_import(
    driver: conformance._ExecutionDriver,
    registry: OperationRegistry,
    profile_id: UUID,
    *,
    files: tuple[Path, ...],
    dry_run: bool,
) -> LedgerImportResultProjection:
    observed = _submit(
        driver,
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        profile_id=profile_id,
        payload=LedgerImportRequest(
            profile_id=profile_id, files=files, provider=LedgerProviderID.AUTO, dry_run=dry_run
        ),
    )
    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, observed.projection
    return conformance._resolve_result_projection(
        driver,
        registry,
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        operation_id=observed.projection.operation_id,
        terminal_revision=observed.projection.revision,
        projection_type=LedgerImportResultProjection,
    )


def _statement_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "statements"
    folder.mkdir()
    # Written out of order, beside a file no statement parser may be handed.
    (folder / "c_later.csv").write_text(_LATER_STATEMENT, encoding="utf-8")
    (folder / "a_not_a_statement.csv").write_text(_NOT_A_STATEMENT, encoding="utf-8")
    (folder / "b_statement.csv").write_text(_STATEMENT, encoding="utf-8")
    (folder / "notes.txt").write_text("not a statement", encoding="utf-8")
    return folder


def test_a_directory_submitted_directly_imports_the_rows_its_listed_files_import(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The operation's plan is the plan a caller listing the files would have sent, file for file."""
    folder = _statement_folder(tmp_path)
    listed = plan_ledger_import_sources(folder)
    assert [path.name for path in listed] == ["a_not_a_statement.csv", "b_statement.csv", "c_later.csv"]
    with conformance._runtime(tmp_path / "runtime", cleanup=conformance._CloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        from_the_files = _statement_import(driver, registry, profile_id, files=listed, dry_run=True)
        previewed = _statement_import(driver, registry, profile_id, files=(folder,), dry_run=True)

        assert previewed == from_the_files
        assert (previewed.rows, previewed.imported) == (3, 3)
        assert [(item.file_name, item.reason_code) for item in previewed.refused_files] == [
            ("a_not_a_statement.csv", "transaction_validation")
        ]
        # A parsed file is named by its place in the plan: the refused file holds the first.
        assert [item.file_index for item in previewed.source_digests] == [1, 2]

        imported = _statement_import(driver, registry, profile_id, files=(folder,), dry_run=False)

        assert (imported.rows, imported.imported, imported.skipped) == (3, 3, 0)
        assert imported.refused_files == previewed.refused_files
        assert imported.source_digests == previewed.source_digests
        stored = compose_ledger_action_ports(
            bucket_id=str(profile_id), operation=operation
        ).transaction_repository.load()
        assert sorted(row.raw.description for row in stored.values()) == [
            "Pago alquiler oficina",
            "Transferencia recibida CLIENTE DOS",
            "Transferencia recibida CLIENTE UNO",
        ]
        assert {reference.transaction_id for reference in imported.imported_transaction_refs} == set(
            stored.transactions
        )


def test_a_directory_with_nothing_to_import_and_an_over_long_plan_are_refused_by_the_operation(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Neither reads a file: an empty plan imports nothing, and a part of an over-long one was never named."""
    del operation
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "notes.txt").write_text("not a statement", encoding="utf-8")
    crowded = tmp_path / "crowded"
    crowded.mkdir()
    for index in range(MAX_LEDGER_IMPORT_FILES + 1):
        (crowded / f"statement-{index:03d}.csv").write_text(_STATEMENT, encoding="utf-8")
    with conformance._runtime(tmp_path / "runtime", cleanup=conformance._CloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        for folder, reason in ((empty, "empty_directory"), (crowded, "file_limit")):
            result = _statement_import(driver, registry, profile_id, files=(folder,), dry_run=False)

            assert (result.rows, result.imported, result.validations) == (0, 0, ())
            assert [(item.file_name, item.reason_code) for item in result.refused_files] == [(folder.name, reason)]


def _invoice_import(
    driver: conformance._ExecutionDriver, profile_id: UUID, book: Path, *, digest: str | None
) -> OperationObservationSuccessV1:
    return _submit(
        driver,
        definition_id=INVOICE_IMPORT_OPERATION_DEFINITION_ID,
        profile_id=profile_id,
        payload=InvoiceImportRequest(
            profile_id=profile_id, kind=InvoiceKind.RECEIVED, source_path=str(book), source_sha256=digest
        ),
    )


def test_an_invoice_book_submitted_with_no_digest_is_imported_and_its_digest_returned(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    del operation
    book = tmp_path / "invoice-book.csv"
    book.write_bytes(_INVOICE_BOOK)
    with (
        conformance._model_runtime_for(INVOICE_IMPORT_OPERATION_DEFINITION_ID),
        conformance._runtime(tmp_path / "runtime", cleanup=conformance._CloseWitness()) as (
            driver,
            registry,
            profile_id,
        ),
    ):
        observed = _invoice_import(driver, profile_id, book, digest=None)

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, observed.projection
        assert observed.projection.effect is OperationEffect.UPDATED
        result = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=INVOICE_IMPORT_OPERATION_DEFINITION_ID,
            operation_id=observed.projection.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceImportProjection,
        )
        assert result.source_sha256 == sha256_hex(_INVOICE_BOOK)
        assert (result.rows, result.created, result.refused) == (2, 2, ())
        stored = InvoiceCatalogueRepository(bucket_id=str(profile_id)).load().invoices
        assert set(stored) == set(result.created_invoice_ids)
        # Each created invoice records the digest of the bytes it was read from.
        recorded = {invoice.provenance.source_sha256 for invoice in stored.values() if invoice.provenance is not None}
        assert recorded == {sha256_hex(_INVOICE_BOOK)}


@pytest.mark.parametrize("supplied", ["the-files-own", "another-files"])
def test_an_invoice_book_is_held_to_the_digest_a_caller_supplies(
    tmp_path: Path, operation: PinnedAuthorityOperation, supplied: str
) -> None:
    """The matching digest imports as an import with none does; any other is refused with nothing stored."""
    del operation
    book = tmp_path / "invoice-book.csv"
    book.write_bytes(_INVOICE_BOOK)
    matches = supplied == "the-files-own"
    with (
        conformance._model_runtime_for(INVOICE_IMPORT_OPERATION_DEFINITION_ID),
        conformance._runtime(tmp_path / "runtime", cleanup=conformance._CloseWitness()) as (
            driver,
            registry,
            profile_id,
        ),
    ):
        observed = _invoice_import(driver, profile_id, book, digest=sha256_hex(_INVOICE_BOOK) if matches else "f" * 64)

        repository = InvoiceCatalogueRepository(bucket_id=str(profile_id))
        stored = repository.load().invoices if repository.exists() else {}
        if not matches:
            assert observed.projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            assert observed.projection.effect is OperationEffect.NONE
            assert stored == {}
            return
        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, observed.projection
        result = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=INVOICE_IMPORT_OPERATION_DEFINITION_ID,
            operation_id=observed.projection.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceImportProjection,
        )
        assert result.source_sha256 == sha256_hex(_INVOICE_BOOK)
        assert set(stored) == set(result.created_invoice_ids) and len(stored) == 2
