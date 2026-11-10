"""Place each factura rectificativa on the informativa it corrects.

An invoice stores a correction as a non-negative amount and its class, and names
the invoice it corrects by number. What the correction does to a declaration
depends on where that invoice falls, so it is decided here with the catalogue in
hand, after each invoice has been observed on its own:

- Modelo 349 nets a correction of the same period into the operator record, and
  files a correction of an earlier period as a rectification record of that
  period, from the base declared for it;
- Modelo 347 keeps a correction of an earlier ejercicio in the amount declared
  but out of the comparison with the floor;
:class:`InvoiceCatalogue`, the profile's invoice catalogue.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TypeGuard

from ...core.decimal.constants import ZERO
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.invoice_bindings import InvoiceObservation
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.modelos.row_models import (
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    validate_m349_country_prefix_context,
)
from ..aggregation.source_mesh import CalculationSourceContext, CalculationSourceDiagnostic
from .source_observations import ObservedInvoice, invoice_source_kind, is_rectificativa, rectified_invoices
from .source_resolver_ports import M349FiledDeclaration, M349FiledDeclarationReader

_M349_RECTIFICATION_LEGAL_REFS: tuple[str, ...] = ("rd-1624-1992:art-80", "ley-37-1992:art-80")

type _M349RecordKey = tuple[str, str, str]
"""The country, operator and clave one Modelo 349 record relates."""


def place_rectifications(
    observed_items: tuple[ObservedInvoice, ...],
    *,
    catalogue: InvoiceCatalogue,
    context: CalculationSourceContext,
    filed_declarations: M349FiledDeclarationReader | None,
    resolver_id: str,
) -> tuple[tuple[ObservedInvoice, ...], tuple[CalculationSourceDiagnostic, ...]]:
    """Return the observations with each correction placed, and the refusal of each it could not place.

    ``catalogue`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    if context.modelo == form_for_role("iva.intracommunity_summary"):
        return _place_m349_rectifications(
            observed_items,
            catalogue=catalogue,
            context=context,
            filed_declarations=filed_declarations,
            resolver_id=resolver_id,
        )
    if context.modelo == form_for_role("third_party.annual_operations"):
        return _mark_m347_earlier_year_modifications(observed_items, catalogue=catalogue, context=context), ()
    return observed_items, ()


def _mark_m347_earlier_year_modifications(
    observed_items: tuple[ObservedInvoice, ...],
    *,
    catalogue: InvoiceCatalogue,
    context: CalculationSourceContext,
) -> tuple[ObservedInvoice, ...]:
    """Mark the corrections RD 1065/2007 art. 35.2 consigns in this ejercicio though their operation is earlier.

    A correction whose invoice the catalogue does not hold, or holds more than once
    under that number, cannot be dated, so it stays with the year's operations and
    the netting advisory names it.
    """
    marked: list[ObservedInvoice] = []
    for invoice, observation in observed_items:
        candidates = rectified_invoices(invoice, catalogue) if is_rectificativa(invoice) else ()
        target = candidates[0] if len(candidates) == 1 else None
        earlier = target is not None and target.issued_at.year < context.filing_year
        marked.append(
            (invoice, observation.model_copy(update={"earlier_year_modification": True}) if earlier else observation),
        )
    return tuple(marked)


@dataclass(frozen=True, slots=True)
class _EarlierCorrection:
    invoice: Invoice
    observation: InvoiceObservation
    rectified: Invoice


def _place_m349_rectifications(
    observed_items: tuple[ObservedInvoice, ...],
    *,
    catalogue: InvoiceCatalogue,
    context: CalculationSourceContext,
    filed_declarations: M349FiledDeclarationReader | None,
    resolver_id: str,
) -> tuple[tuple[ObservedInvoice, ...], tuple[CalculationSourceDiagnostic, ...]]:
    """Split the period's corrections by the period of the invoice each corrects.

    Manual IVA 2025 p. 302: "cuando la rectificación se produce en el mismo
    período de declaración, no se tiene que cumplimentar la Hoja de
    Rectificaciones 349, si no que se enviará un único registro en la hoja de
    declarados neteando el importe". A correction of an earlier period goes to
    that hoja, in the declaration of the period it was notified (Modelo 349
    instructions); the invoice records no notification date, so its issue date
    places it, as it places every invoice on this declaration.
    """
    same_period: list[ObservedInvoice] = []
    earlier: list[_EarlierCorrection] = []
    diagnostics: list[CalculationSourceDiagnostic] = []
    for invoice, observation in observed_items:
        if not is_rectificativa(invoice):
            same_period.append((invoice, observation))
            continue
        candidates = rectified_invoices(invoice, catalogue)
        rectified = candidates[0] if len(candidates) == 1 else None
        if len(candidates) > 1:
            diagnostics.append(
                _m349_refusal(
                    invoice,
                    resolver_id=resolver_id,
                    why=(
                        f"corrects invoice {invoice.rectifies_invoice_number!r}, a number more than one invoice in "
                        "your records carries, so the invoice and the period it corrects are unknown"
                    ),
                    remedy="Give the corrected invoice a number no other invoice of that customer carries, then "
                    "calculate again.",
                ),
            )
        elif rectified is None:
            diagnostics.append(
                _m349_refusal(
                    invoice,
                    resolver_id=resolver_id,
                    why=(
                        f"corrects invoice {invoice.rectifies_invoice_number!r}, which is not in your records, so "
                        "the period it corrects is unknown"
                    ),
                    remedy="Add the corrected invoice to your records, then calculate again.",
                ),
            )
        elif context.period.contains(rectified.issued_at):
            same_period.append((invoice, _reducing(observation)))
        elif rectified.issued_at > context.period.end_date:
            diagnostics.append(
                _m349_refusal(
                    invoice,
                    resolver_id=resolver_id,
                    why=f"corrects invoice {rectified.invoice_number!r}, which is dated after it",
                    remedy="Check the dates of both invoices, then calculate again.",
                ),
            )
        else:
            earlier.append(_EarlierCorrection(invoice, observation, rectified))
    netted, netted_refusals = _net_same_period_records(same_period, resolver_id=resolver_id)
    rectifications, rectification_refusals = _m349_rectification_observations(
        earlier,
        declarations=() if not earlier or filed_declarations is None else filed_declarations.load(),
        context=context,
        resolver_id=resolver_id,
    )
    return (*netted, *rectifications), (*diagnostics, *netted_refusals, *rectification_refusals)


def _reducing(observation: InvoiceObservation) -> InvoiceObservation:
    total = observation.invoice_total_amount
    return observation.model_copy(
        update={
            "base_amount": -observation.base_amount,
            "invoice_total_amount": None if total is None else -total,
        },
    )


def _record_key(observation: InvoiceObservation) -> _M349RecordKey:
    return (observation.country_code, observation.party_tax_id, observation.intracommunity_clave or "")


def _net_same_period_records(
    items: Sequence[ObservedInvoice],
    *,
    resolver_id: str,
) -> tuple[list[ObservedInvoice], list[CalculationSourceDiagnostic]]:
    """Drop a record its corrections cancel, and refuse the corrections of one they would take below zero.

    The operator record's base carries no sign, so a negative one has no place in
    it, and a base of nothing is an operation with nothing left to declare.
    """
    totals: dict[_M349RecordKey, Decimal] = {}
    for _invoice, observation in items:
        key = _record_key(observation)
        totals[key] = totals.get(key, ZERO) + observation.base_amount
    kept: list[ObservedInvoice] = []
    refusals: list[CalculationSourceDiagnostic] = []
    for invoice, observation in items:
        total = totals[_record_key(observation)]
        if total > ZERO:
            kept.append((invoice, observation))
        elif total < ZERO and is_rectificativa(invoice):
            refusals.append(
                _m349_refusal(
                    invoice,
                    resolver_id=resolver_id,
                    why="takes its operator's base for this period below zero",
                    remedy="Check the amount of the correction and of the invoice it corrects, then calculate again.",
                ),
            )
        elif total < ZERO:
            kept.append((invoice, observation))
    return kept, refusals


def _group_by_filed_record(
    corrections: Sequence[_EarlierCorrection],
    *,
    declarations: tuple[M349FiledDeclaration, ...],
    resolver_id: str,
) -> tuple[
    dict[tuple[_M349RecordKey, M349FiledDeclaration], list[_EarlierCorrection]],
    list[CalculationSourceDiagnostic],
]:
    """Group each correction under its record and the filed declaration of its period, refusing the unfiled."""
    groups: dict[tuple[_M349RecordKey, M349FiledDeclaration], list[_EarlierCorrection]] = {}
    refusals: list[CalculationSourceDiagnostic] = []
    for correction in corrections:
        filed = next((item for item in declarations if item.period.contains(correction.rectified.issued_at)), None)
        if filed is None:
            refusals.append(_not_filed_refusal(correction, resolver_id=resolver_id))
            continue
        groups.setdefault((_record_key(correction.observation), filed), []).append(correction)
    return groups, refusals


def _m349_rectification_observations(
    corrections: Sequence[_EarlierCorrection],
    *,
    declarations: tuple[M349FiledDeclaration, ...],
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[list[ObservedInvoice], list[CalculationSourceDiagnostic]]:
    """Fill one rectification record per operator, clave and corrected period.

    Manual IVA 2025 p. 300: "En el campo 'Base imponible rectificada' se
    consignará el nuevo importe total de la Base Imponible", and in "Base
    imponible declarada anteriormente" "el importe que se declaró en la
    declaración que se corrige". The row builder sums a record's observations, so
    the first of a record carries its base and the declared base, and each later
    one only moves the base.
    """
    groups, refusals = _group_by_filed_record(corrections, declarations=declarations, resolver_id=resolver_id)
    placed: list[ObservedInvoice] = []
    for (key, filed), members in groups.items():
        previous = _declared_base(key, filed=filed, declarations=declarations, context=context)
        if previous is None:
            refusals.extend(_not_filed_refusal(member, resolver_id=resolver_id) for member in members)
            continue
        corrected = previous - sum((member.observation.base_amount for member in members), ZERO)
        if corrected < ZERO:
            refusals.extend(
                _m349_refusal(
                    member.invoice,
                    resolver_id=resolver_id,
                    why=(
                        f"corrects more than the {previous} EUR declared for that operator "
                        f"in {filed.period.registry_token}"
                    ),
                    remedy="Check the amount of the correction, then calculate again.",
                )
                for member in members
            )
            continue
        placed.extend(
            _rectification_items(members, previous=previous, corrected=corrected, filed=filed, context=context)
        )
    return placed, refusals


def _rectification_items(
    members: Sequence[_EarlierCorrection],
    *,
    previous: Decimal,
    corrected: Decimal,
    filed: M349FiledDeclaration,
    context: CalculationSourceContext,
) -> Iterable[ObservedInvoice]:
    ordered = sorted(members, key=lambda member: (member.invoice.issued_at, member.invoice.invoice_number))
    for index, member in enumerate(ordered):
        observation = member.observation
        validate_m349_country_prefix_context(
            country_code=observation.country_code,
            clave_operacion=observation.intracommunity_clave or "",
            filing_year=context.filing_year,
            period=context.period.registry_token,
            is_rectification=True,
            rectified_year=filed.period.filing_year,
            rectified_period=filed.period.registry_token,
        )
        yield (
            member.invoice,
            observation.model_copy(
                update={
                    "is_rectification": True,
                    "rectified_year": filed.period.filing_year,
                    "rectified_period": filed.period.registry_token,
                    "rectified_base_previous": previous if index == 0 else ZERO,
                    "base_amount": (
                        corrected + sum((other.observation.base_amount for other in ordered[1:]), ZERO)
                        if index == 0
                        else -observation.base_amount
                    ),
                },
            ),
        )


def _is_operator_row(row: object, *, nif: str, clave: str) -> TypeGuard[Modelo349OperadorRow]:
    """Whether ``row`` declares the operator and clave."""
    return isinstance(row, Modelo349OperadorRow) and row.nif_comunitario == nif and row.clave_operacion == clave


def _declared_base(
    key: _M349RecordKey,
    *,
    filed: M349FiledDeclaration,
    declarations: tuple[M349FiledDeclaration, ...],
    context: CalculationSourceContext,
) -> Decimal | None:
    """Return the base the operator stands at for ``filed``'s period, or ``None`` when no record declares it.

    A record rectified by a later filed declaration stands at its rectified base.
    Only declarations before this one count, so recalculating a period already
    filed does not start from its own earlier result.
    """
    country, party, clave = key
    nif = _m349_prefixed_nif(party, country)
    operator_rows = [row for row in filed.rows if _is_operator_row(row, nif=nif, clave=clave)]
    if not operator_rows:
        return None
    base = sum((row.importe for row in operator_rows), ZERO)
    earlier = (item for item in declarations if item.period.end_date < context.period.end_date)
    for declaration in sorted(earlier, key=lambda item: item.period.end_date):
        for row in declaration.rows:
            if _rectifies_filed_period(row, nif=nif, clave=clave, filed=filed):
                base = row.base_rectificada
    return base


def _rectifies_filed_period(
    row: object,
    *,
    nif: str,
    clave: str,
    filed: M349FiledDeclaration,
) -> TypeGuard[Modelo349RectificacionRow]:
    """Whether ``row`` rectifies the operator and clave for ``filed``'s own period."""
    return (
        isinstance(row, Modelo349RectificacionRow)
        and row.nif_comunitario == nif
        and row.clave_operacion == clave
        and row.ejercicio == str(filed.period.filing_year)
        and row.periodo == filed.period.registry_token
    )


def _m349_prefixed_nif(party_tax_id: str, country_code: str) -> str:
    """The NIF-IVA as a Modelo 349 row holds it, with its country prefix."""
    normalized = party_tax_id.upper()
    return normalized if normalized.startswith(country_code.upper()) else f"{country_code.upper()}{normalized}"


def _not_filed_refusal(correction: _EarlierCorrection, *, resolver_id: str) -> CalculationSourceDiagnostic:
    return _m349_refusal(
        correction.invoice,
        resolver_id=resolver_id,
        why=(
            f"corrects invoice {correction.rectified.invoice_number!r} of an earlier period, and no Modelo 349 "
            "recorded as filed for that period declares its operator and clave, so the base declared before is unknown"
        ),
        remedy=(
            "Calculate and record the Modelo 349 of the corrected period first, then calculate this one again, or "
            "enter the rectification record yourself with the base you declared."
        ),
    )


def _m349_refusal(
    invoice: Invoice,
    *,
    resolver_id: str,
    why: str,
    remedy: str,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="unrouted_declarable_quantity",
        source_kind=invoice_source_kind(invoice),
        resolver_id=resolver_id,
        source_ref=f"invoice:{invoice.invoice_id}",
        message=f"Correction {invoice.invoice_number!r} is NOT declared on this Modelo 349: it {why}.",
        remedy=remedy,
        asserted_legal_refs=_M349_RECTIFICATION_LEGAL_REFS,
    )


__all__ = ["place_rectifications"]
