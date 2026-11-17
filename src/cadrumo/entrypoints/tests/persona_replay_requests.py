"""Build the typed requests a persona replay submits from the persona's own records."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Final

from ...application.invoices.catalogue_add_contracts import InvoiceAddRequest
from ...application.ledger.actions_common import display_decimal
from ...application.ledger.classify_requests import LedgerClassifyPatch, LedgerClassifyPatchField
from ...application.ledger.counterparty_filing_name_rendering import CounterpartyFilingNameRendering
from ...application.ledger.counterparty_operation import (
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ...application.operations.public_scalar import PublicDecimal
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.wizard.imputation_election import YEAR_QUESTION_ID
from ...domain.iva.schema import InvoiceKind
from ...domain.user_profile.values import UserProfileRecord, compose_legal_full_name
from ...tests.persona_types import (
    HouseholdMember,
    IdentityRef,
    LedgerRow,
    Persona,
    PersonaDate,
    ProfileValue,
    YearEnvelope,
)
from .persona_operations import run_operation
from .persona_world import PERSONA_ACTOR, PersonaMaterialisationError, PersonaWorld

_STATEMENT_HEADER = "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda;Referencia"


def load_profile_record(world: PersonaWorld) -> UserProfileRecord:
    """Read the profile's current record, which every profile mutation names as its baseline."""
    return ProfileRecordRepository.for_current_session(
        world.profile_id, profile_decode_context=world.operation.profile_decode_context()
    ).load(world.profile_id)


def submitted_answer(persona: Persona, value: ProfileValue, envelope: YearEnvelope) -> str:
    """Render one ``[profile]`` value as the profile patch takes it, as the catalogue README states."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):
        return ",".join(value)
    if isinstance(value, IdentityRef):
        return identity_text(persona, value)
    return value.resolve(envelope).isoformat()


def identity_text(persona: Persona, reference: IdentityRef) -> str:
    """One identity field as an operation takes it; ``full_name`` is the official surnames-first name or razón social."""
    if reference.field != "full_name":
        return persona.identity(reference)
    holder = persona.identities.role(reference.role)
    if holder.legal_name is not None:
        return holder.legal_name
    if holder.surnames is None or holder.name is None:
        raise PersonaMaterialisationError(f"identity {reference.role} carries no name to compose")
    return compose_legal_full_name(surnames=holder.surnames, name=holder.name)


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
    """One household row as the operations take it: its identity's NIF and its surnames-first name."""
    leaves = [
        (key, value.resolve(envelope).isoformat() if isinstance(value, PersonaDate) else value)
        for key, value in member.leaves
    ]
    if member.identity is not None:
        person = persona.identities.role(member.identity)
        leaves.append(("nif", person.value))
        if person.name is not None and person.surnames is not None:
            leaves.append(("apellidos_nombre", compose_legal_full_name(surnames=person.surnames, name=person.name)))
    return tuple(leaves)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def bank_statement(rows: Sequence[LedgerRow], envelope: YearEnvelope) -> str:
    """Bank movements in the statement columns ``app ledger import --file`` reads."""
    lines = [_STATEMENT_HEADER]
    balance = Decimal("0.00")
    for row in sorted(rows, key=lambda item: item.operation_date(envelope)):
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


def classify_patch(
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
        ("iva_amount", row.iva_amount),
        ("recargo_amount", row.recargo_amount),
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


def party_name(persona: Persona, role: str) -> str:
    counterparty = persona.identities.role(role)
    return counterparty.razon_social or f"{counterparty.field('nombre')} {counterparty.field('surnames')}"


INFORMATIVE_MODELOS: Final = frozenset({"347", "349", "180", "190", "193"})
"""The informative returns whose design names a third party by its filing name."""


def informative_party_roles(persona: Persona) -> tuple[str, ...]:
    """The roles of the third parties the persona's informative returns name, in first-named order.

    A persona that files none of :data:`INFORMATIVE_MODELOS` names no party. Otherwise the counterparty
    of every ledger row is a declarado, operador or perceptor, and the landlord of leased premises is
    the perceptor of the Modelo 180. The payer of a withholding certificate is the taxpayer's source
    of income on the Modelo 100, not a party an informative return names.
    """
    if INFORMATIVE_MODELOS.isdisjoint(persona.modelos):
        return ()
    payers = {certificate.payer for certificate in persona.withholding_certificates}
    roles: dict[str, None] = {}
    for row in persona.ledger:
        if row.counterparty is not None and row.counterparty not in payers:
            roles[row.counterparty] = None
    for premises in persona.leased_premises:
        roles[premises.landlord] = None
    return tuple(roles)


def _filing_name_request(persona: Persona, role: str, world: PersonaWorld) -> LedgerCounterpartyRequest:
    """The statement of one party's filing name, in the identity's own words and order."""
    party = persona.identities.role(role)
    stated: dict[str, object]
    if party.is_entity:
        stated = {"party_kind": "entity", "razon_social": party.razon_social}
    else:
        stated = {
            "party_kind": "natural_person",
            "primer_apellido": party.primer_apellido,
            "segundo_apellido": party.segundo_apellido,
            "no_second_surname": party.no_second_surname,
            "nombre": party.nombre,
        }
    return LedgerCounterpartyRequest.model_validate(
        {
            "profile_id": world.profile_id,
            "action": "filing_name",
            "tax_identifier": party.value,
            "country_code": party.country,
            "asserted_by": PERSONA_ACTOR,
            "renderings": tuple(
                CounterpartyFilingNameRendering(width=width, text=text) for width, text in party.renderings
            ),
            **stated,
        }
    )


def _state_filing_names(persona: Persona, world: PersonaWorld) -> None:
    """State each informative-return party's filing name through the registered counterparty operation."""
    for role in informative_party_roles(persona):
        result = run_operation(
            world,
            LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
            _filing_name_request(persona, role, world),
            LedgerCounterpartyResult,
        )
        if result.filing_name is None or result.recorded is not True:
            raise PersonaMaterialisationError(f"{persona.id} {role}: the filing name was not recorded")


def _invoice_request(persona: Persona, row: LedgerRow, world: PersonaWorld) -> InvoiceAddRequest | None:
    """The invoice behind a row as ``ledger invoice add`` records it; ``None`` for a row no invoice backs."""
    if row.invoice_kind is None or row.invoice_number is None:
        return None
    if row.counterparty is None:
        raise PersonaMaterialisationError(f"{persona.id} {row.ref}: an invoice names its counterparty")
    counterparty = persona.identities.role(row.counterparty)
    name = party_name(persona, row.counterparty)
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


__all__ = [
    "household_leaves",
    "load_profile_record",
    "patch_answers",
    "submitted_answer",
]
