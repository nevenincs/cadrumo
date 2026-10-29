"""Intake composition delegates canonical custody/FX with lazy admission."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ...adapters.outbound.llm.preconditions import LLMPreconditionCondition
from ...adapters.outbound.llm.tests.model_run_support import ON_HOST_LANE, serving_agent
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.invoices.bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
from ...application.invoices.creation_wizard import create_invoice_via_wizard
from ...application.ledger.import_ports import LedgerImportReaderUnavailableError
from ...application.operations.error_detail import build_operation_error_detail
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.config import override_settings
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.model_roles import ModelRole
from ...domain.buckets.event import BucketEventHistoryCatalogue, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.schema import InvoiceKind
from ...tests.inventory import FIXTURES_DIR
from ..invoice_intake_operation_composition import build_invoice_intake_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_PROFILE = UUID("76767676-7676-4767-8676-767676767676")

#: A Spanish libro registro whose column names only the mapping lane can read.
_LIBRO = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"


def test_composed_wizard_and_book_use_retained_pin_and_reopen_canonical_encrypted_audit(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ...domain.calculations.registry import authority

    # Both services must use the retained pin; the standalone fallback remains
    # available to ordinary callers, but is not a worker's generation lease.
    def fallback():
        pytest.fail("worker intake acquired a new descriptor-following authority")

    monkeypatch.setattr(authority, "bundled_indexed_authority", fallback)
    admissions: list[str] = []
    commits = 0

    def commit(save: Callable[[], None]) -> None:
        nonlocal commits
        save()
        commits += 1

    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        validating_governed_facts(authority_operation),
    ):
        baseline_events = BucketEventHistoryRepository(objects=profile.repository).load()
        baseline_event_ids = frozenset(baseline_events.events)
        baseline_event_digest = sha256_hex(canonical_json_bytes(baseline_events.model_dump(mode="json")))
        ports = build_invoice_intake_ports(
            profile_id=_PROFILE,
            operation=authority_operation,
            commit=commit,
            admit_provider=lambda: admissions.append("provider"),
        )
        assert ports.profile_id == _PROFILE and ports.operation is authority_operation and not admissions
        with pytest.raises(ProfileAccessRefusedError):
            build_invoice_intake_ports(
                profile_id=uuid4(),
                operation=authority_operation,
                commit=commit,
                admit_provider=lambda: admissions.append("foreign"),
            )
        creation = ports.creation()
        wizard = create_invoice_via_wizard(
            bucket_id=str(_PROFILE),
            kind=InvoiceKind.RECEIVED,
            counterparty_nif="A58818501",
            counterparty_name="Synthetic supplier",
            invoice_number="PIN-WIZARD",
            invoice_date="2026-05-01",
            taxable_base="100.00",
            iva_rate="21",
            currency="EUR",
            country_code="ES",
            series="S",
            recargo_amount="5.20",
            ports=creation,
            operation=authority_operation,
        )
        path = tmp_path / "synthetic.csv"
        payload = b"counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\nA58818501,Supplier,PIN-BOOK,2026-05-01,100.00,21\n"
        path.write_bytes(payload)
        source = read_bulk_invoice_import_source(path, mapper=ports.mapper, expected_sha256=sha256_hex(payload))
        imported = import_invoices_from_rows(
            source,
            bucket_id=str(_PROFILE),
            kind=InvoiceKind.RECEIVED,
            declared_country="ES",
            ports=creation,
            operation=authority_operation,
        )
        assert not wizard.already_existed and imported.created == 1 and commits == 2
        reopened = InvoiceCatalogueRepository(objects=profile.repository).load()
        assert reopened.get(wizard.invoice.invoice_id) == wizard.invoice
        assert reopened.get(imported.created_invoice_ids[0]) is not None
        reopened_events = BucketEventHistoryRepository(objects=profile.repository).load()
        assert baseline_event_ids <= reopened_events.events.keys()
        retained = BucketEventHistoryCatalogue(events={key: reopened_events.events[key] for key in baseline_event_ids})
        assert sha256_hex(canonical_json_bytes(retained.model_dump(mode="json"))) == baseline_event_digest
        new_events = tuple(reopened_events.events[key] for key in reopened_events.events.keys() - baseline_event_ids)
        assert len(new_events) == 2
        assert {event.object_id for event in new_events} == {wizard.invoice.invoice_id, *imported.created_invoice_ids}
        assert all(event.event_type is BucketEventType.PAYABLE_INVOICE_CREATED for event in new_events)
    assert admissions == ["provider"]


@pytest.mark.parametrize(
    ("refusal", "condition"),
    [
        (ModelRunRefusalCode.MODEL_NOT_INSTALLED, LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED),
        (ModelRunRefusalCode.NO_SELECTION, LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED),
    ],
    ids=["model-not-installed", "no-selection"],
)
def test_a_book_whose_mapping_reader_is_missing_refuses_with_its_typed_verdict(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    refusal: ModelRunRefusalCode,
    condition: LLMPreconditionCondition,
) -> None:
    """The composed mapper reports the reader, and the book refuses with its verdict rather than missing columns.

    The agent service refuses the column-mapping role's lookup. A selected
    model the local server does not hold is named in the verdict; a role
    with no selection says the role needs one. Either way nothing is run.
    """
    admissions: list[str] = []
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)),
        override_settings(
            cadrumo_llm_cache_dir=tmp_path / "cache",
            cadrumo_llm_usage_dir=tmp_path / "usage",
            cadrumo_llm_run_record_dir=tmp_path / "run-record",
        ),
        serving_agent(lane=ON_HOST_LANE, lookup_refusal=refusal) as service,
    ):
        ports = build_invoice_intake_ports(
            profile_id=_PROFILE,
            operation=authority_operation,
            commit=lambda _save: pytest.fail("a book that was never read reached a write"),
            admit_provider=lambda: admissions.append("provider"),
        )
        with pytest.raises(LedgerImportReaderUnavailableError) as raised:
            read_bulk_invoice_import_source(_LIBRO, mapper=ports.mapper)
        assert ports.mapping_reasons() == ()

    assert admissions == ["provider"]
    assert service.lookups == [ModelRole.COLUMN_ROLE_MAPPING]
    assert service.runs == []
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition.value
    facts = {key: value for evidence in verdict.evidence for key, value in evidence.values.items()}
    assert facts["model_run_refusal"] == refusal.value
    assert facts["model_role"] == ModelRole.COLUMN_ROLE_MAPPING.value
    if refusal is ModelRunRefusalCode.NO_SELECTION:
        assert facts["role_selection_required"] is True
    detail = build_operation_error_detail(raised.value)
    assert detail is not None
    assert detail.error_code == "REFUSED_LEDGER_IMPORT_READER"
    projected = detail.precondition_verdict()
    assert projected is not None
    assert projected.failed_condition_id == condition.value
    assert verdict.action is None
    assert projected.action is None
