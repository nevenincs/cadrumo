"""Income families the annual return holds for the taxpayer and the application does not calculate.

The registry names the families that have no calculator. A taxpayer has such a
family when a ledger row of the ejercicio is classified to it, or when the
profile declares the family's income category for the ejercicio. Either way its
figures reach no casilla, so each family raises one blocking diagnostic instead
of the return reading as if the family did not exist.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.irpf_income_categories import irpf_income_categories_without_calculator
from ...domain.transactions.irpf_categories import normalize_irpf_category
from .retencion_soportada_source import declared_irpf_income_categories
from .source_mesh import CalculationSourceContext, CalculationSourceDiagnostic

if TYPE_CHECKING:
    from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource
    from ...domain.transactions.models import Transaction

__all__ = ["income_family_not_computed_diagnostics"]

_SOURCE_KIND: Final = BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
_SOURCE_REF_PREFIX: Final = "income-family:"


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
    uncomputed family is exactly what the aggregation does not keep.
    """
    uncomputed = irpf_income_categories_without_calculator(effective_date=context.period.end_date, authority=authority)
    if not uncomputed:
        return ()
    names = {str(token) for token in uncomputed}
    rows = Counter(
        category
        for transaction in window_transactions
        if (category := normalize_irpf_category(transaction.irpf_category)) in names
    )
    declared = declared_irpf_income_categories(context) or frozenset()
    return tuple(
        CalculationSourceDiagnostic(
            reason="income_family_not_computed",
            source_kind=_SOURCE_KIND.value,
            binding_source=_SOURCE_KIND,
            resolver_id=resolver_id,
            source_ref=f"{_SOURCE_REF_PREFIX}{family}",
            message=(
                f"income family {family!r} has no calculator: {rows[family]} ledger row(s) of the ejercicio are "
                f"classified to it"
                f"{' and the profile declares it' if family in declared else ''}; its casillas stay unresolved "
                f"until their figures are entered"
            ),
        )
        for family in sorted(names)
        if rows[family] or family in declared
    )
