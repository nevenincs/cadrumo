"""Art. 81 maternity contribution behavior for descendants."""

from __future__ import annotations

from ...core.descendant_relacion import ART_81_1_MATERNIDAD_RELACIONES, DescendantRelacion
from .descendant_record import DescendantRecordBase
from .family_types import (
    ART_81_1_ENTRY_WINDOW_YEARS,
    MAX_AGE_MENOR_TRES,
    MinimoDescendientesThresholds,
    months_of_year_between,
)


class DescendantMaternityMixin(DescendantRecordBase):
    """The maternity deduction facts a descendant carries."""

    def maternidad_eligible_meses(self, filing_year: int) -> int:
        """Months of *filing_year* the Art. 81.1 deducción may reach for this descendant.

        The whole eligible window, not one limb of it: the under-three months
        and the adopción/acogimiento entry months together, clipped so that no
        month precedes the entry event.

        The clip is load-bearing. The under-three limb runs from the BIRTH month
        for every relación, including an adopted one, so an unclipped union
        reaches the months before the child was the taxpayer's: a child born in
        January and adopted in October yields a full twelve where three are due.

        An unclipped union is defensible only on a case that does not
        discriminate — an infant adopted in October, argued from the claim that
        neither limb alone reaches twelve. That infant's under-three limb IS
        twelve, so the union merely equals the wider limb there. The union
        exceeds the wider limb only in a year containing both the entry month
        and the third-birthday month, and the single month distinguishing them
        falls before the entry event.

        Clipping is written as a clip rather than as "return the entry window",
        which is what it currently reduces to: with the anchor never earlier than
        the birth, the two are algebraically identical today. Expressing the RULE
        — no month before the child was yours — keeps this correct if either limb
        is later widened, where the shortcut silently would not.

        A descendant with no entry date is unclipped, so an ordinary child is
        unaffected and the method degenerates to the under-three limb.
        """
        return len(self._maternidad_eligible_months(filing_year))

    def _maternidad_eligible_months(self, filing_year: int) -> frozenset[int]:
        """The Art. 81.1 eligible months: both limbs, clipped to the entry anchor."""
        months = self._maternidad_edad_months(filing_year) | self._maternidad_entry_window_months(filing_year)
        anchor = self.art_58_2_entry_date()
        if anchor is None:
            return months
        return frozenset(month for month in months if (filing_year, month) >= (anchor.year, anchor.month))

    def _maternidad_edad_months(self, filing_year: int) -> frozenset[int]:
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
            (self.birth_date.year + MAX_AGE_MENOR_TRES, self.birth_date.month),
            filing_year,
        )

    def art_81_1_entry_window_meses(self, filing_year: int) -> int:
        """Months of *filing_year* inside the Art. 81.1 adopción/acogimiento window.

        A SEPARATE window from the Art. 58.2 one, and separate because the two
        statutes measure differently for the same child. Art. 58.2 counts whole
        tax PERIODS — "en el período impositivo en que se inscriba en el Registro
        Civil y en los dos siguientes" — so annual granularity suffices there.
        Art. 81.1 instead runs "durante los tres años siguientes a la FECHA de la
        inscripción en el Registro Civil", and where no inscription is required,
        "durante los tres años posteriores a la fecha de la resolución judicial o
        administrativa que la declare". That is a date, so the window opens and
        closes mid-year and the two disagree in BOTH directions for the same
        child: the entry period is granted whole by Art. 58.2 while its months
        before the inscription fall outside this one, and the fourth calendar
        year is inside this one while Art. 58.2 has already closed.

        The window is age-independent — "con independencia de la edad del menor"
        — which is the whole point of the limb: it reaches a child adopted well
        after their third birthday, for whom the ordinary limb grants nothing.

        Anchors on :meth:`art_58_2_entry_date`, the FIRST entitling event, rather
        than on whichever date the record happens to carry. A fostered-then-
        adopted child anchored on the adoption would draw a second three-year
        window after the first, granting up to six years where the statute allows
        three. Sharing the anchor keeps the cap intact.

        The entitling relación set is shared with Art. 58.2 as well, and that is
        a reading rather than an assumption. The two statutes enumerate
        differently on their face — Art. 58.2 says "acogimiento, tanto
        preadoptivo como permanente" while Art. 81.1 says "acogimiento
        permanente o delegación de guarda para la convivencia" — but the
        delegación de guarda IS the successor figure to the abolished acogimiento
        preadoptivo, so the two enumerations cover the same placements under
        their respective vocabularies.

        Returns ``0`` for a relación the statutes exclude and for an entitling
        relación whose entry date is not yet recorded.
        """
        return len(self._maternidad_entry_window_months(filing_year))

    def _maternidad_entry_window_months(self, filing_year: int) -> frozenset[int]:
        """The months of *filing_year* covered by the Art. 81.1 entry-event limb."""
        anchor = self.art_58_2_entry_date()
        if anchor is None:
            return frozenset[int]()
        return months_of_year_between(
            (anchor.year, anchor.month),
            (anchor.year + ART_81_1_ENTRY_WINDOW_YEARS, anchor.month),
            filing_year,
        )

    def maternidad_contributing_meses(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
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
        months the authority refuses. Reading
        :data:`~cadrumo.core.ART_81_1_MATERNIDAD_RELACIONES` rather than
        restating the membership keeps the three populations on this axis
        distinct, which is the property whose loss produced that defect.
        """
        if self.relacion not in ART_81_1_MATERNIDAD_RELACIONES:
            return 0
        if not self.is_eligible_ordinary(
            filing_year,
            thresholds=thresholds,
            dependencia_assimilation_available=dependencia_assimilation_available,
        ):
            return 0
        return len(frozenset(self.meses_madre_trabajo) & self._maternidad_eligible_months(filing_year))


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
    :attr:`~core.DescendantRelacion.GUARDA_Y_CUSTODIA_JUDICIAL` was added for
    exactly that carer and is excluded from
    :data:`~core.ART_81_1_MATERNIDAD_RELACIONES`, so they can state their
    relationship truthfully and the deducción already does not reach them. The
    behaviour was right; the reasoning beside it was written twice and neither
    copy followed the axis when it gained the member. Stating it once is what
    surfaced that.

    Asked in two places, at two different moments: the declaration surface warns
    the operator as they type, and the calculate path catches an already-stored
    row, including one declared before the notice existed. Each keeps its own
    months gate -- declared months at declaration time, contributing months at
    calculate time -- because those genuinely differ. What must not differ is
    which relación is ambiguous, and that lived as a repeated
    ``is DescendantRelacion.DESCENDIENTE`` at both sites with the reasoning
    restated beside each. A member added to the axis for either population would
    have had to reach both.
    """
    return relacion is DescendantRelacion.DESCENDIENTE
