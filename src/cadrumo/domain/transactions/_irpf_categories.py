"""Ledger IRPF category catalogue for invoice-withholding treatment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..categories import SpendingCategory, SpendingCategoryFamily, categories_for_family
from ._enums import TransactionDirection

LedgerIrpfCategoryPurpose = Literal[
    "activity_income_withholding",
    "rent_expense_withholding",
    "employment_income",
]


@dataclass(frozen=True, slots=True)
class LedgerIrpfCategoryDescriptor:
    """One public ``--irpf-category`` value understood by ledger workflows."""

    id: str
    purpose: LedgerIrpfCategoryPurpose
    directions: tuple[TransactionDirection, ...]
    net_paid_invoice: bool
    related_category_ids: tuple[str, ...] = ()


IRPF_CATEGORY_TRABAJO = "trabajo"
IRPF_CATEGORY_ACTIVIDAD_ECONOMICA = "actividad_economica"
RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING = frozenset(
    {
        SpendingCategory.ARRENDAMIENTO_LOCAL.value,
        SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO.value,
    },
)
RENT_IRPF_CATEGORIES_PAID_NET_OF_WITHHOLDING = RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING
PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING = frozenset(
    category.value for category in categories_for_family(SpendingCategoryFamily.PROFESSIONAL_SERVICES)
)

_LEDGER_IRPF_CATEGORY_CATALOGUE = (
    LedgerIrpfCategoryDescriptor(
        id=IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
        purpose="activity_income_withholding",
        directions=(TransactionDirection.INCOMING, TransactionDirection.OUTGOING),
        net_paid_invoice=True,
        related_category_ids=tuple(sorted(PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING)),
    ),
    LedgerIrpfCategoryDescriptor(
        id=SpendingCategory.ARRENDAMIENTO_LOCAL.value,
        purpose="rent_expense_withholding",
        directions=(TransactionDirection.OUTGOING,),
        net_paid_invoice=True,
        related_category_ids=(SpendingCategory.ARRENDAMIENTO_LOCAL.value,),
    ),
    LedgerIrpfCategoryDescriptor(
        id=SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO.value,
        purpose="rent_expense_withholding",
        directions=(TransactionDirection.OUTGOING,),
        net_paid_invoice=True,
        related_category_ids=(SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO.value,),
    ),
    LedgerIrpfCategoryDescriptor(
        id=IRPF_CATEGORY_TRABAJO,
        purpose="employment_income",
        directions=(TransactionDirection.INCOMING,),
        net_paid_invoice=False,
    ),
)


def ledger_irpf_category_catalogue() -> tuple[LedgerIrpfCategoryDescriptor, ...]:
    """Return public :class:`LedgerIrpfCategoryDescriptor` rows for ledger IRPF categories."""
    return _LEDGER_IRPF_CATEGORY_CATALOGUE


def has_non_work_irpf_category(value: str | None) -> bool:
    """Return whether a row carries an explicit non-salary withholding axis."""
    return value not in {None, "", IRPF_CATEGORY_TRABAJO}


def has_activity_irpf_category(value: str | None) -> bool:
    """Return whether a row carries the actividad-economica withholding axis."""
    return value == IRPF_CATEGORY_ACTIVIDAD_ECONOMICA


def has_rent_irpf_category(value: str | None) -> bool:
    """Return whether a row carries an explicit rental withholding axis."""
    return value in RENT_IRPF_CATEGORIES_PAID_NET_OF_WITHHOLDING


def format_irpf_category_ids(ids: frozenset[str] | tuple[str, ...]) -> str:
    """Render stable category ids for operator-facing validator messages."""
    return ", ".join(sorted(ids))
