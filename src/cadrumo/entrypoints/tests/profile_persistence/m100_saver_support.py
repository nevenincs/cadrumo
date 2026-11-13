"""Savers for the Modelo 100 detail-record proof: positions, linked ledger rows, carries and the written records.

A saver holds positions in the profile's ``inversiones_posicion`` section, ledger
rows linked to them under a capital-mobiliario concept, and one payer certificate
per paying entity. This module stores those inputs and reads the exported detail
records back through the registry's XML layout; it computes no tax amount. The
expected figures live in the tests that assert them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from defusedxml import ElementTree

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.filing.export_xml_dictionary_xsd import (
    xml_dictionary_repeating_element_paths,
    xml_dictionary_xsd_source,
)
from cadrumo.application.filing.export_xml_input_dictionary import declared_and_admitted_dictionary_entries
from cadrumo.application.filing.export_xml_row_columns import nearest_repeating_element_path
from cadrumo.application.filing.runtime import build_runtime_schema_provider
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from cadrumo.domain.calculations.registry.capital_mobiliario_position_bindings import (
    capital_mobiliario_position_bindings,
)
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.contribuyente.inmueble_facts import facts_for_row
from cadrumo.domain.contribuyente.posicion_facts import POSICION_SECTION
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.tests.savings_link_rows import savings_row
from cadrumo.domain.user_profile.values import UserProfileFact

from .m130_m100_annual_support import BUCKET_ID, M100_ANNUAL_PERIOD, YEAR

__all__ = [
    "SAVINGS_CARRY_FAMILIES",
    "LinkedRow",
    "SavingsPosition",
    "detail_records",
    "position_facts",
    "savings_carries_stated_zero",
    "seed_linked_rows",
]

#: The two savings carry families a Modelo 100 reads from the four previous ejercicios (LIRPF art. 49.1).
SAVINGS_CARRY_FAMILIES = frozenset(
    {
        AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_CAPITAL_INCOME_PENDING,
        AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_GAINS_LOSSES_PENDING,
    }
)

_CLASSIFIED_AT = datetime(YEAR + 1, 1, 20, 9, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SavingsPosition:
    """One row of ``inversiones_posicion``: kind, payer, source state, share and holding interval."""

    tipo: str
    payer: str
    payer_name: str
    share: str
    since: date
    until: date | None = None
    country: str = "ES"


@dataclass(frozen=True, slots=True)
class LinkedRow:
    """One ledger movement linked to a position: the net cash credited, or a fee paid, on its date."""

    row_id: str
    position: str
    concept: str
    amount: str
    on: date
    direction: TransactionDirection = TransactionDirection.INCOMING


def position_facts(positions: dict[str, SavingsPosition]) -> tuple[UserProfileFact, ...]:
    """The profile facts of each position, keyed by its row in the section."""
    facts: list[UserProfileFact] = []
    for clave, position in positions.items():
        values = {
            "tipo": position.tipo,
            "pagador_nif": position.payer,
            "pagador_nombre": position.payer_name,
            "pais_origen": position.country,
            "porcentaje_titularidad": position.share,
            "fecha_inicio": position.since.isoformat(),
        }
        if position.until is not None:
            values["fecha_fin"] = position.until.isoformat()
        facts.extend(
            UserProfileFact(path=path, value=value)
            for path, value in facts_for_row(POSICION_SECTION, int(clave), values).items()
        )
    return tuple(facts)


def _transaction(row: LinkedRow) -> Transaction:
    base = savings_row(provider_id=row.row_id)
    return savings_row(
        provider_id=row.row_id,
        raw=base.raw.model_copy(update={"amount": Decimal(row.amount), "booked_date": row.on}),
        direction=row.direction,
        posicion_ref=row.position,
        concepto_capital_mobiliario=row.concept,
        business_classification=BusinessClassification.PERSONAL,
        classified_at=_CLASSIFIED_AT,
        classified_by="manual",
    )


def seed_linked_rows(objects: SecureObjectRepository, rows: tuple[LinkedRow, ...]) -> None:
    """Persist the saver's linked ledger rows as the bucket's transaction catalogue."""
    TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects).save(
        TransactionCatalogue.from_transactions(tuple(_transaction(row) for row in rows))
    )


def savings_carries_stated_zero(operation: PinnedAuthorityOperation) -> dict[BindingId, Decimal]:
    """The taxpayer's statement, from her copy of the previous return, that no negative savings balance is pending.

    Every binding of the two savings carry families of the ejercicio's edition is
    stated as 0.00: nothing of capital mobiliario nor of gains and losses was left
    to offset by the four previous ejercicios.
    """
    revision = operation.snapshot("100", filing_year=YEAR, period=M100_ANNUAL_PERIOD).revision
    return {
        binding.id: Decimal("0.00")
        for binding in revision.bindings
        if binding.absence_attestation in SAVINGS_CARRY_FAMILIES
    }


def detail_records(operation: PinnedAuthorityOperation, payload: bytes) -> dict[str, list[dict[str, str]]]:
    """Read each written occurrence of every detail record the savings row columns fill, by quantity.

    The record, its fields and its repeating element come from the edition's input
    dictionary and XSD through the registry, never from a path spelled here.
    """
    provider = build_runtime_schema_provider(
        filing_year=YEAR,
        period=Period.from_year_and_code(YEAR, M100_ANNUAL_PERIOD),
        modelos=("100",),
        operation=operation,
    )
    revision = provider.get_snapshot("100").revision
    layout = revision.export_layouts[0]
    _declared, admitted = declared_and_admitted_dictionary_entries(
        layout,
        bindings=revision.bindings,
        casillas=revision.casillas,
        sources=provider.sources,
        source_payloads=provider.source_payloads,
    )
    repeating = xml_dictionary_repeating_element_paths(
        xml_dictionary_xsd_source(layout, provider.sources), source_payloads=provider.source_payloads
    )
    paths = {entry.field_id: entry.path for entry in admitted}
    document = ElementTree.fromstring(payload)
    written: dict[str, list[dict[str, str]]] = {}
    for _binding, selector in capital_mobiliario_position_bindings(revision):
        if selector.dictionary_field is None or selector.detail_record is None:
            continue
        path = paths[selector.dictionary_field]
        element = nearest_repeating_element_path(path, repeating)
        if element is None:
            raise AssertionError(f"{selector.dictionary_field} has no repeating element in the design")
        occurrences = written.setdefault(selector.detail_record, [])
        for index, node in enumerate(document.findall(element.strip("/"))):
            if index == len(occurrences):
                occurrences.append({})
            text = node.findtext(path.removeprefix(f"{element}/"))
            if text is not None:
                occurrences[index][selector.quantity.value] = text
    return written
