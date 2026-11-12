"""Income families the annual return holds for the taxpayer and the application does not calculate.

The registry names the families that have no calculator. A taxpayer has such a
family when a ledger row of the ejercicio is classified to it, or when the
profile declares the family's income category for the ejercicio. Either way its
figures reach no casilla, so each family raises one blocking diagnostic instead
of the return reading as if the family did not exist.

The operator clears a family's finding by entering its figures by hand. The
entry is bound to the ledger rows present when it was made: the operator layer
keeps, per family, the digest of the family's rows in the filing window at
entry (:func:`income_family_row_digests`), and the finding stays cleared only
while the rows still digest the same. Rows added, removed or reclassified since
then raise the finding again, saying so, until the figures are entered anew.

A family narrows as its calculators land. A ledger row linked to a savings
position under a concept the position resolver computes is no longer a row of
the capital-mobiliario family, and the profile's declaration of that family
raises nothing while the profile holds a position in the ejercicio: the position
resolver then answers for the family's figures, or blocks them itself.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.capital_mobiliario_facts import resolve_capital_mobiliario_concept_vocabulary
from ...domain.calculations.registry.irpf_income_categories import irpf_income_categories_without_calculator
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.transactions.irpf_categories import normalize_irpf_category
from ...domain.transactions.savings_link import SAVINGS_LINK_IRPF_CATEGORY, has_savings_link
from .capital_mobiliario_position_source import profile_positions
from .retencion_soportada_source import declared_irpf_income_categories
from .source_mesh import CalculationSourceContext, CalculationSourceDiagnostic

if TYPE_CHECKING:
    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.transactions.models import Transaction

__all__ = [
    "income_family_casilla_ids",
    "income_family_entry_digests_after_edit",
    "income_family_not_computed_diagnostics",
    "income_family_row_digests",
]

_SOURCE_KIND: Final = BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
_SOURCE_REF_PREFIX: Final = "income-family:"
_DIGEST_DOMAIN: Final = "income_family_ledger_rows"


def _computed_concepts(*, effective_date: date, authority: GovernedFactSource) -> frozenset[str]:
    vocabulary = resolve_capital_mobiliario_concept_vocabulary(effective_date=effective_date, authority=authority)
    return frozenset(concept.token for concept in vocabulary.concepts)


def _computed_by_position(transaction: Transaction, computed_concepts: frozenset[str]) -> bool:
    """Return whether the position resolver reads the row: linked, under a concept it computes."""
    concept = transaction.concepto_capital_mobiliario
    return (
        has_savings_link(posicion_ref=transaction.posicion_ref)
        and concept is not None
        and str(concept) in computed_concepts
    )


def _family_row_ids(
    window_transactions: Iterable[Transaction], families: Iterable[str], computed_concepts: frozenset[str]
) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {family: [] for family in families}
    for transaction in window_transactions:
        category = normalize_irpf_category(transaction.irpf_category)
        if category in rows and not _computed_by_position(transaction, computed_concepts):
            rows[category].append(str(transaction.transaction_id))
    return rows


def _row_digest(row_ids: Iterable[str]) -> str:
    return content_hash_hex({"domain": _DIGEST_DOMAIN, "row_ids": sorted(row_ids)})


def income_family_row_digests(
    window_transactions: Iterable[Transaction],
    families: Iterable[str],
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> dict[str, str]:
    """Digest, per family, the sorted ids of its ledger rows among the filing window's rows.

    The one digest the operator layer records when the operator enters a
    family's figures and the resolver compares against the rows it reads, so
    the two can never disagree on what "the same rows" means. A family with no
    row digests the empty set. A row the position resolver reads is no row of
    its family; ``effective_date`` selects the concepts it computes.
    """
    computed = _computed_concepts(effective_date=effective_date, authority=authority)
    return {
        family: _row_digest(ids)
        for family, ids in sorted(_family_row_ids(window_transactions, families, computed).items())
    }


def _holds_position_in(context: CalculationSourceContext) -> bool:
    """Return whether the profile holds a savings position on some day of the ejercicio.

    A position whose facts do not cohere answers no, so the declared family keeps
    its finding rather than vanishing on unreadable facts.
    """
    try:
        positions = profile_positions(context)
    except ProfileAnswerTypeError:
        return False
    start, end = context.period.start_date, context.period.end_date
    return any(
        position.fecha_inicio <= end and (position.fecha_fin is None or start <= position.fecha_fin)
        for position in positions
    )


def _declared_families(context: CalculationSourceContext) -> frozenset[str]:
    declared = declared_irpf_income_categories(context) or frozenset[str]()
    if SAVINGS_LINK_IRPF_CATEGORY in declared and _holds_position_in(context):
        return declared - {SAVINGS_LINK_IRPF_CATEGORY}
    return declared


def _diagnostic(
    family: str, *, rows: int, declared: bool, changed: bool, resolver_id: str
) -> CalculationSourceDiagnostic:
    if changed:
        message = (
            f"income family {family!r} has no calculator and its {rows} ledger row(s) of the ejercicio changed after "
            f"its figures were entered by hand; its casillas stay unresolved until they are entered again"
        )
    else:
        message = (
            f"income family {family!r} has no calculator: {rows} ledger row(s) of the ejercicio are classified to it"
            f"{' and the profile declares it' if declared else ''}; its casillas stay unresolved until their figures "
            f"are entered"
        )
    return CalculationSourceDiagnostic(
        reason="income_family_not_computed",
        source_kind=_SOURCE_KIND.value,
        binding_source=_SOURCE_KIND,
        resolver_id=resolver_id,
        source_ref=f"{_SOURCE_REF_PREFIX}{family}",
        message=message,
        fact=(
            CalculationNoteFact.of(CalculationNoteSentence.INCOME_FAMILY_ROWS_CHANGED_SINCE_ENTRY, count=rows)
            if changed
            else None
        ),
    )


def income_family_not_computed_diagnostics(
    context: CalculationSourceContext,
    window_transactions: Iterable[Transaction],
    *,
    authority: GovernedFactSource,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one blocking diagnostic per uncomputed income family the taxpayer has, in token order.

    ``window_transactions`` are the raw ledger rows of the filing period, before
    any aggregation drops rows by direction or classification: a row of an
    uncomputed family is exactly what the aggregation does not keep. A family
    whose figures the operator entered against the rows still present raises
    nothing; one whose rows changed since that entry raises the finding saying so.
    """
    uncomputed = irpf_income_categories_without_calculator(effective_date=context.period.end_date, authority=authority)
    if not uncomputed:
        return ()
    names = sorted(str(token) for token in uncomputed)
    window = tuple(window_transactions)
    end = context.period.end_date
    rows = _family_row_ids(window, names, _computed_concepts(effective_date=end, authority=authority))
    current = income_family_row_digests(window, names, effective_date=end, authority=authority)
    entered = context.income_family_entry_digests
    declared = _declared_families(context)
    return tuple(
        _diagnostic(
            family,
            rows=len(rows[family]),
            declared=family in declared,
            changed=family in entered,
            resolver_id=resolver_id,
        )
        for family in names
        if (rows[family] or family in declared) and entered.get(family) != current[family]
    )


def income_family_casilla_ids(
    revision: ModeloRevision, sections_by_family: Mapping[str, frozenset[str]]
) -> dict[str, frozenset[CasillaId]]:
    """Return, per family, the casillas of ``revision`` whose section path names one of the family's sections."""
    return {
        family: frozenset(casilla.id for casilla in revision.casillas if not sections.isdisjoint(casilla.section))
        for family, sections in sorted(sections_by_family.items())
    }


def income_family_entry_digests_after_edit(
    previous: Mapping[str, str],
    *,
    family_casilla_ids: Mapping[str, frozenset[CasillaId]],
    entered_casilla_ids: frozenset[CasillaId],
    set_casilla_ids: frozenset[CasillaId],
    current_digests: Callable[[frozenset[str]], Mapping[str, str]],
) -> dict[str, str]:
    """Return the per-family entry digests the operator layer keeps after one edit.

    A family the edit sets a casilla of is bound afresh to the rows present now.
    A family that still holds an entered casilla and was not set keeps the digest
    of its earlier entry, so an unrelated edit never re-binds changed rows. A
    family left with no entered casilla drops its digest. ``current_digests`` is
    asked only for the families set, so an edit that sets none reads no ledger.
    """
    held = {family for family, casillas in family_casilla_ids.items() if casillas & entered_casilla_ids}
    refreshed = frozenset(family for family in held if family_casilla_ids[family] & set_casilla_ids)
    fresh: Mapping[str, str] = current_digests(refreshed) if refreshed else dict[str, str]()
    return {
        family: fresh[family] if family in refreshed else previous[family]
        for family in sorted(held)
        if family in refreshed or family in previous
    }
