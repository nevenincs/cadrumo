"""What the known-values read says about real encrypted records, counted by hand from the seeds."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction

from ...adapters.persistence.profile.actividad_asset import ActividadAssetHistoryRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.ledger.known_values_operation import (
    KNOWN_VALUE_MAX_LENGTH,
    KNOWN_VALUES_PER_KIND,
    LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID,
    LedgerKnownValuesExecutor,
    LedgerKnownValuesPorts,
    LedgerKnownValuesProjection,
    LedgerKnownValuesRequest,
    build_ledger_known_values_definition,
    build_ledger_known_values_registration,
)
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.owner import OperationExecutorContext
from ...application.operations.registry import OperationRegistry
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.ledger_known_values import LedgerKnownValueKind
from ...core.operations import OperationEffect, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.schema import InvoiceKind
from ...domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ...domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.m210_income_classification import M210IncomeClassification
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..invoice_inspection_composition import build_invoice_inspection_read_ports
from ..ledger_action_composition import compose_ledger_read_ports
from .supervised_operation_rig import operation_access_context

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_FLOOR = filing_year_envelope().floor
_CREATED = datetime(_YEAR + 1, 1, 1, 9, 0, tzinfo=UTC)

_PROFILE = UUID("77777777-7777-4777-8777-777777777777")
_BUCKET = str(_PROFILE)
_OTHER_PROFILE = UUID("88888888-8888-4888-8888-888888888888")


def _movement(
    row: str,
    *,
    booked: date = date(_YEAR, 3, 1),
    counterparty: str = "",
    description: str = "movimiento",
    **fields: object,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=row,
        booked_date=booked,
        amount=Decimal("10.00"),
        currency="EUR",
        counterparty=counterparty,
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_CREATED,
            provider_name="synthetic provider",
        ),
        raw_fields={"Concepto": row},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": _CREATED,
            "modified_at": _CREATED,
            **fields,
        }
    )


def _invoice(number: str, *, name: str, tax_id: str | None, issued: date) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": _BUCKET,
            "invoice_number": number,
            "issued_at": issued,
            "counterparty_name": name,
            "counterparty_tax_id": tax_id,
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine(
                    description="synthetic line",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    subtotal=Decimal("100.00"),
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=Decimal("21.00"),
                ),
            ),
        }
    )


def _revision(asset_id: str, *, reference: str, in_service: date) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id=f"evidence-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("1000"),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="reviewed allocation source",
        ),
        in_service_date=in_service,
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
            research_development_evidence_reference=reference,
        ),
    )


@dataclass(slots=True)
class _Operands:
    """Hold what the executor publishes, as the supervisor's confidential store would."""

    stored: list[BaseModel] = field(default_factory=list)

    async def put(self, result: BaseModel, *, written_at: datetime) -> str:
        del written_at
        self.stored.append(result)
        return "result"


@dataclass(slots=True)
class _Events:
    effects: list[OperationEffect] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)

    async def phase(self, code: str) -> None:
        self.phases.append(code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


def _read(operation: PinnedAuthorityOperation, *kinds: LedgerKnownValueKind) -> LedgerKnownValuesProjection:
    # The supervisor's journal is covered by the registered conformance scenario.
    """Run the executor over the production ports the composition binds."""
    executor = LedgerKnownValuesExecutor(
        LedgerKnownValuesPorts(
            ledger=compose_ledger_read_ports,
            invoices=build_invoice_inspection_read_ports,
            asset_history=lambda bucket_id: ActividadAssetHistoryRepository(bucket_id=bucket_id),
        )
    )
    request = OperationRequest[LedgerKnownValuesRequest](
        definition_id=LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(_BUCKET),
        payload=LedgerKnownValuesRequest(profile_id=_PROFILE, kinds=kinds),
    )
    operands, events = _Operands(), _Events()
    context = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
        ),
        events=events,
        operands=operands,
        authority_operation=operation,
    )
    asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    assert events.effects == [OperationEffect.NONE]
    (result,) = operands.stored
    assert isinstance(result, LedgerKnownValuesProjection)
    assert result.profile_id == _PROFILE
    return result


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        yield


def _save_movements(rows: Iterable[Transaction]) -> None:
    TransactionCatalogueRepository(bucket_id=_BUCKET).save(TransactionCatalogue.from_transactions(rows))


def _save_invoices(*rows: Invoice) -> None:
    InvoiceCatalogueRepository(bucket_id=_BUCKET).save(InvoiceCatalogue(invoices={row.invoice_id: row for row in rows}))


@pytest.mark.usefixtures("profile")
def test_each_kind_counts_its_own_distinct_values_across_the_whole_history(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Spelling variants fold together, the newest spelling is shown, and split parents stay out."""
    _save_movements(
        (
            _movement("a", booked=date(_YEAR, 1, 2), description="Alquiler oficina", counterparty="Casero SL"),
            _movement("b", booked=date(_YEAR, 6, 1), description="ALQUILER  OFICINA", group_label="Oficina"),
            _movement("c", booked=date(_YEAR, 3, 1), description="Luz", group_label="oficina"),
            _movement("d", booked=date(_YEAR, 4, 1), description="LUZ", group_label=None),
            _movement(
                "split-parent",
                booked=date(_YEAR, 9, 1),
                description="Texto del padre",
                group_label="Grupo del padre",
                lifecycle_state=TransactionLifecycleState.SPLIT,
            ),
        )
    )

    result = _read(
        authority_operation,
        LedgerKnownValueKind.DESCRIPTION,
        LedgerKnownValueKind.GROUP_LABEL,
    )

    assert [(row.text, row.uses, row.last_used) for row in result.descriptions] == [
        ("ALQUILER  OFICINA", 2, date(_YEAR, 6, 1)),
        ("LUZ", 2, date(_YEAR, 4, 1)),
    ]
    assert result.descriptions[0].counterparty == "Casero SL"
    assert [(row.text, row.uses, row.last_used) for row in result.group_labels] == [
        ("Oficina", 2, date(_YEAR, 6, 1)),
    ]
    assert result.truncated == ()
    # Only the kinds asked for are read and returned.
    assert result.counterparties == ()
    assert result.m210_payers == ()
    assert result.asset_references == ()


@pytest.mark.usefixtures("profile")
def test_a_movement_name_joins_the_only_tax_id_it_can_mean(authority_operation: PinnedAuthorityOperation) -> None:
    """One folded name under one tax id joins; the movement name stays with that party."""
    _save_invoices(_invoice("U-1", name="Gestoría Núñez SL", tax_id="B00015016", issued=date(_YEAR, 1, 10)))
    _save_movements(
        (
            _movement("named", booked=date(_YEAR, 5, 1), counterparty="GESTORIA NUNEZ SL"),
            _movement("nobody", booked=date(_YEAR, 7, 1), counterparty="Sin Factura SA"),
        )
    )

    result = _read(authority_operation, LedgerKnownValueKind.COUNTERPARTY)

    assert [(row.name, row.tax_id, row.country, row.uses, row.last_used) for row in result.counterparties] == [
        ("Sin Factura SA", None, None, 1, date(_YEAR, 7, 1)),
        ("GESTORIA NUNEZ SL", "B00015016", "ES", 2, date(_YEAR, 5, 1)),
    ]


@pytest.mark.usefixtures("profile")
def test_a_name_under_two_tax_ids_gives_a_movement_neither(authority_operation: PinnedAuthorityOperation) -> None:
    """The ambiguous name keeps both invoice parties, and its movement joins neither."""
    _save_invoices(
        _invoice("A-1", name="Comercial Duero SL", tax_id="B00015016", issued=date(_YEAR, 1, 10)),
        _invoice("A-2", name="comercial duero sl", tax_id="B00010157", issued=date(_YEAR, 2, 10)),
    )
    _save_movements((_movement("ambiguous", booked=date(_YEAR, 5, 1), counterparty="Comercial Duero SL"),))

    result = _read(authority_operation, LedgerKnownValueKind.COUNTERPARTY)

    assert [(row.name, row.tax_id, row.uses) for row in result.counterparties] == [
        ("Comercial Duero SL", None, 1),
        ("comercial duero sl", "B00010157", 1),
        ("Comercial Duero SL", "B00015016", 1),
    ]


@pytest.mark.usefixtures("profile")
def test_the_cap_keeps_the_newest_and_says_so_only_when_something_was_cut(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """One past the cap is truncated and drops the oldest; exactly the cap is not truncated."""
    rows = [
        _movement(
            f"group-{index}", booked=date(_FLOOR, 1, 1).replace(year=_FLOOR + index // 300), group_label=f"g{index:04}"
        )
        for index in range(KNOWN_VALUES_PER_KIND)
    ]
    _save_movements(
        (
            *rows,
            _movement("no-group", booked=date(_FLOOR - 1, 1, 1), description="Una sola"),
        )
    )
    at_the_cap = _read(authority_operation, LedgerKnownValueKind.GROUP_LABEL)
    assert len(at_the_cap.group_labels) == KNOWN_VALUES_PER_KIND
    assert at_the_cap.truncated == ()

    _save_movements(
        (
            *rows,
            _movement("past-the-cap", booked=date(_FLOOR - 1, 1, 1), group_label="la mas antigua"),
        )
    )
    past_the_cap = _read(authority_operation, LedgerKnownValueKind.GROUP_LABEL, LedgerKnownValueKind.DESCRIPTION)
    assert len(past_the_cap.group_labels) == KNOWN_VALUES_PER_KIND
    assert "la mas antigua" not in {row.text for row in past_the_cap.group_labels}
    assert past_the_cap.truncated == (LedgerKnownValueKind.GROUP_LABEL,)


@pytest.mark.usefixtures("profile")
def test_a_text_too_long_to_return_is_said_rather_than_silently_dropped(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A fitting value at the bound stays; the one past it leaves and the kind reads as truncated."""
    at_the_bound = "x" * KNOWN_VALUE_MAX_LENGTH
    _save_movements(
        (
            _movement("fits", description=at_the_bound),
            _movement("long", description="y" * (KNOWN_VALUE_MAX_LENGTH + 1)),
        )
    )

    result = _read(authority_operation, LedgerKnownValueKind.DESCRIPTION)

    assert [row.text for row in result.descriptions] == [at_the_bound]
    assert result.truncated == (LedgerKnownValueKind.DESCRIPTION,)


@pytest.mark.usefixtures("profile")
def test_m210_values_and_asset_references_come_from_their_own_stated_fields(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The nonresident payer and asset read from the classification; references read from the revisions."""
    classification = M210IncomeClassification(
        official_tipo_renta_code="01",
        gross_income_amount=Decimal("100"),
        applicable_rate=Decimal("0.19"),
        payer_id="PAGADOR-7",
        asset_or_right_id="BIEN-3",
    )
    _save_movements(
        (
            _movement("m210", booked=date(_YEAR, 8, 1), m210_income_classification=classification),
            _movement("plain", booked=date(_YEAR, 9, 1), description="ignored here"),
        )
    )
    assets = ActividadAssetHistoryRepository(bucket_id=_BUCKET)
    assets.append_revision(_revision("asset-a", reference="EXP-2024/17", in_service=date(_YEAR, 1, 1)))
    assets.append_revision(_revision("asset-b", reference="exp-2024/17", in_service=date(_YEAR, 3, 1)))
    assets.append_revision(_revision("asset-c", reference="CERT-9", in_service=date(_YEAR, 2, 1)))

    result = _read(
        authority_operation,
        LedgerKnownValueKind.M210_PAYER,
        LedgerKnownValueKind.M210_ASSET,
        LedgerKnownValueKind.ASSET_REFERENCE,
    )

    assert [(row.text, row.uses, row.last_used) for row in result.m210_payers] == [("PAGADOR-7", 1, date(_YEAR, 8, 1))]
    assert [(row.text, row.uses, row.last_used) for row in result.m210_assets] == [("BIEN-3", 1, date(_YEAR, 8, 1))]
    assert [(row.text, row.uses, row.last_used) for row in result.asset_references] == [
        ("exp-2024/17", 2, date(_YEAR, 3, 1)),
        ("CERT-9", 1, date(_YEAR, 2, 1)),
    ]


def test_a_request_names_at_least_one_kind_and_each_once() -> None:
    with pytest.raises(ValidationError):
        LedgerKnownValuesRequest(profile_id=_PROFILE, kinds=())
    with pytest.raises(ValidationError):
        LedgerKnownValuesRequest(
            profile_id=_PROFILE,
            kinds=(LedgerKnownValueKind.DESCRIPTION, LedgerKnownValueKind.DESCRIPTION),
        )


def _access_request(*, payload_profile: UUID, subject_profile: UUID) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile)),
        payload=LedgerKnownValuesRequest(profile_id=payload_profile, kinds=(LedgerKnownValueKind.DESCRIPTION,)),
    )


def _unexpected_ports(*args: object, **kwargs: object) -> Any:
    raise AssertionError(f"admission composed ports with {args!r} {kwargs!r}")


def _registration(*, context_profile: UUID = _PROFILE) -> tuple[OperationRegistry, OperationAccessContext]:
    definition = build_ledger_known_values_definition(
        LedgerKnownValuesPorts(ledger=_unexpected_ports, invoices=_unexpected_ports, asset_history=_unexpected_ports)
    )
    registration = build_ledger_known_values_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, operation_access_context(
        registration.contract, profile_id=context_profile, action=AccessAction.RESULT
    )


@pytest.mark.parametrize(
    ("context_profile", "payload_profile", "subject_profile"),
    [
        pytest.param(_OTHER_PROFILE, _PROFILE, _PROFILE, id="admitted-under-another-profile"),
        pytest.param(_PROFILE, _OTHER_PROFILE, _PROFILE, id="payload-names-another-profile"),
        pytest.param(_PROFILE, _PROFILE, _OTHER_PROFILE, id="subject-names-another-profile"),
    ],
)
def test_another_profile_is_refused_before_any_port_is_built(
    context_profile: UUID, payload_profile: UUID, subject_profile: UUID
) -> None:
    registry, context = _registration(context_profile=context_profile)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=_access_request(payload_profile=payload_profile, subject_profile=subject_profile),
            context=context,
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_access_spans_every_period_because_the_values_do() -> None:
    registry, context = _registration()

    resolved = resolve_operation_access(
        registry=registry,
        request=_access_request(payload_profile=_PROFILE, subject_profile=_PROFILE),
        context=context,
    )

    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == frozenset()
    assert resolved.policy.requires_all_periods is True
    assert AccessAction.COMMIT not in resolved.policy.actions
