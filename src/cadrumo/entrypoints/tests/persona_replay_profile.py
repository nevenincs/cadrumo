"""Replay a persona's profile, household, withholding, ledger, documents and inventory through operations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from functools import partial
from pathlib import Path

from ...application.inventory.registered_evidence_operation import (
    INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    InventoryEvidenceAddProjection,
    InventoryEvidenceAddRequest,
)
from ...application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
)
from ...application.inventory.registered_requests import (
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    InventoryClosingValueFactsInput,
    InventoryClosingValueRecordRequest,
    InventoryCreateRequest,
)
from ...application.invoices.catalogue_add_contracts import INVOICE_ADD_OPERATION_DEFINITION_ID, InvoiceAddResult
from ...application.ledger.actions_import import LedgerProviderID
from ...application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LedgerAttachRequest,
)
from ...application.ledger.classify_requests import LEDGER_CLASSIFY_OPERATION_DEFINITION_ID, LedgerClassifyRequest
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
from ...application.ledger.update_contracts import (
    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
    LedgerUpdatePatch,
    LedgerUpdateRequest,
)
from ...application.operations.public_scalar import PublicDecimal
from ...application.retencion_soportada_certificado.contracts import RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID
from ...application.retencion_soportada_certificado.requests import RetencionSoportadaRecordRequest
from ...application.retencion_soportada_certificado.results import RetencionSoportadaMutationProjection
from ...application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow
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
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    PriorClosingContinuityEvidence,
)
from ...domain.filing_evidence import FilingEvidenceReference
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen
from ...tests.persona_invoices import render_facturae
from ...tests.persona_types import InventoryBook, Persona, PersonaDocument, WithholdingCertificate, YearEnvelope
from ..ledger_action_composition import compose_ledger_action_ports
from .persona_inventory_purchases import replay_inventory_purchases
from .persona_operations import run_operation, settle_operation
from .persona_replay_requests import (
    _decimal_text,
    _invoice_request,
    bank_statement,
    classify_patch,
    household_leaves,
    load_profile_record,
    party_name,
    patch_answers,
    submitted_answer,
)
from .persona_world import PERSONA_ACTOR, PersonaMaterialisationError, PersonaWorld


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
    for row in persona.profile_rows:
        record = load_profile_record(world)
        settle_operation(
            world,
            PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
            ProfileRepeatableRowMutationOperationRequest(
                profile_id=world.profile_id,
                expected_revision=record.record_revision,
                expected_content_digest=record.content_digest,
                section_key=row.section,
                values=tuple(
                    ProfileRepeatableRowValue(field_key=key, value=submitted_answer(persona, value, envelope))
                    for key, value in row.values
                ),
            ),
        )


def _replay_household(persona: Persona, world: PersonaWorld) -> None:
    """Replace each household family the persona states; a family it states as empty declares it has none."""
    envelope = world.envelope
    if "descendants" in persona.household_families:
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
    if "ascendants" in persona.household_families:
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


def declared_withholding(persona: Persona) -> list[WithholdingCertificate]:
    """The certificates the record operation takes: those the taxpayer declares, which need no certificate bytes."""
    return [item for item in persona.withholding_certificates if item.origin == "operator_declaration"]


def _stated_figure(figure: Decimal | None) -> PublicDecimal | None:
    return None if figure is None else PublicDecimal(decimal=str(figure))


def _replay_withholding(persona: Persona, world: PersonaWorld) -> None:
    zero = PublicDecimal(decimal="0.00")
    for certificate in declared_withholding(persona):
        payer = persona.identities.role(certificate.payer)
        recorded = run_operation(
            world,
            RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
            RetencionSoportadaRecordRequest(
                profile_id=world.profile_id,
                ejercicio=certificate.ejercicio.resolve(world.envelope),
                income_class=RetencionSoportadaClase(certificate.income_class),
                payer_tax_id=payer.value,
                payer_legal_name=party_name(persona, certificate.payer),
                importe_integro_dinerario=PublicDecimal(decimal=str(certificate.importe_integro)),
                valoracion_especie=zero,
                retencion=PublicDecimal(decimal=str(certificate.retencion)),
                ingreso_a_cuenta=zero,
                ingreso_a_cuenta_repercutido=zero,
                reducciones_aplicables=_stated_figure(certificate.reducciones_aplicables),
                gastos_deducibles=_stated_figure(certificate.gastos_deducibles),
                origin=RetencionSoportadaOrigen.OPERATOR_DECLARATION,
            ),
            RetencionSoportadaMutationProjection,
        )
        if recorded.outcome != "recorded":
            raise PersonaMaterialisationError(f"{persona.id} {certificate.payer}: {recorded.refusal}")


def _imported_transactions(persona: Persona, world: PersonaWorld) -> dict[str, str]:
    """Import the statement and map each ledger ref to the transaction it became."""
    rows = persona.ledger
    statement = world.workdir / f"{persona.id}-statement.csv"
    statement.write_text(bank_statement(rows, world.envelope), encoding="utf-8", newline="\n")
    result = run_operation(
        world,
        LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        LedgerImportRequest(profile_id=world.profile_id, files=(statement,), provider=LedgerProviderID.CSV),
        LedgerImportResultProjection,
    )
    if result.imported != len(rows) or result.refused_files:
        raise PersonaMaterialisationError(
            f"{persona.id}: imported {result.imported} of {len(rows)} rows, refused {result.refused_files}"
        )
    stored = compose_ledger_action_ports(
        bucket_id=str(world.profile_id), operation=world.operation
    ).transaction_repository.load()
    refs = {row.ref for row in rows}
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
        patch, fields = classify_patch(persona, row)
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
        if (accrued_on := row.accrual_date(world.envelope)) is not None:
            settle_operation(
                world,
                LEDGER_UPDATE_OPERATION_DEFINITION_ID,
                LedgerUpdateRequest(
                    profile_id=world.profile_id,
                    transaction_id=transactions[row.ref],
                    patch=LedgerUpdatePatch(accrual_date=accrued_on.isoformat()),
                    patch_fields=("accrual_date",),
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


def document_path(persona: Persona, document: PersonaDocument, *, envelope: YearEnvelope, workdir: Path) -> Path:
    """The file evidence intake reads: the specimen itself, or the generated invoice written to the workdir."""
    if document.path is not None:
        return document.path
    generated = render_facturae(persona, document, envelope)
    target = workdir / "documents" / generated.file_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generated.text, encoding="utf-8", newline="\n")
    return target


def _replay_documents(persona: Persona, world: PersonaWorld, transactions: Mapping[str, str]) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for document in persona.documents:
        source = document_path(persona, document, envelope=world.envelope, workdir=world.workdir)
        added = run_operation(
            world,
            LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
            LedgerEvidenceAddRequest(
                profile_id=world.profile_id,
                source_path=str(source),
                source_directory=str(source.parent),
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


def inventory_statement(persona: Persona, book: InventoryBook, *, envelope: YearEnvelope, workdir: Path) -> Path:
    """The taxpayer's statement behind one inventory book, written to the workdir as the PDF evidence intake keeps."""
    year = book.year.resolve(envelope)
    target = workdir / "inventory" / f"{persona.id}-{book.activity}-{year}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(f"%PDF-1.4\n% {book.statement} ({year})\n%%EOF\n".encode())
    return target


def _replay_inventory(persona: Persona, world: PersonaWorld, transactions: Mapping[str, str]) -> None:
    """Open each inventory book, add its purchases, and record its closing on its movements, evidenced by the statement.

    Each purchase claims the ledger row that books it, and rests on the invoice
    attached to that row. The statement also evidences the prior year's closing
    the opening continues from, since no earlier book holds one.
    """
    for book in persona.inventory:
        year = book.year.resolve(world.envelope)
        where = f"{persona.id} inventory {book.activity} {year}"
        created = run_operation(
            world,
            INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            InventoryCreateRequest(
                profile_id=world.profile_id,
                actividad_id=book.activity,
                year=year,
                valuation_method=book.valuation_method,
                opening_stock=PublicDecimal(decimal=_decimal_text(book.opening_stock)),
            ),
            InventoryCreateProjection,
        )
        if created.outcome != "created":
            raise PersonaMaterialisationError(f"{where}: create refused: {created.model_dump_json()}")
        replay_inventory_purchases(
            persona,
            book,
            year=year,
            profile_id=world.profile_id,
            workdir=world.workdir,
            transactions=transactions,
            invoice_source=lambda ref: document_path(
                persona,
                next(document for document in persona.documents if ref in document.attach_to),
                envelope=world.envelope,
                workdir=world.workdir,
            ),
            settle=partial(settle_operation, world),
        )
        source = inventory_statement(persona, book, envelope=world.envelope, workdir=world.workdir)
        stored = run_operation(
            world,
            INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
            InventoryEvidenceAddRequest(
                profile_id=world.profile_id, source_path=str(source), source_directory=str(source.parent)
            ),
            InventoryEvidenceAddProjection,
        )
        if stored.reference is None or stored.content_digest is None:
            raise PersonaMaterialisationError(f"{where}: statement refused: {stored.model_dump_json()}")
        reference = FilingEvidenceReference(reference=stored.reference)
        recorded = run_operation(
            world,
            INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
            InventoryClosingValueRecordRequest(
                profile_id=world.profile_id,
                actividad_id=book.activity,
                year=year,
                facts=InventoryClosingValueFactsInput(
                    decision_id=f"persona-{book.activity}-{year}",
                    authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
                    reason=book.statement,
                    decision_evidence=(
                        InventoryClosingDecisionEvidence(
                            reference=reference,
                            role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                            content_digest=stored.content_digest,
                        ),
                    ),
                    prior_evidence=(
                        PriorClosingContinuityEvidence(reference=reference, content_digest=stored.content_digest),
                    ),
                ),
            ),
            InventoryClosingAuthorityOperationProjection,
        )
        if recorded.outcome != "recorded":
            raise PersonaMaterialisationError(f"{where}: closing refused: {recorded.model_dump_json()}")
