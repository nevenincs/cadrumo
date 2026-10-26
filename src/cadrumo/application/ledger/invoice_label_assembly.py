"""Resolve collected invoice labels into reconciled draft values."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from .closure_findings import within_rounding_allowance
from .invoice_draft_records import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftRateBreakdown,
)
from .invoice_label_models import (
    HUNDRED,
    InvoiceLabelAssembly,
    InvoiceLabelCollection,
    InvoiceLabelKind,
    InvoiceLabelTier,
    PrintedValue,
)
from .invoice_label_value_parsing import parse_amount

PROVENANCE_NOTE = "read by label rules from the text layer; not yet checked against the document"


TAX_FIGURE_FIELDS = ("taxable_base", "iva_rate", "iva_amount", "recargo_amount", "iva_breakdown")


ARITHMETIC_FINDING_KINDS = frozenset(
    {
        DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
        DraftDiscrepancyKind.RATE_INCONSISTENT,
        DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT,
    },
)


def single_consensus[T](
    name: str, occurrences: Iterable[PrintedValue[T]], assembly: InvoiceLabelAssembly
) -> PrintedValue[T] | None:
    """Return the one value every occurrence agrees on, or record the disagreement."""
    items = list(occurrences)
    distinct: dict[T, PrintedValue[T]] = {}
    for item in items:
        distinct.setdefault(item.value, item)
    if len(distinct) == 1:
        return items[0]
    if len(distinct) > 1:
        assembly.ambiguities[name] = tuple(
            FieldAmbiguityCandidate(value=str(value), anchor=item.anchor, note="another label prints a different value")
            for value, item in distinct.items()
        )
    return None


def _tiers(collected: InvoiceLabelCollection, assembly: InvoiceLabelAssembly) -> list[InvoiceLabelTier]:
    if collected.table_tiers:
        return collected.table_tiers
    by_rate: dict[Decimal, InvoiceLabelTier] = {}
    unrated = InvoiceLabelTier()
    unrated_bases: list[PrintedValue[Decimal]] = []
    unrated_ivas: list[PrintedValue[Decimal]] = []
    _add_rated_amounts(collected, InvoiceLabelKind.BASE, by_rate, unrated_bases)
    _add_rated_amounts(collected, InvoiceLabelKind.IVA, by_rate, unrated_ivas)
    _add_recargo_amounts(collected, by_rate, unrated)
    if len(by_rate) > 1:
        return list(by_rate.values())
    single = next(iter(by_rate.values())) if by_rate else unrated
    _complete_single_tier(single, collected, assembly, unrated_bases, unrated_ivas, unrated)
    return [single]


def _add_rated_amounts(
    collected: InvoiceLabelCollection,
    kind: InvoiceLabelKind,
    by_rate: dict[Decimal, InvoiceLabelTier],
    unrated: list[PrintedValue[Decimal]],
) -> None:
    attribute = "base" if kind is InvoiceLabelKind.BASE else "iva"
    for amount, rate in collected.amounts.get(kind, []):
        if rate is None:
            unrated.append(amount)
            continue
        tier = by_rate.setdefault(rate.value, InvoiceLabelTier(rate=rate))
        if getattr(tier, attribute) is None:
            setattr(tier, attribute, amount)


def _add_recargo_amounts(
    collected: InvoiceLabelCollection,
    by_rate: dict[Decimal, InvoiceLabelTier],
    unrated: InvoiceLabelTier,
) -> None:
    if len(by_rate) > 1:
        return
    target = next(iter(by_rate.values())) if by_rate else unrated
    for amount, rate in collected.amounts.get(InvoiceLabelKind.RECARGO, []):
        target.re_amount = amount
        target.re_rate = rate


def _complete_single_tier(
    tier: InvoiceLabelTier,
    collected: InvoiceLabelCollection,
    assembly: InvoiceLabelAssembly,
    unrated_bases: list[PrintedValue[Decimal]],
    unrated_ivas: list[PrintedValue[Decimal]],
    unrated: InvoiceLabelTier,
) -> None:
    if tier.base is None:
        tier.base = single_consensus("taxable_base", unrated_bases, assembly)
    if tier.iva is None:
        tier.iva = single_consensus("iva_amount", unrated_ivas, assembly)
    if tier.rate is None:
        tier.rate = single_consensus("iva_rate", collected.rates, assembly)
    if tier.re_amount is None and unrated.re_amount is not None:
        tier.re_amount, tier.re_rate = unrated.re_amount, unrated.re_rate


def _tier_reconciles(tier: InvoiceLabelTier, assembly: InvoiceLabelAssembly) -> bool:
    checks = ((tier.base, tier.rate, tier.iva, "iva"), (tier.base, tier.re_rate, tier.re_amount, "recargo"))
    for base, rate, amount, label in checks:
        if base is None or rate is None or amount is None:
            continue
        expected = base.value * rate.value / HUNDRED
        if not within_rounding_allowance(amount.value - expected, term_count=2):
            assembly.findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.RATE_INCONSISTENT,
                    field="iva_rate" if label == "iva" else "recargo_amount",
                    detail=(
                        f"the printed {label} {amount.anchor!r} is not {rate.anchor} of the printed base "
                        f"{base.anchor!r}; the figures were left empty rather than one of them chosen"
                    ),
                    expected=expected,
                    observed=amount.value,
                ),
            )
            return False
    return True


def _printed_total(
    collected: InvoiceLabelCollection,
    total_kind: InvoiceLabelKind,
    tier_kind: InvoiceLabelKind,
    name: str,
    tiers: list[InvoiceLabelTier],
    assembly: InvoiceLabelAssembly,
) -> PrintedValue[Decimal] | None:
    """Return the document's printed total for *name*.

    On a multi-rate document an unrated ``Base imponible`` or ``IVA`` line
    beside the per-rate lines is that total, so it is kept as a cross-check
    rather than dropped.
    """
    totals = [amount for amount, _ in collected.amounts.get(total_kind, [])]
    if len(tiers) > 1 and not collected.table_tiers:
        totals.extend(amount for amount, rate in collected.amounts.get(tier_kind, []) if rate is None)
    return single_consensus(name, totals, assembly)


def assemble_tax_figures(collected: InvoiceLabelCollection, assembly: InvoiceLabelAssembly) -> None:
    """Reconcile printed single-rate or per-rate tax figures into the draft."""
    tiers = [tier for tier in _tiers(collected, assembly) if tier.base or tier.iva or tier.rate]
    if not all(_tier_reconciles(tier, assembly) for tier in tiers):
        return
    printed_base_total = _printed_total(
        collected, InvoiceLabelKind.BASE_TOTAL, InvoiceLabelKind.BASE, "taxable_base", tiers, assembly
    )
    printed_iva_total = _printed_total(
        collected, InvoiceLabelKind.IVA_TOTAL, InvoiceLabelKind.IVA, "iva_amount", tiers, assembly
    )
    if len(tiers) == 1 and len(collected.table_tiers) <= 1:
        _assemble_single_tier(tiers[0], printed_base_total, printed_iva_total, assembly)
        return
    _assemble_multiple_tiers(tiers, printed_base_total, printed_iva_total, assembly)


def _assemble_single_tier(
    tier: InvoiceLabelTier,
    printed_base_total: PrintedValue[Decimal] | None,
    printed_iva_total: PrintedValue[Decimal] | None,
    assembly: InvoiceLabelAssembly,
) -> None:
    base = tier.base or printed_base_total
    if base is None:
        # A cuota or rate with no base has nothing to be checked against.
        return
    assembly.put("taxable_base", base)
    # A printed 0 % charges no rate; the draft's single rate stays empty.
    assembly.put("iva_rate", tier.rate if tier.rate is None or tier.rate.value != 0 else None)
    assembly.put("iva_amount", tier.iva or printed_iva_total)
    assembly.put("recargo_amount", tier.re_amount)


def _assemble_multiple_tiers(
    tiers: list[InvoiceLabelTier],
    printed_base_total: PrintedValue[Decimal] | None,
    printed_iva_total: PrintedValue[Decimal] | None,
    assembly: InvoiceLabelAssembly,
) -> None:
    if not _tiers_have_required_figures(tiers):
        return
    assembly.values["iva_breakdown"] = tuple(_breakdown_row(tier) for tier in tiers)
    assembly.anchors["iva_breakdown"] = _breakdown_anchor(tiers)
    if not _record_breakdown_totals(tiers, printed_base_total, printed_iva_total, assembly):
        assembly.clear(*TAX_FIGURE_FIELDS)


def _tiers_have_required_figures(tiers: list[InvoiceLabelTier]) -> bool:
    if not tiers:
        return False
    return all(tier.base is not None and tier.rate is not None and tier.iva is not None for tier in tiers)


def _breakdown_row(tier: InvoiceLabelTier) -> InvoiceDraftRateBreakdown:
    if tier.base is None or tier.rate is None or tier.iva is None:
        raise ValueError("a multi-rate breakdown requires a base, rate, and IVA amount for every tier")
    return InvoiceDraftRateBreakdown(
        iva_rate=tier.rate.value,
        taxable_base=tier.base.value,
        iva_amount=tier.iva.value,
        recargo_rate=tier.re_rate.value if tier.re_rate else None,
        recargo_amount=tier.re_amount.value if tier.re_amount else None,
    )


def _breakdown_anchor(tiers: list[InvoiceLabelTier]) -> str:
    return " / ".join(
        f"{tier.base.anchor} {tier.rate.anchor} {tier.iva.anchor}"
        for tier in tiers
        if tier.base is not None and tier.rate is not None and tier.iva is not None
    )


def _record_breakdown_totals(
    tiers: list[InvoiceLabelTier],
    printed_base_total: PrintedValue[Decimal] | None,
    printed_iva_total: PrintedValue[Decimal] | None,
    assembly: InvoiceLabelAssembly,
) -> bool:
    recargos: list[PrintedValue[Decimal] | None] = []
    for tier in tiers:
        if tier.re_amount is not None:
            recargos.append(tier.re_amount)
    parts_by_name: tuple[tuple[str, PrintedValue[Decimal] | None, list[PrintedValue[Decimal] | None]], ...] = (
        ("taxable_base", printed_base_total, [tier.base for tier in tiers]),
        ("iva_amount", printed_iva_total, [tier.iva for tier in tiers]),
        ("recargo_amount", None, recargos),
    )
    return all(_record_breakdown_total(name, printed, parts, assembly) for name, printed, parts in parts_by_name)


def _record_breakdown_total(
    name: str,
    printed: PrintedValue[Decimal] | None,
    parts: list[PrintedValue[Decimal] | None],
    assembly: InvoiceLabelAssembly,
) -> bool:
    total = sum((part.value for part in parts if part is not None), Decimal(0))
    if printed is not None:
        if not within_rounding_allowance(printed.value - total, term_count=len(parts)):
            assembly.findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT,
                    field=name,
                    detail=f"the per-rate figures sum to {total} while the document prints {printed.anchor!r}",
                    expected=total,
                    observed=printed.value,
                ),
            )
            return False
        assembly.put(name, printed)
    elif parts:
        assembly.values[name] = total
        assembly.derived[name] = ("iva_breakdown",)
    return True


def assemble_totals(collected: InvoiceLabelCollection, assembly: InvoiceLabelAssembly) -> None:
    """Read and cross-check invoice total, retention, and payable figures."""
    grand_total = single_consensus(
        "grand_total", (a for a, _ in collected.amounts.get(InvoiceLabelKind.GRAND_TOTAL, [])), assembly
    )
    suplidos = single_consensus(
        "suplidos_amount", (a for a, _ in collected.amounts.get(InvoiceLabelKind.SUPLIDOS, [])), assembly
    )
    assembly.put("suplidos_amount", suplidos)
    base = assembly.value("taxable_base")
    grand_total = _check_grand_total(grand_total, base, assembly)
    if base is not None:
        # A total with no base has nothing to be checked against.
        assembly.put("grand_total", grand_total)

    retention_entries = collected.amounts.get(InvoiceLabelKind.RETENCION, [])
    retention = single_consensus("retencion_amount", (a for a, _ in retention_entries), assembly)
    retention = _match_retention_sign(retention, assembly.value("grand_total"))
    retention_rate = single_consensus(
        "retencion_rate",
        (rate for _, rate in retention_entries if rate is not None),
        assembly,
    )
    base = assembly.value("taxable_base")
    retention, retention_rate = _check_retention_rate(retention, retention_rate, base, assembly)
    payable = single_consensus(
        "grand_total", (a for a, _ in collected.amounts.get(InvoiceLabelKind.PAYABLE, [])), assembly
    )
    total = assembly.value("grand_total")
    retention, retention_rate = _check_payable(payable, total, retention, retention_rate, assembly)
    assembly.put("retencion_amount", retention)
    assembly.put("retencion_rate", retention_rate)


def _check_grand_total(
    grand_total: PrintedValue[Decimal] | None,
    base: Decimal | None,
    assembly: InvoiceLabelAssembly,
) -> PrintedValue[Decimal] | None:
    if grand_total is None or base is None:
        return grand_total
    terms = [base, assembly.value("iva_amount"), assembly.value("recargo_amount"), assembly.value("suplidos_amount")]
    stated = [term for term in terms if term is not None]
    computed = sum(stated, Decimal(0))
    if within_rounding_allowance(grand_total.value - computed, term_count=len(stated)):
        return grand_total
    assembly.findings.append(
        DraftDiscrepancyFinding(
            kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
            field="grand_total",
            detail=(
                f"the printed total {grand_total.anchor!r} is not base plus cuota plus recargo plus "
                f"suplidos ({computed}); the figures were left empty rather than one of them chosen"
            ),
            expected=computed,
            observed=grand_total.value,
        ),
    )
    assembly.clear(*TAX_FIGURE_FIELDS, "suplidos_amount")
    return None


def _match_retention_sign(
    retention: PrintedValue[Decimal] | None,
    grand_total: Decimal | None,
) -> PrintedValue[Decimal] | None:
    if retention is None:
        return None
    magnitude = abs(retention.value)
    anchor = retention.anchor.lstrip("-")
    if grand_total is not None and grand_total < 0:
        return PrintedValue(-magnitude, f"-{anchor}")
    return PrintedValue(magnitude, anchor)


def _check_retention_rate(
    retention: PrintedValue[Decimal] | None,
    retention_rate: PrintedValue[Decimal] | None,
    base: Decimal | None,
    assembly: InvoiceLabelAssembly,
) -> tuple[PrintedValue[Decimal] | None, PrintedValue[Decimal] | None]:
    if retention is None or retention_rate is None or base is None:
        return retention, retention_rate
    expected = base * retention_rate.value / HUNDRED
    if within_rounding_allowance(retention.value - expected, term_count=2):
        return retention, retention_rate
    assembly.findings.append(
        DraftDiscrepancyFinding(
            kind=DraftDiscrepancyKind.RATE_INCONSISTENT,
            field="retencion_amount",
            detail=(
                f"the printed retención {retention.anchor!r} is not {retention_rate.anchor} of the "
                f"taxable base ({expected}); both were left empty"
            ),
            expected=expected,
            observed=retention.value,
        ),
    )
    return None, None


def _check_payable(
    payable: PrintedValue[Decimal] | None,
    total: Decimal | None,
    retention: PrintedValue[Decimal] | None,
    retention_rate: PrintedValue[Decimal] | None,
    assembly: InvoiceLabelAssembly,
) -> tuple[PrintedValue[Decimal] | None, PrintedValue[Decimal] | None]:
    if payable is None or total is None:
        return retention, retention_rate
    withheld = retention.value if retention is not None else Decimal(0)
    expected = total - withheld
    if within_rounding_allowance(expected - payable.value, term_count=2):
        return retention, retention_rate
    assembly.findings.append(
        DraftDiscrepancyFinding(
            kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
            field="retencion_amount",
            detail=(
                f"the printed amount payable {payable.anchor!r} is not the total less the retención "
                f"({expected}); the retención was left empty"
            ),
            expected=expected,
            observed=payable.value,
        ),
    )
    return None, None


def record_ambiguous_amounts(collected: InvoiceLabelCollection, assembly: InvoiceLabelAssembly) -> None:
    """Attach competing amount readings where no accepted amount was found."""
    targets = {
        InvoiceLabelKind.BASE: "taxable_base",
        InvoiceLabelKind.BASE_TOTAL: "taxable_base",
        InvoiceLabelKind.IVA: "iva_amount",
        InvoiceLabelKind.IVA_TOTAL: "iva_amount",
        InvoiceLabelKind.GRAND_TOTAL: "grand_total",
        InvoiceLabelKind.RECARGO: "recargo_amount",
        InvoiceLabelKind.RETENCION: "retencion_amount",
        InvoiceLabelKind.SUPLIDOS: "suplidos_amount",
    }
    for kind, printed_forms in collected.ambiguous_amounts.items():
        name = targets.get(kind)
        if name is None or name in assembly.values:
            continue
        printed = printed_forms[0]
        _, readings = parse_amount(printed)
        assembly.ambiguities[name] = tuple(
            FieldAmbiguityCandidate(value=reading, anchor=printed, note="the separator may mark thousands or decimals")
            for reading in readings
        )


def field_provenance(assembly: InvoiceLabelAssembly) -> tuple[FieldProvenance, ...]:
    """Build provenance envelopes for observed, derived, and ambiguous fields."""
    envelopes: list[FieldProvenance] = []
    for name in InvoiceDraft.model_fields:
        if name in assembly.derived and name in assembly.values:
            envelopes.append(
                FieldProvenance(
                    field=name,
                    origin=FieldOrigin.DERIVED,
                    grounding=FieldGroundingOutcome.RECONCILED,
                    derived_from=assembly.derived[name],
                    note="summed from the per-rate figures the document prints",
                ),
            )
        elif name == "iva_breakdown" and name in assembly.values:
            envelopes.append(
                FieldProvenance(
                    field=name,
                    origin=FieldOrigin.TEXT_RULES,
                    grounding=FieldGroundingOutcome.RECONCILED,
                    anchor=assembly.anchors[name],
                    note="every printed tier satisfies base x rate = cuota",
                ),
            )
        elif name in assembly.values:
            envelopes.append(
                FieldProvenance(
                    field=name,
                    origin=FieldOrigin.TEXT_RULES,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                    anchor=assembly.anchors[name],
                    role_evidence=assembly.role_evidence.get(name),
                    note=PROVENANCE_NOTE,
                ),
            )
        elif name in assembly.ambiguities and len(assembly.ambiguities[name]) >= 2:
            envelopes.append(
                FieldProvenance(
                    field=name,
                    origin=FieldOrigin.TEXT_RULES,
                    grounding=FieldGroundingOutcome.AMBIGUOUS,
                    candidates=assembly.ambiguities[name],
                    note="the document prints competing values; none was chosen",
                ),
            )
    return tuple(envelopes)


__all__ = [
    "ARITHMETIC_FINDING_KINDS",
    "assemble_tax_figures",
    "assemble_totals",
    "field_provenance",
    "record_ambiguous_amounts",
    "single_consensus",
]
