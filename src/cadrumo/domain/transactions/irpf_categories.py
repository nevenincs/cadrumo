"""Ledger IRPF category catalogue for invoice-withholding treatment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..categories.spending_category import SpendingCategory, SpendingCategoryFamily, categories_for_family
from .enums import TransactionDirection

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


_CATALOGUE_BY_ID: dict[str, LedgerIrpfCategoryDescriptor] = {
    descriptor.id: descriptor for descriptor in _LEDGER_IRPF_CATEGORY_CATALOGUE
}


def ledger_irpf_category_catalogue() -> tuple[LedgerIrpfCategoryDescriptor, ...]:
    """Return public :class:`LedgerIrpfCategoryDescriptor` rows for ledger IRPF categories."""
    return _LEDGER_IRPF_CATEGORY_CATALOGUE


def ledger_irpf_category_ids() -> tuple[str, ...]:
    """Return every public ledger IRPF category id in stable sorted order."""
    return tuple(sorted(_CATALOGUE_BY_ID))


def normalize_irpf_category(value: str | None) -> str | None:
    """Return the canonical catalogue spelling of an ``irpf_category`` token.

    Every surface that reads ``irpf_category`` -- the gross invariant, the
    ledger preflight, and the Renta aggregators -- must agree on what a token
    names, so the one normalisation lives here rather than at each reader.
    The catalogue ids are lowercase, and a token that differs only in case or
    surrounding whitespace names the same category; resolving that per reader
    is what let ``TRABAJO`` classify as employment in the preflight while
    naming no descriptor at all in the gross invariant.

    Normalisation is deliberately narrow: case folding and whitespace only.
    It never maps one category onto another, so the closed catalogue stays
    closed and an unknown token stays unknown.

    Args:
        value: The row's raw ``irpf_category`` token, if any.

    Returns:
        The normalised token, or ``None`` when there is no token to resolve
        (absent, or blank after stripping).
    """
    if value is None:
        return None
    return value.strip().casefold() or None


def ledger_irpf_category(
    value: str | None,
    *,
    direction: TransactionDirection | None = None,
) -> LedgerIrpfCategoryDescriptor | None:
    """Return the withholding descriptor ``value`` names for ``direction``, or ``None``.

    ``None`` is returned for three distinct situations that are all "this row
    declares no ledger withholding treatment": no token at all, a token that
    names no catalogue row, and a token whose descriptor does not admit
    ``direction``.

    The last case is the one worth stating. ``irpf_category`` is not a
    single-taxonomy field: alongside the ledger withholding ids it also carries
    the Renta income-type tags that classify which LIRPF branch a row's income
    or expense belongs to. Those tags are a different axis with no withholding
    treatment attached, so resolving them here to ``None`` is correct rather
    than an error — refusing them would refuse a legitimate classification.
    What must not happen is the inverse: an unrecognised or wrong-direction
    token silently unlocking the withholding relaxation on the gross invariant.

    Args:
        value: The row's ``irpf_category`` token, if any.
        direction: When given, the row's :class:`TransactionDirection`; the
            descriptor is returned only if it declares that direction.

    Returns:
        The matching descriptor, or ``None``.
    """
    normalized = normalize_irpf_category(value)
    if normalized is None:
        return None
    descriptor = _CATALOGUE_BY_ID.get(normalized)
    if descriptor is None:
        return None
    if direction is not None and direction not in descriptor.directions:
        return None
    return descriptor


def has_non_work_irpf_category(value: str | None, *, direction: TransactionDirection) -> bool:
    """Return whether a row carries an explicit non-salary withholding axis.

    Resolved through the closed catalogue rather than "anything that is not
    ``trabajo``": ``net_paid_invoice`` is the descriptor's own statement that
    the declared invoice substrate may legitimately exceed the cash movement,
    and ``directions`` is its statement of which flow the treatment is defined
    for -- rent withholding is paid, never received.
    """
    descriptor = ledger_irpf_category(value, direction=direction)
    return descriptor is not None and descriptor.net_paid_invoice


def has_activity_irpf_category(value: str | None, *, direction: TransactionDirection) -> bool:
    """Return whether a row carries the actividad-economica withholding axis."""
    descriptor = ledger_irpf_category(value, direction=direction)
    return descriptor is not None and descriptor.purpose == "activity_income_withholding"


def has_rent_irpf_category(value: str | None, *, direction: TransactionDirection) -> bool:
    """Return whether a row carries an explicit rental withholding axis."""
    descriptor = ledger_irpf_category(value, direction=direction)
    return descriptor is not None and descriptor.purpose == "rent_expense_withholding"


def has_employment_irpf_category(value: str | None, *, direction: TransactionDirection) -> bool:
    """Return whether a row carries the trabajo (nómina) employment axis.

    Resolved through the closed catalogue so the ledger preflight reads the
    same token the gross invariant does, rather than comparing the raw string
    to a local ``"trabajo"`` literal.
    """
    descriptor = ledger_irpf_category(value, direction=direction)
    return descriptor is not None and descriptor.purpose == "employment_income"


def format_irpf_category_ids(ids: frozenset[str] | tuple[str, ...]) -> str:
    """Render stable category ids for operator-facing validator messages."""
    return ", ".join(sorted(ids))
