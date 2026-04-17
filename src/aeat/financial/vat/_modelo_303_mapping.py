"""``VATCategory`` → Modelo 303 casilla bridge table.

Single source of truth for the question: "given a transaction's
:class:`VATCategory` and :class:`InvoiceDirection`, which casillas
of Modelo 303 does it contribute to?". Both the upstream
classifier (:func:`aeat.financial.vat.classify_vat`) and the
downstream filing draft builder consume this table — divergence is
impossible by construction.

The mapping is a frozen :class:`MappingProxyType` over a literal
dict, declared at module import time. Every :class:`VATCategory`
member is either present in the mapping (for at least one
direction) or explicitly listed in :data:`_OUT_OF_SCOPE_V1`. The
import-time invariant raises :class:`RuntimeError` on drift.

The casilla layout matches the wave-2 Modelo 303 ruleset
(`src/aeat/formulas/_rulesets/modelo_303_*.py`) which covers
casillas 01-09, 28-45, 64-71. Categories whose contributions
target informational-only or régimen-simplificado casillas
(46-63, 59, 60, 80+) are tagged with the casilla id but flagged
as informational; downstream consumers honor the role + sign and
ignore the contribution if the wave-2 ruleset does not declare
the casilla.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from pydantic import Field, model_validator

from ._classification import InvoiceDirection
from ._schema import VATCategory, VATRateKind, _StrictFrozen


class CasillaRole(StrEnum):
    """Whether a contribution lands on the base or the cuota line."""

    BASE = "base"
    CUOTA = "cuota"


class Modelo303Contribution(_StrictFrozen):
    """One bucket-level contribution from a classified transaction."""

    casilla_id: str = Field(min_length=2, max_length=4)
    role: CasillaRole
    sign: int = Field(ge=-1, le=1)
    rate_kind: VATRateKind | None = Field(
        default=None,
        description=(
            "When the contribution depends on a tier (e.g. casilla "
            "01/04/07 base ↔ rate kind), this field carries the tier; "
            "``None`` for non-tiered casillas."
        ),
    )

    @model_validator(mode="after")
    def _reject_zero_sign(self) -> Modelo303Contribution:
        """Sign must be ±1; zero contributions are not modelable."""
        if self.sign == 0:
            raise ValueError("Modelo303Contribution.sign must be -1 or +1, not 0")
        return self


_BASE_PLUS = lambda casilla_id, rate_kind: Modelo303Contribution(  # noqa: E731
    casilla_id=casilla_id,
    role=CasillaRole.BASE,
    sign=1,
    rate_kind=rate_kind,
)
_CUOTA_PLUS = lambda casilla_id, rate_kind: Modelo303Contribution(  # noqa: E731
    casilla_id=casilla_id,
    role=CasillaRole.CUOTA,
    sign=1,
    rate_kind=rate_kind,
)


_MAPPING: dict[tuple[VATCategory, InvoiceDirection], tuple[Modelo303Contribution, ...]] = {
    # ── Domestic régimen general — issued (devengado) ─────────────────
    (VATCategory.DOMESTIC_GENERAL_21, InvoiceDirection.ISSUED): (_BASE_PLUS("07", VATRateKind.GENERAL),),
    (VATCategory.DOMESTIC_REDUCED_10, InvoiceDirection.ISSUED): (_BASE_PLUS("04", VATRateKind.REDUCED),),
    (VATCategory.DOMESTIC_SUPER_REDUCED_4, InvoiceDirection.ISSUED): (_BASE_PLUS("01", VATRateKind.SUPER_REDUCED),),
    (VATCategory.DOMESTIC_ZERO, InvoiceDirection.ISSUED): (_BASE_PLUS("01", VATRateKind.ZERO),),
    # ── Domestic régimen general — received (deducible) ───────────────
    # Spanish 303 lumps every input-VAT base on casilla 28; the cuota
    # lands on casilla 29 regardless of the rate tier the supplier
    # invoiced at. The rate_kind on the contribution preserves the
    # provenance so reverse-audit ledgers can sanity-check
    # cuota = base x rate.
    (VATCategory.DOMESTIC_GENERAL_21, InvoiceDirection.RECEIVED): (
        _BASE_PLUS("28", VATRateKind.GENERAL),
        _CUOTA_PLUS("29", VATRateKind.GENERAL),
    ),
    (VATCategory.DOMESTIC_REDUCED_10, InvoiceDirection.RECEIVED): (
        _BASE_PLUS("28", VATRateKind.REDUCED),
        _CUOTA_PLUS("29", VATRateKind.REDUCED),
    ),
    (VATCategory.DOMESTIC_SUPER_REDUCED_4, InvoiceDirection.RECEIVED): (
        _BASE_PLUS("28", VATRateKind.SUPER_REDUCED),
        _CUOTA_PLUS("29", VATRateKind.SUPER_REDUCED),
    ),
    (VATCategory.DOMESTIC_ZERO, InvoiceDirection.RECEIVED): (_BASE_PLUS("28", VATRateKind.ZERO),),
    # Exempt + not-subject + intra-community supply: informational only.
    # Out-of-scope categories are handled below via _OUT_OF_SCOPE_V1.
    # ── Domestic reverse charge ───────────────────────────────────────
    # Issuer side: invoice base contributes to the appropriate
    # devengado base casilla (rate_tier-aware); no cuota line.
    (VATCategory.DOMESTIC_REVERSE_CHARGE, InvoiceDirection.ISSUED): (_BASE_PLUS("07", VATRateKind.GENERAL),),
    # Recipient side: self-assessed cuota lands on both the
    # devengado side (operaciones interiores) and the deducible side.
    (VATCategory.DOMESTIC_REVERSE_CHARGE, InvoiceDirection.RECEIVED): (
        _BASE_PLUS("28", VATRateKind.GENERAL),
        _CUOTA_PLUS("29", VATRateKind.GENERAL),
    ),
    # ── Intra-community ──────────────────────────────────────────────
    (VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE, InvoiceDirection.RECEIVED): (
        _BASE_PLUS("36", VATRateKind.GENERAL),
        _CUOTA_PLUS("37", VATRateKind.GENERAL),
    ),
    # ── Imports ──────────────────────────────────────────────────────
    (VATCategory.IMPORT_THIRD_COUNTRY, InvoiceDirection.RECEIVED): (
        _BASE_PLUS("32", VATRateKind.GENERAL),
        _CUOTA_PLUS("33", VATRateKind.GENERAL),
    ),
}

# Categories that deliberately have no Modelo 303 contribution in v1.
# Each is tagged with the wave-2 ADR rationale.
_OUT_OF_SCOPE_V1: frozenset[VATCategory] = frozenset(
    {
        VATCategory.DOMESTIC_EXEMPT,  # informational; no 303 base/cuota wiring
        VATCategory.DOMESTIC_NOT_SUBJECT,  # informational
        VATCategory.INTRA_COMMUNITY_SUPPLY,  # casilla 59 — informational, deferred
        VATCategory.INTRA_COMMUNITY_TRIANGULATION,  # complex, deferred
        VATCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,  # casilla 60 — deferred
        VATCategory.RECARGO_EQUIVALENCIA,  # régimen especial; out-of-scope v1
        VATCategory.REGIMEN_SIMPLIFICADO,  # régimen especial; out-of-scope v1
        VATCategory.OPERACION_NO_SUJETA,  # informational
        VATCategory.ERRONEOUS_INVOICE,  # quarantined upstream
        VATCategory.UNKNOWN,  # quarantined upstream
    }
)


def _validate_coverage() -> None:
    """Assert every :class:`VATCategory` is mapped or explicitly out-of-scope.

    Runs at module import time. The check guards against silent
    classification drift when a future enum addition is missed by
    the bridge update.
    """
    mapped_categories = {category for category, _ in _MAPPING}
    seen = mapped_categories | _OUT_OF_SCOPE_V1
    missing = [m for m in VATCategory if m not in seen]
    if missing:
        names = ", ".join(member.name for member in missing)
        raise RuntimeError(
            f"Modelo 303 casilla mapping coverage is incomplete: "
            f"unhandled VATCategory members: {names}. Either add them "
            f"to MODELO_303_CASILLA_MAPPING or to _OUT_OF_SCOPE_V1 with "
            f"a citation."
        )


_validate_coverage()


MODELO_303_CASILLA_MAPPING: Mapping[
    tuple[VATCategory, InvoiceDirection],
    tuple[Modelo303Contribution, ...],
] = MappingProxyType(_MAPPING)
"""Frozen mapping from ``(VATCategory, InvoiceDirection)`` to contributions."""


def lookup_modelo_303_contribution(
    *,
    category: VATCategory,
    direction: InvoiceDirection,
) -> tuple[Modelo303Contribution, ...]:
    """Return the Modelo 303 contributions for a ``(category, direction)``.

    Args:
        category: The :class:`VATCategory` of the classified transaction.
        direction: Whether the autónomo issued or received the invoice.

    Returns:
        A tuple of :class:`Modelo303Contribution`. Returns an empty
        tuple when the pair is unmapped (typically because the
        category is documented in ``_OUT_OF_SCOPE_V1`` for the v1
        wave).
    """
    return MODELO_303_CASILLA_MAPPING.get((category, direction), ())


__all__ = [
    "MODELO_303_CASILLA_MAPPING",
    "CasillaRole",
    "Modelo303Contribution",
    "lookup_modelo_303_contribution",
]
