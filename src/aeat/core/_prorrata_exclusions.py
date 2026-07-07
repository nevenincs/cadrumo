"""Closed value set for the LIVA art. 104.Tres prorrata denominator exclusions.

Art. 104.Tres lists the six operations excluded from BOTH terms of the prorrata
general ratio (art. 104.Dos): they are removed from the numerator (con-derecho
volume) AND the denominator (total volume) alike, so they never move the
percentage. This enum is the single typed home for that closed set, declared in
``core`` per the core-authority discipline (closed axes live in ``core/``,
hydrated at boundaries, asserted as members in tests).

The six exclusions split by HOW the ledger can recognise them:

* Four are AUTO-DERIVED and never operator-declared on a transaction:
  :attr:`Art104TresExclusion.DIRECT_IVA_CUOTAS` is structural (the volume rollup
  sums bases/contraprestaciones, never cuotas, so the cuota term is excluded by
  construction); :attr:`Art104TresExclusion.NON_SUBJECT_ART_7` and
  :attr:`Art104TresExclusion.SELF_SUPPLY_ART_9_1_D` are recognised from the
  existing :class:`~domain.iva.IvaCategory` taxonomy (a not-subject / autoconsumo
  category is not a con-derecho output category, so the volume side already
  resolves to neither term); :attr:`Art104TresExclusion.INVESTMENT_GOODS_DISPOSAL`
  is owned by the bienes-inversión register (read, never a transaction flag).

* Two are JUDGMENT facts the ledger cannot reliably infer and are therefore
  OPERATOR-DECLARED on the transaction:
  :attr:`Art104TresExclusion.FOREIGN_PERMANENT_ESTABLISHMENT` (the PE location)
  and :attr:`Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL` (the
  habituality of an inmobiliaria/financiera operation, with arrendamiento always
  habitual and the art. 20.Uno.18 financial-operation scope).

:data:`ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS` and
:data:`ART_104_TRES_AUTO_DERIVED_EXCLUSIONS` partition the closed set so the
transaction boundary can reject an auto-derived value as an operator tag (it
would double-count or misroute a value the category/register/structure already
excludes) and the rollup can reason about which side each exclusion comes from.

The "subvenciones no vinculadas al precio" case is deliberately NOT a member: it
is not an art. 104.Tres exclusion of otherwise-computed volume — Ley 3/2006
(BOE-A-2006-5691) removed subvenciones from the prorrata denominator entirely, so
they are simply not computed rather than excluded.

See Also:
    :class:`~domain.iva.IvaCategory`
        Taxonomy the auto-derived art. 7 / art. 9.1.d exclusions read from.
    :mod:`~application.calculations._prorrata_regularizacion`
        Annual volume rollup that skips the excluded operations on the ledger
        side of the declared-vs-ledger divergence advisory.
"""

from __future__ import annotations

from enum import StrEnum


class Art104TresExclusion(StrEnum):
    """One LIVA art. 104.Tres operation excluded from both terms of the prorrata ratio.

    The value byte-equals the stored token, so a StrEnum member compares,
    hashes, and JSON-serialises identically to its string.

    Attributes:
        FOREIGN_PERMANENT_ESTABLISHMENT: (art. 104.Tres 1.º) Operations carried
            out from permanent establishments outside the territory of
            application of the tax. Operator-declared (a judgment fact).
        DIRECT_IVA_CUOTAS: (art. 104.Tres 2.º) The IVA cuotas that directly taxed
            those operations. Auto-derived (structural — the volume rollup never
            sums cuotas).
        INVESTMENT_GOODS_DISPOSAL: (art. 104.Tres 3.º) The amount of entregas and
            exportaciones of bienes de inversión the taxpayer used in its
            activity. Auto-derived from the bienes-inversión register.
        NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL: (art. 104.Tres 4.º) Inmobiliario or
            financiero operations that are not the taxpayer's habitual business
            activity (arrendamiento always habitual; operaciones financieras per
            art. 20.Uno.18). Operator-declared (a judgment fact).
        NON_SUBJECT_ART_7: (art. 104.Tres 5.º) Operations not subject to the tax
            under art. 7. Auto-derived from the IVA category.
        SELF_SUPPLY_ART_9_1_D: (art. 104.Tres 6.º) The operations referred to in
            art. 9, número 1.º, letra d) (self-supplies of that letter).
            Auto-derived from the IVA category.
    """

    FOREIGN_PERMANENT_ESTABLISHMENT = "foreign_permanent_establishment"
    DIRECT_IVA_CUOTAS = "direct_iva_cuotas"
    INVESTMENT_GOODS_DISPOSAL = "investment_goods_disposal"
    NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL = "non_habitual_real_estate_or_financial"
    NON_SUBJECT_ART_7 = "non_subject_art_7"
    SELF_SUPPLY_ART_9_1_D = "self_supply_art_9_1_d"


#: The two art. 104.Tres exclusions that are genuine judgment facts (PE location,
#: habituality) the ledger cannot infer — the only members a taxpayer may declare
#: on a transaction. The transaction boundary rejects any other member.
ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS: frozenset[Art104TresExclusion] = frozenset(
    {
        Art104TresExclusion.FOREIGN_PERMANENT_ESTABLISHMENT,
        Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL,
    }
)

#: The four art. 104.Tres exclusions recognised structurally, from the IVA
#: category, or from the bienes-inversión register — never operator-declared.
ART_104_TRES_AUTO_DERIVED_EXCLUSIONS: frozenset[Art104TresExclusion] = frozenset(
    member for member in Art104TresExclusion if member not in ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS
)


__all__ = [
    "ART_104_TRES_AUTO_DERIVED_EXCLUSIONS",
    "ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS",
    "Art104TresExclusion",
]
