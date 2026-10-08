"""Art. 81 maternity contribution behavior for descendants."""

from __future__ import annotations

from ...core.descendant_relacion import DescendantRelacion
from ..calculations.registry.descendant_relacion_catalogue import (
    descendant_relacion_default_token,
    descendant_relacion_maternity_tokens,
)
from .descendant_record import DescendantRecordBase
from .family_fact_context import FamilyFactResolutionContext
from .family_types import (
    MinimoDescendientesThresholds,
    months_of_year_between,
)


class DescendantMaternityMixin(DescendantRecordBase):
    """The maternity deduction facts a descendant carries."""

    @staticmethod
    def art_81_1_maternity_relations(
        *,
        context: FamilyFactResolutionContext,
    ) -> frozenset[DescendantRelacion]:
        """Resolve the dated Art. 81.1 relationship catalogue.

        The relationship population is registry-owned. An absent, malformed,
        or wrong-family fact is a refusal rather than permission to fall back to
        a local set, because a local set would become a second legal authority.
        """
        return descendant_relacion_maternity_tokens(
            effective_date=context.filing_period,
            authority=context.authority,
        )

    def _maternidad_eligible_months(self, filing_year: int, *, context: FamilyFactResolutionContext) -> frozenset[int]:
        """The Art. 81.1 eligible months: both limbs, clipped to the entry anchor."""
        months = self._maternidad_edad_months(filing_year, context=context) | self._maternidad_entry_window_months(
            filing_year, context=context
        )
        anchor = self.art_58_2_entry_date()
        if anchor is None:
            return months
        return frozenset(month for month in months if (filing_year, month) >= (anchor.year, anchor.month))

    def _maternidad_edad_months(self, filing_year: int, *, context: FamilyFactResolutionContext) -> frozenset[int]:
        """The months of *filing_year* covered by the Art. 81.1 under-three limb.

        The article runs "hasta que el menor alcance los tres años de edad",
        which is a MONTH boundary rather than a year-end age test, and the
        authority draws it twice: the month of birth counts in full, and the
        month in which the child turns three does not.

        Comparing ``(year, month)`` pairs rather than constructing a third-
        birthday date is deliberate: a 29 February birth has no third-birthday
        date in a non-leap year, and building one raises.
        """
        return months_of_year_between(
            (self.birth_date.year, self.birth_date.month),
            (self.birth_date.year + context.integer("lirpf-art-58-under-three-maximum-age"), self.birth_date.month),
            filing_year,
        )

    def _maternidad_entry_window_months(
        self, filing_year: int, *, context: FamilyFactResolutionContext
    ) -> frozenset[int]:
        """The months of *filing_year* covered by the Art. 81.1 entry-event limb."""
        anchor = self.art_58_2_entry_date()
        if anchor is None:
            return frozenset[int]()
        return months_of_year_between(
            (anchor.year, anchor.month),
            (anchor.year + context.integer("lirpf-art-81-adoption-entry-window-years"), anchor.month),
            filing_year,
        )

    def maternidad_contributing_meses(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
        context: FamilyFactResolutionContext,
        dependencia_assimilation_available: bool = False,
    ) -> int:
        """Art. 81.1 months this descendant contributes to the deducción in *filing_year*.

        The split between what the operator supplies and what the engine applies
        follows the statute rather than a design preference, and the two halves
        must not re-derive each other.

        The EMPLOYMENT months are the operator's and stay so:
        ``meses_madre_trabajo`` records whether the mother held contributory
        or assistance unemployment benefit at the birth, or Social Security /
        mutualidad registration with the contributed period the article requires.
        That is her employment history, which this application does not hold and
        must not infer. It is separately reported to the authority by its own
        informative return, so the declared figure is checkable against a record
        the authority already holds.

        The CHILD-side condition is the engine's, and it is the ORDINARY mínimo
        test rather than a bespoke one: the authority grants the deduction to
        women with children under three "con derecho a la aplicación del mínimo
        por descendientes", so the qualifying child is defined by the predicate
        this record already computes — cohabitation or assimilated dependency,
        the Art. 58.1 rentas ceiling, and the Art. 61 norma 2ª own-return
        exclusion. Re-asserting it here would create a second authority for a
        question :meth:`is_eligible_ordinary` already answers, and the two would
        drift the moment either statute moved.

        *thresholds* is required for the same reason it is required there: an
        optional ceiling lets a caller evaluate the household limb while
        silently skipping the two income conditions, which inflates the
        deducción.

        The declared months are INTERSECTED with the eligible window rather than
        trusted outright. An operator who declared correctly is unaffected,
        because their months already lie inside the window; one who declared raw
        employment months has the out-of-window ones removed. The intersection
        can only ever reduce, so it cannot invent an entitlement.

        A real intersection rather than a cap on a count, and the difference is
        not cosmetic: a count clipped by the window's SIZE keeps months the
        window does not contain, so a mother declaring months outside it kept an
        entitlement for months she did not qualify in. Months in, months
        compared, months out.

        That window is :meth:`_maternidad_eligible_months`, which carries both of
        the article's limbs and the clip that keeps a month from preceding the
        entry event. It is asked for rather than recomposed here: the window is
        one rule with one owner, and a second assembly of it at a call site
        drifts from the first without any gate noticing.

        The relación gate is SEPARATE from the mínimo test and runs first. Both
        are necessary and neither implies the other: Art. 58.1 assimilates
        temporal acogimiento while Art. 81.1 excludes it outright, so gating only
        on entitlement to the mínimo granted a temporal carer a full twelve
        months the authority refuses. Reading the dated registry relationship
        catalogue rather than restating membership keeps the three populations
        on this axis distinct, which is the property whose loss produced that
        defect.
        """
        if self.relacion not in self.art_81_1_maternity_relations(context=context):
            return 0
        if not self.is_eligible_ordinary(
            filing_year,
            thresholds=thresholds,
            context=context,
            dependencia_assimilation_available=dependencia_assimilation_available,
        ):
            return 0
        return len(frozenset(self.meses_madre_trabajo) & self._maternidad_eligible_months(filing_year, context=context))


def art_81_1_maternity_relations(
    *,
    context: FamilyFactResolutionContext,
) -> frozenset[DescendantRelacion]:
    """Resolve the dated Art. 81.1 relationship population from authority."""
    return DescendantMaternityMixin.art_81_1_maternity_relations(context=context)


def relacion_is_ambiguous_for_maternidad(relacion: DescendantRelacion) -> bool:
    """Whether a declared relación cannot distinguish an Art. 81.1 child from a mínimo-only descendant.

    ``DESCENDIENTE`` is the ONLY ambiguous value, and for ONE remaining
    population: a grandchild or other descendant by consanguinidad other than a
    child, whom the AEAT manual documents as mínimo-eligible under Art. 58.1
    while excluding them from Art. 81.1. The axis has no member for them, so a
    filer with such a child has no truthful value but ``DESCENDIENTE``. That is
    also the value a filer with a genuine hijo gets by never being asked, since
    the fact is never written for the default even when the operator typed it
    explicitly. The two are indistinguishable at the stored fact, which is the
    whole reason a notice exists rather than a refusal.

    Both sites used to name a SECOND population here -- a minor held under
    guarda y custodia by judicial resolución -- and both were out of date.
    The judicial-guard relationship is represented by its own dated registry
    token and is excluded by the Art. 81.1 registry
    catalogue, so they can state their relationship truthfully and the
    deducción already does not reach them. The behaviour was right; the
    reasoning beside it was written twice and neither copy followed the axis
    when it gained the member. Stating it once is what surfaced that.

    Asked in two places, at two different moments: the declaration surface warns
    the operator as they type, and the calculate path catches an already-stored
    row, including one declared before the notice existed. Each keeps its own
    months gate -- declared months at declaration time, contributing months at
    calculate time -- because those genuinely differ. What must not differ is
    which relación is ambiguous, and that lived as a repeated
    the ordinary descendant token at both sites with the reasoning
    restated beside each. A member added to the axis for either population would
    have had to reach both.
    """
    return relacion == descendant_relacion_default_token()
