"""Replay a canonical persona into a registered profile through production operations only.

A persona (``dev/fixtures/personas``, read by :mod:`cadrumo.tests.personas`)
reaches its profile the way an operator's input does: the registered wizard
patch, field and repeatable-row mutations, the household replacements, the
statement import, single classification, and evidence intake and attachment,
each submitted to the production registry's supervisor and settled. Nothing is
written to storage by any other route. A persona block that no operation can
record is returned in :attr:`MaterialisedPersona.not_loaded` with its reason,
never written another way.

Every operation runs at the persona's scenario instant, including the
registration of the profile it runs against.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from functools import cache
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
from ...adapters.persistence.profile.tests.sealed_profile_world import (
    SealedProfileWorld,
    copied_profile_world,
    sealed_profile_world,
)
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from ...adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from ...application.invoices.catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    InvoiceAddRequest,
    InvoiceAddResult,
)
from ...application.ledger.actions_common import display_decimal
from ...application.ledger.actions_import import LedgerProviderID
from ...application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LedgerAttachRequest,
)
from ...application.ledger.classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyPatch,
    LedgerClassifyPatchField,
    LedgerClassifyRequest,
)
from ...application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddProjection,
    LedgerEvidenceAddRequest,
)
from ...application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    LedgerImportRequest,
    LedgerImportResultProjection,
)
from ...application.ledger.link_operation import LEDGER_LINK_OPERATION_DEFINITION_ID, LedgerLinkRequest
from ...application.operations.composition import OperationComposedServices, compose_operation_services
from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.public_scalar import PublicDecimal
from ...application.operations.registry import OperationRegistry
from ...application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.descendant_rows import ProfileDescendantFact, ProfileDescendantRow
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,
    PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    ProfileAscendantsOperationRequest,
    ProfileDescendantsOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfilePatchOperationRequest,
    ProfilePatchValue,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowValue,
)
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.registration import register_profile_with_credentials
from ...application.wizard.imputation_election import YEAR_QUESTION_ID
from ...core.auth_provider import AuthProviderKind
from ...core.config import override_settings
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import frozen_clock, now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.irpf_categories import is_net_paid_related_category
from ...domain.user_profile.values import UserProfileRecord
from ...tests.personas import (
    HouseholdMember,
    IdentityRef,
    LedgerRow,
    Persona,
    PersonaDate,
    ProfileValue,
    YearEnvelope,
    read_persona,
)
from ..ledger_action_composition import compose_ledger_action_ports
from ..operation_composition import build_production_operation_registry

PERSONA_ACTOR = "operator:persona"
"""The actor every replayed operation is submitted under."""

SCENARIO_TIME = time(9, 0, tzinfo=UTC)
"""The time of day of every persona's scenario instant; the date is the persona's ``[clock].as_of``."""

_PROFILE_CREDENTIAL = "persona-materialisation-passphrase"
_STATEMENT_HEADER = "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda;Referencia"


class PersonaMaterialisationError(RuntimeError):
    """A production operation refused a persona fact; the catalogue or the operation must change."""


@dataclass(frozen=True, slots=True)
class NotLoaded:
    """A persona block no production operation recorded, and why."""

    block: str
    reason: str


@dataclass(frozen=True, slots=True)
class PersonaWorld:
    """One registered, empty profile and the supervisor that runs operations against it."""

    profile_id: UUID
    storage_root: Path
    workdir: Path
    as_of: datetime
    envelope: YearEnvelope
    services: OperationComposedServices
    registry: OperationRegistry
    operation: PinnedAuthorityOperation


@dataclass(frozen=True, slots=True)
class MaterialisedPersona:
    """What replaying a persona left in its profile."""

    persona: Persona
    world: PersonaWorld
    transactions: Mapping[str, str]
    """Ledger ``ref`` to the imported transaction id."""
    invoices: Mapping[str, str]
    """Ledger ``ref`` to the recorded and linked invoice id."""
    evidence: Mapping[str, str]
    """Document id to the stored evidence id."""
    not_loaded: tuple[NotLoaded, ...]


def year_envelope(operation: PinnedAuthorityOperation) -> YearEnvelope:
    """The registry's supported filing-year envelope, as the persona reader takes it."""
    support = operation.supported_filing_years()
    return YearEnvelope(floor=support.floor, horizon=support.horizon)


def scenario_instant(persona: Persona, envelope: YearEnvelope) -> datetime:
    """The instant a persona's operations run at."""
    return datetime.combine(persona.as_of.resolve(envelope), SCENARIO_TIME)


@cache
def _registry() -> OperationRegistry:
    return build_production_operation_registry()


def _registered_world(as_of: datetime) -> SealedProfileWorld:
    create_context, decode_context = profile_authority_contexts()

    def register() -> str:
        return register_profile_with_credentials(
            label="persona",
            passphrase=_PROFILE_CREDENTIAL,
            profile_create_context=create_context,
            profile_decode_context=decode_context,
        ).profile_id

    return sealed_profile_world(("persona world", str(create_context.generation), as_of.isoformat()), register)


@contextmanager
def persona_world(tmp_path: Path, *, as_of: datetime) -> Generator[PersonaWorld]:
    """Open a registered empty profile and a production supervisor over it, frozen at ``as_of``."""
    _create_context, decode_context = profile_authority_contexts()
    with (
        frozen_clock(as_of),
        override_settings(cadrumo_auth_provider=AuthProviderKind.CERTIFICATE, cadrumo_certificate_path=None),
    ):
        world = _registered_world(as_of)
        with (
            copied_profile_world(world, tmp_path / "runtime", profile_decode_context=decode_context) as (
                root,
                profile_id,
            ),
            profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects,
            bundled_indexed_authority().operation() as operation,
        ):
            registry = _registry()
            journal = OperationJournalRepository(storage_root=root / "operations")
            operands = operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects))
            services = compose_operation_services(
                registry=registry,
                authority_operation=operation,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
                operands=operands,
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
            workdir = tmp_path / "inputs"
            workdir.mkdir(parents=True, exist_ok=True)
            try:
                yield PersonaWorld(
                    profile_id=profile_id,
                    storage_root=root,
                    workdir=workdir,
                    as_of=as_of,
                    envelope=year_envelope(operation),
                    services=services,
                    registry=registry,
                    operation=operation,
                )
            finally:
                asyncio.run(services.shutdown())
                reset_test_profile_session()


# -- one settled operation -----------------------------------------------------------------------------------------


def settle_operation(world: PersonaWorld, definition_id: str, payload: BaseModel) -> BaseModel | None:
    """Submit one registered operation, settle it, refuse anything but success, and return its public result."""

    async def settle() -> OperationPublicProjectionV1:
        services = world.services
        submitted = await services.submission.submit(
            OperationRequest(
                definition_id=definition_id,
                subject_ref=profile_operation_subject(str(world.profile_id)),
                payload=payload,
            ),
            actor_ref=PERSONA_ACTOR,
        )
        operation_id = submitted.receipt.operation_id
        await services.submission.start(operation_id)
        await services.submission.settled(operation_id)
        observed = await services.observation.observe(
            OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
        )
        if not isinstance(observed, OperationObservationSuccessV1):
            raise PersonaMaterialisationError(f"{definition_id} could not be observed")
        return observed.projection

    terminal = asyncio.run(settle())
    result = _public_result(world, terminal)
    if terminal.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        detail = "no detail" if result is None else result.model_dump_json(exclude={"profile_id"})
        raise PersonaMaterialisationError(
            f"{definition_id} settled {terminal.terminal_condition} ({terminal.failure_error_code}): {detail}"
        )
    return result


def run_operation[Projection: BaseModel](
    world: PersonaWorld, definition_id: str, payload: BaseModel, projection: type[Projection]
) -> Projection:
    """Settle one registered operation and return its public result as ``projection``."""
    result = settle_operation(world, definition_id, payload)
    if not isinstance(result, projection):
        raise PersonaMaterialisationError(f"{definition_id} published no {projection.__name__}")
    return result


def _public_result(world: PersonaWorld, terminal: OperationPublicProjectionV1) -> BaseModel | None:
    """The public result, or refusal detail, a settled operation publishes, in its registered model."""
    contract = terminal.definition_contract
    if contract.result_schema is None or (terminal.result_ref is None and terminal.refusal_ref is None):
        return None
    registration = world.registry.lookup_public_registration(terminal.definition_id)
    (model,) = (
        binding.model_type for binding in registration.schema_bindings if binding.identity == contract.result_schema
    )
    resolved = asyncio.run(
        world.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=terminal.operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
            model,
        )
    )
    return resolved.projection if isinstance(resolved, OperationResultProjectionSuccessV1) else None


def load_profile_record(world: PersonaWorld) -> UserProfileRecord:
    """Read the profile's current record, which every profile mutation names as its baseline."""
    return ProfileRecordRepository.for_current_session(
        world.profile_id, profile_decode_context=world.operation.profile_decode_context()
    ).load(world.profile_id)


# -- persona values as operations take them ------------------------------------------------------------------------


def submitted_answer(persona: Persona, value: ProfileValue, envelope: YearEnvelope) -> str:
    """Render one ``[profile]`` value as the profile patch takes it, as the catalogue README states."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):
        return ",".join(value)
    if isinstance(value, IdentityRef):
        return persona.identity(value)
    return value.resolve(envelope).isoformat()


def patch_answers(persona: Persona, envelope: YearEnvelope) -> tuple[tuple[str, str], ...]:
    """Every wizard answer the persona's patch submits: its ``[profile]`` answers, then its elections and their year."""
    answers = [(answer.question_id, submitted_answer(persona, answer.value, envelope)) for answer in persona.profile]
    years = {str(election.year.resolve(envelope)) for election in persona.elections}
    if len(years) > 1:
        raise PersonaMaterialisationError(f"{persona.id}: one patch states one election year, found {sorted(years)}")
    answers.extend((election.question, election.value) for election in persona.elections)
    answers.extend((YEAR_QUESTION_ID, year) for year in years)
    return tuple(answers)


def household_leaves(persona: Persona, member: HouseholdMember, envelope: YearEnvelope) -> tuple[tuple[str, str], ...]:
    """One household row as the descendant and ascendant operations take it, with its identity as ``nif``."""
    leaves = [
        (key, value.resolve(envelope).isoformat() if isinstance(value, PersonaDate) else value)
        for key, value in member.leaves
    ]
    if member.identity is not None:
        leaves.append(("nif", persona.identity(member.identity)))
    return tuple(leaves)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _statement(persona: Persona, envelope: YearEnvelope) -> str:
    """The persona's bank movements in the statement columns ``app ledger import --file`` reads."""
    lines = [_STATEMENT_HEADER]
    balance = Decimal("0.00")
    for row in sorted(persona.ledger, key=lambda item: item.operation_date(envelope)):
        balance += row.amount
        day = row.operation_date(envelope).strftime("%d/%m/%Y")
        lines.append(
            ";".join(
                (
                    day,
                    day,
                    row.description,
                    _decimal_text(row.amount).replace(".", ","),
                    _decimal_text(balance).replace(".", ","),
                    row.currency,
                    row.ref,
                )
            )
        )
    return "\n".join(lines) + "\n"


def _carries_iva_amount(row: LedgerRow) -> bool:
    """Whether single classification can carry the row's IVA cuota.

    Classification checks base, cuota and recargo against the cash movement.
    It takes no recargo, reconstitutes no self-assessed intra-community service
    cuota, and accepts a payment net of retención only under the expense
    categories the registry relates to withheld activity income, so any such
    row is refused with its cuota and is classified without it.
    """
    reverse_charge = row.iva_category is not None and row.iva_category.endswith("_reverse_charge")
    withheld_payment = row.retencion_amount is not None and row.amount < 0
    return (
        row.iva_amount is not None
        and row.recargo_amount is None
        and not reverse_charge
        and (not withheld_payment or is_net_paid_related_category(row.category_id))
    )


def _classify_patch(
    persona: Persona, row: LedgerRow
) -> tuple[LedgerClassifyPatch, tuple[LedgerClassifyPatchField, ...]]:
    values: dict[LedgerClassifyPatchField, str] = {"business_classification": row.classification}
    counterparty = None if row.counterparty is None else persona.identities.role(row.counterparty)
    if counterparty is not None and counterparty.country is not None:
        values["counterparty_country"] = counterparty.country
    optional: tuple[tuple[LedgerClassifyPatchField, str | Decimal | None], ...] = (
        ("category_id", row.category_id),
        ("irpf_category", row.irpf_category),
        ("iva_category", row.iva_category),
        ("taxable_base", row.taxable_base),
        ("iva_rate", row.iva_rate),
        ("iva_amount", row.iva_amount if _carries_iva_amount(row) else None),
        ("deduction_fact_kind", row.deduction_kind),
    )
    for field, value in optional:
        if value is not None:
            values[field] = display_decimal(value) if isinstance(value, Decimal) else value
    return LedgerClassifyPatch.model_validate(values), tuple(sorted(values))


def _public_decimal(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=str(value))


def _public_percentage(fraction: Decimal | None) -> PublicDecimal | None:
    """A ledger fraction as the invoice operation takes a rate: a percentage."""
    return None if fraction is None else PublicDecimal(decimal=str(fraction * 100))


def _invoice_request(persona: Persona, row: LedgerRow, world: PersonaWorld) -> InvoiceAddRequest | None:
    """The invoice behind a row as ``ledger invoice add`` records it; ``None`` for no invoice or no named party."""
    if row.invoice_kind is None or row.invoice_number is None or row.counterparty is None:
        return None
    counterparty = persona.identities.role(row.counterparty)
    name = counterparty.legal_name or f"{counterparty.field('name')} {counterparty.field('surnames')}"
    return InvoiceAddRequest(
        profile_id=world.profile_id,
        kind=InvoiceKind(row.invoice_kind),
        counterparty_name=name,
        counterparty_tax_id=counterparty.value,
        counterparty_country=counterparty.country or "ES",
        invoice_number=row.invoice_number,
        issued_at=row.operation_date(world.envelope),
        taxable_base=_public_decimal(row.taxable_base),
        iva_rate=_public_percentage(row.iva_rate),
        currency=row.currency,
        iva_category=row.iva_category,
        retention_rate=_public_decimal(row.retencion_rate),
        retention_amount=_public_decimal(row.retencion_amount),
        recargo_amount=_public_decimal(row.recargo_amount),
    )


# -- replay --------------------------------------------------------------------------------------------------------


def _replay_profile(persona: Persona, world: PersonaWorld) -> None:
    envelope = world.envelope
    record = load_profile_record(world)
    settle_operation(
        world,
        PROFILE_PATCH_OPERATION_DEFINITION_ID,
        ProfilePatchOperationRequest(
            profile_id=world.profile_id,
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
            values=tuple(
                ProfilePatchValue(question_id=question_id, value=value)
                for question_id, value in patch_answers(persona, envelope)
            ),
        ),
    )
    for field in persona.fields:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
            ProfileFieldMutationOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                path=field.path,
                value=field.value,
            ),
        )
    for activity in persona.activities:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
            ProfileRepeatableRowMutationOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                section_key="activities",
                values=tuple(ProfileRepeatableRowValue(field_key=key, value=value) for key, value in activity.values),
            ),
        )
    if persona.descendants:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
            ProfileDescendantsOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                descendants=tuple(
                    ProfileDescendantRow(
                        facts=tuple(
                            ProfileDescendantFact(field_key=key, value=value)
                            for key, value in household_leaves(persona, member, envelope)
                        )
                    )
                    for member in persona.descendants
                ),
            ),
        )
    if persona.ascendants:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,
            ProfileAscendantsOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                ascendants=tuple(
                    ProfileAscendantRow(
                        facts=tuple(
                            ProfileAscendantFact(field_key=key, value=value)
                            for key, value in household_leaves(persona, member, envelope)
                        )
                    )
                    for member in persona.ascendants
                ),
            ),
        )


def _imported_transactions(persona: Persona, world: PersonaWorld) -> dict[str, str]:
    """Import the statement and map each ledger ref to the transaction it became."""
    statement = world.workdir / f"{persona.id}-statement.csv"
    statement.write_text(_statement(persona, world.envelope), encoding="utf-8", newline="\n")
    result = run_operation(
        world,
        LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        LedgerImportRequest(profile_id=world.profile_id, files=(statement,), provider=LedgerProviderID.CSV),
        LedgerImportResultProjection,
    )
    if result.imported != len(persona.ledger) or result.refused_files:
        raise PersonaMaterialisationError(
            f"{persona.id}: imported {result.imported} of {len(persona.ledger)} rows, refused {result.refused_files}"
        )
    stored = compose_ledger_action_ports(
        bucket_id=str(world.profile_id), operation=world.operation
    ).transaction_repository.load()
    refs = {row.ref for row in persona.ledger}
    by_ref = {
        transaction.raw.provider_transaction_id: transaction_id
        for transaction_id, transaction in stored.transactions.items()
        if transaction.raw.provider_transaction_id in refs
    }
    if set(by_ref) != refs:
        raise PersonaMaterialisationError(f"{persona.id}: refs not carried by the import: {sorted(refs - set(by_ref))}")
    return by_ref


def _replay_ledger(persona: Persona, world: PersonaWorld, transactions: Mapping[str, str]) -> dict[str, str]:
    """Classify every row, then record each row's invoice and link it; returns ledger ref to invoice id."""
    for row in persona.ledger:
        patch, fields = _classify_patch(persona, row)
        settle_operation(
            world,
            LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
            LedgerClassifyRequest(
                profile_id=world.profile_id,
                transaction_id=transactions[row.ref],
                patch=patch,
                patch_fields=fields,
                actor=PERSONA_ACTOR,
            ),
        )
    invoices: dict[str, str] = {}
    for row in persona.ledger:
        request = _invoice_request(persona, row, world)
        if request is None:
            continue
        added = run_operation(world, INVOICE_ADD_OPERATION_DEFINITION_ID, request, InvoiceAddResult)
        if added.invoice is None:
            raise PersonaMaterialisationError(f"{persona.id} {row.ref}: no invoice was created")
        invoices[row.ref] = added.invoice.invoice_id
        settle_operation(
            world,
            LEDGER_LINK_OPERATION_DEFINITION_ID,
            LedgerLinkRequest(
                profile_id=world.profile_id,
                transaction_id=transactions[row.ref],
                invoice_id=added.invoice.invoice_id,
                actor=PERSONA_ACTOR,
            ),
        )
    return invoices


def _replay_documents(persona: Persona, world: PersonaWorld, transactions: Mapping[str, str]) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for document in persona.documents:
        added = run_operation(
            world,
            LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
            LedgerEvidenceAddRequest(
                profile_id=world.profile_id,
                source_path=str(document.path),
                source_directory=str(document.path.parent),
                notes=f"persona {persona.id} document {document.id} ({document.relation})",
                idempotency_key=f"persona-{persona.id}-{document.id}",
            ),
            LedgerEvidenceAddProjection,
        )
        evidence[document.id] = added.record.evidence_id
        for ref in document.attach_to:
            settle_operation(
                world,
                LEDGER_ATTACH_OPERATION_DEFINITION_ID,
                LedgerAttachRequest(
                    profile_id=world.profile_id,
                    transaction_id=transactions[ref],
                    purchase_invoice_evidence_id=added.record.evidence_id,
                    actor=PERSONA_ACTOR,
                ),
            )
    return evidence


def _refs(rows: list[LedgerRow]) -> str:
    return ", ".join(row.ref for row in rows)


def _not_loaded(persona: Persona) -> tuple[NotLoaded, ...]:
    """The persona facts no production operation recorded, and why."""
    found = [
        NotLoaded(block=block, reason="no production operation records this block")
        for block in persona.declared_blocks()
    ]
    if persona.withholding_certificates:
        found.append(
            NotLoaded(
                block="withholding_certificates",
                reason=(
                    "the retención-soportada record operation takes a payer certificate's bytes for origin "
                    "payer_certificate and has no field for cotizaciones_seguridad_social; the persona "
                    "references no certificate document"
                ),
            )
        )
    uncarried = [row for row in persona.ledger if row.iva_amount is not None and not _carries_iva_amount(row)]
    if uncarried:
        found.append(
            NotLoaded(
                block="ledger.iva_amount",
                reason=(
                    "single classification takes no recargo amount, does not reconstitute a self-assessed "
                    "intra-community service cuota and accepts a payment net of retención only under an expense "
                    "category the registry relates to withheld activity income, so these rows are classified "
                    f"without their cuota: {_refs(uncarried)}"
                ),
            )
        )
    anonymous = [row for row in persona.ledger if row.invoice_kind is not None and row.counterparty is None]
    if anonymous:
        found.append(
            NotLoaded(
                block="ledger.invoice",
                reason=(
                    "the invoice operation requires a counterparty name and the persona names none for these "
                    f"invoices to anonymous consumers: {_refs(anonymous)}"
                ),
            )
        )
    return tuple(found)


def materialise_persona(persona: Persona, world: PersonaWorld) -> MaterialisedPersona:
    """Replay ``persona`` into ``world``'s profile through production operations."""
    with frozen_clock(world.as_of):
        _replay_profile(persona, world)
        transactions = _imported_transactions(persona, world)
        invoices = _replay_ledger(persona, world, transactions)
        evidence = _replay_documents(persona, world, transactions)
    return MaterialisedPersona(
        persona=persona,
        world=world,
        transactions=transactions,
        invoices=invoices,
        evidence=evidence,
        not_loaded=_not_loaded(persona),
    )


@contextmanager
def materialised_persona(persona_id: str, tmp_path: Path) -> Generator[MaterialisedPersona]:
    """Read one persona, open its world at its scenario instant and replay it there."""
    with bundled_indexed_authority().operation() as operation:
        envelope = year_envelope(operation)
    persona = read_persona(persona_id, envelope=envelope)
    with persona_world(tmp_path, as_of=scenario_instant(persona, envelope)) as world:
        yield materialise_persona(persona, world)


__all__ = [
    "PERSONA_ACTOR",
    "SCENARIO_TIME",
    "MaterialisedPersona",
    "NotLoaded",
    "PersonaMaterialisationError",
    "PersonaWorld",
    "household_leaves",
    "load_profile_record",
    "materialise_persona",
    "materialised_persona",
    "patch_answers",
    "persona_world",
    "run_operation",
    "scenario_instant",
    "settle_operation",
    "submitted_answer",
    "year_envelope",
]
