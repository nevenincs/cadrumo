"""Give each invoice party the filing name the person declared for it, and report the slots it cannot fill.

A record naming a party (a Modelo 347 declarado or arrendatario, a Modelo 349
operador) files the name the person declared for that party, composed by the
slot's design rule. An invoice's printed name is display only. A party with no
declared name, with one the design does not compose, or with one wider than its
slot leaves the slot without content; each such party is named here once, with
an invoice to recognise it by, and the export refuses until the name is stated.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, NamedTuple

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.filing.declared_party_name import DeclaredPartyFilingName
from ...domain.filing.errors import (
    FilingExportDeclaredPartyNameError,
    FilingExportDeclaredPartyNameSingleSurnameError,
    FilingExportDeclaredPartyNameTooWideError,
)
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ..aggregation.source_mesh import CalculationSourceContext, CalculationSourceDiagnostic
from ..ledger.counterparty_establishment import confirmed_counterparty_facts_key
from .source_observations import ObservedInvoice
from .source_resolver_ports import CounterpartyFilingNameReader

#: How many characters of a party's stated-facts key name it in a refusal.
_PARTY_HANDLE_LENGTH: Final = 12

#: The row field a party-name slot fills; the layout record maps it to its casilla.
_PARTY_FILING_NAME_ROW_FIELD: Final = "party_filing_name"

#: The source kind a slot's diagnostic names when its binding's source is unknown.
_INVOICE_SOURCE_KIND: Final = "invoice"

_REMEDY: Final = (
    "State the counterparty's filing name (surnames and given name, or razón social), then calculate again."
)


def with_declared_filing_names(
    observed_items: tuple[ObservedInvoice, ...],
    filing_names: CounterpartyFilingNameReader,
) -> tuple[ObservedInvoice, ...]:
    """Give each observation its party's declared filing name and the handle that names the party.

    Only a stated name is used; a party with none keeps no name.

    Raises:
        InvoiceSourcePersistenceError: The stated facts cannot be read.
    """
    stated: dict[tuple[str, str], tuple[DeclaredPartyFilingName | None, str | None]] = {}
    placed: list[ObservedInvoice] = []
    for invoice, observation in observed_items:
        party = (observation.country_code, str(observation.party_tax_id))
        if party not in stated:
            key = confirmed_counterparty_facts_key(party[1], country_code=party[0])
            name = None if key is None else filing_names.filing_name_of(party[1], country_code=party[0])
            stated[party] = (name, None if key is None else key[:_PARTY_HANDLE_LENGTH])
        name, handle = stated[party]
        placed.append(
            (invoice, observation.model_copy(update={"party_filing_name": name, "party_handle": handle})),
        )
    return tuple(placed)


class RefusedParty(NamedTuple):
    """A party a refusal names: how it is shown in the note, and a row to recognise it by."""

    named: str
    rows: tuple[str, ...]


def party_name_refusal_diagnostics(
    refusals: Sequence[FilingExportDeclaredPartyNameError],
    observed_items: Sequence[ObservedInvoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name each party whose filing name a slot could not file, once per party and refusal, with an invoice."""
    earliest = _earliest_invoice_by_party(observed_items)
    return refused_party_diagnostics(
        refusals,
        {handle: RefusedParty(_party_named(item), (item[0].invoice_id,)) for handle, item in earliest.items()},
        context=context,
        resolver_id=resolver_id,
    )


def refused_party_diagnostics(
    refusals: Sequence[FilingExportDeclaredPartyNameError],
    parties: Mapping[str, RefusedParty],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report each refusal once per party handle, reason and field, naming the party from ``parties``."""
    slots = _party_name_slot_sources(context.revision)
    diagnostics: dict[tuple[str, str, str], CalculationSourceDiagnostic] = {}
    for refusal in refusals:
        handle = refusal.party_handle or ""
        key = (handle, refusal.reason, refusal.export_field_id)
        if key not in diagnostics:
            diagnostics[key] = _refusal_diagnostic(
                refusal,
                party=parties.get(handle),
                slot=slots.get(refusal.export_field_id, (None, None)),
                context=context,
                resolver_id=resolver_id,
            )
    return tuple(diagnostics[key] for key in sorted(diagnostics))


def _earliest_invoice_by_party(observed_items: Sequence[ObservedInvoice]) -> dict[str, ObservedInvoice]:
    earliest: dict[str, ObservedInvoice] = {}
    for invoice, observation in sorted(
        observed_items, key=lambda item: (item[0].issued_at, item[0].invoice_number, item[0].invoice_id)
    ):
        if observation.party_handle is not None:
            earliest.setdefault(observation.party_handle, (invoice, observation))
    return earliest


def _refusal_diagnostic(
    refusal: FilingExportDeclaredPartyNameError,
    *,
    party: RefusedParty | None,
    slot: tuple[BindingSourceKind | None, CasillaId | None],
    context: CalculationSourceContext,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    source, casilla_id = slot
    handle = refusal.party_handle or ""
    named = refusal.export_field_id if party is None else party.named
    return CalculationSourceDiagnostic(
        reason="declared_party_name_unresolved",
        source_kind=_INVOICE_SOURCE_KIND if source is None else source.value,
        binding_source=source,
        resolver_id=resolver_id,
        source_ref=f"party-name:{refusal.reason}:{handle or refusal.export_field_id}",
        casilla_id=casilla_id,
        fact=CalculationNoteFact.of(
            _SENTENCES[type(refusal).reason],
            rows=() if party is None else party.rows,
            party=named,
            width=refusal.field_length,
        ),
        message=_message(refusal, named=named, context=context),
        remedy=_REMEDY,
    )


_SENTENCES: Final = {
    "missing": CalculationNoteSentence.DECLARED_PARTY_NAME_MISSING,
    "single_surname": CalculationNoteSentence.DECLARED_PARTY_NAME_SINGLE_SURNAME,
    "too_wide": CalculationNoteSentence.DECLARED_PARTY_NAME_TOO_WIDE,
}


def _message(refusal: FilingExportDeclaredPartyNameError, *, named: str, context: CalculationSourceContext) -> str:
    lead = f"Modelo {context.modelo} names {named} in a {refusal.field_length}-character name field"
    if isinstance(refusal, FilingExportDeclaredPartyNameTooWideError):
        return (
            f"{lead}, but its declared filing name is wider and no shorter rendering is stated for that width, "
            "so the field is left without content."
        )
    if isinstance(refusal, FilingExportDeclaredPartyNameSingleSurnameError):
        return (
            f"{lead}, but its declared filing name has one surname, which the record design gives no rule for, "
            "so the field is left without content."
        )
    return f"{lead}, but no filing name is declared for it, so the field is left without content."


def _party_named(item: ObservedInvoice) -> str:
    _, observation = item
    party = str(observation.party_tax_id)
    return party if observation.party_legal_name is None else f"{observation.party_legal_name} ({party})"


def _party_name_slot_sources(
    revision: ModeloRevision,
) -> dict[str, tuple[BindingSourceKind | None, CasillaId | None]]:
    """Index each party-name export field by id, with its binding's source and the casilla its record maps."""
    sources: dict[BindingId, BindingSourceKind] = {binding.id: binding.source for binding in revision.bindings}
    slots: dict[str, tuple[BindingSourceKind | None, CasillaId | None]] = {}
    for layout in revision.export_layouts:
        for record in layout.records:
            casilla_id = record.row_field_casilla_ids.get(_PARTY_FILING_NAME_ROW_FIELD)
            for field in record.fields:
                if field.party_name is None or field.binding is None:
                    continue
                slots[str(field.id)] = (sources.get(field.binding), casilla_id)
    return slots


__all__ = ["RefusedParty", "party_name_refusal_diagnostics", "refused_party_diagnostics", "with_declared_filing_names"]
