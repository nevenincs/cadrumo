"""An invoice correction says records may have changed only once a write begins.

The update runs every rule the corrected invoice must meet before anything is
saved. A correction one of those rules refuses settles with no effect; only a
write that is about to begin journals that records may have changed.

Real behaviour throughout: an isolated encrypted profile, the production
executor and its production lifecycle ports, fenced the way the host fences them.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.exchange_rate_provider import exchange_rate_provider
from ....application.invoices.catalogue_creation import build_catalogue_invoice
from ....application.invoices.catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    InvoiceUpdateExecutor,
    InvoiceUpdatePatch,
    InvoiceUpdateRequest,
    InvoiceUpdateValues,
)
from ....application.operations.models import OperationIdentity, OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.time.clock import now
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.models import Invoice
from ....domain.invoices.rule_findings import InvoiceRuleFindingCode, rule_finding_words_key
from ....domain.invoices.tests.catalogue_support import build_invoice_catalogue
from ....domain.iva.schema import InvoiceKind
from ...adapter_composition_ports import build_invoice_lifecycle_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE = UUID("20202020-2020-4202-8202-202020202020")
_BUCKET_ID = str(_PROFILE)


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        yield


class _Context:
    def __init__(self, request: OperationRequest[InvoiceUpdateRequest]) -> None:
        self.identity = OperationIdentity(
            operation_id="b" * 64, definition_id=request.definition_id, subject_ref=request.subject_ref
        )
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = operation_secure_reference_repository()


def _stored_invoice(objects: SecureObjectRepository) -> Invoice:
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="B00010157",
        counterparty_country="ES",
        invoice_number="F-0201",
        issued_at=now().date() - timedelta(days=30),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=exchange_rate_provider(),
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).save(build_invoice_catalogue((invoice,)))
    return invoice


def _update(
    invoice: Invoice, values: InvoiceUpdateValues, fields: frozenset[str]
) -> tuple[_Context, BaseException | None]:
    request = OperationRequest[InvoiceUpdateRequest](
        definition_id=INVOICE_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(_BUCKET_ID),
        payload=InvoiceUpdateRequest(
            profile_id=_PROFILE,
            invoice_id=invoice.invoice_id,
            patch=InvoiceUpdatePatch(values=values, fields=fields),
        ),
    )
    context = _Context(request)
    executor = InvoiceUpdateExecutor(build_invoice_lifecycle_ports)
    try:
        asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    except InvoiceValidationError as refused:
        return context, refused
    return context, None


def test_a_correction_its_rules_refuse_settles_with_no_effect(tmp_path: Path) -> None:
    """LIVA art. 75 needs the role an operation date answers; adding the date alone is refused before any write."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice = _stored_invoice(profile.repository)

        context, refused = _update(
            invoice,
            InvoiceUpdateValues(operation_date=invoice.issued_at - timedelta(days=1)),
            frozenset({"operation_date"}),
        )

        assert isinstance(refused, InvoiceValidationError)
        assert refused.translated_message == rule_finding_words_key(InvoiceRuleFindingCode.OPERATION_DATE_ROLE_MISMATCH)
        assert context.events.effects == []
        stored = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).load()
        assert stored.get(invoice.invoice_id) == invoice


def test_an_admitted_correction_journals_a_possible_effect_before_it_writes(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice = _stored_invoice(profile.repository)

        context, refused = _update(invoice, InvoiceUpdateValues(notes="revisada"), frozenset({"notes"}))

        assert refused is None
        assert context.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
        stored = (
            InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).load().get(invoice.invoice_id)
        )
        assert stored is not None
        assert stored.notes == "revisada"
