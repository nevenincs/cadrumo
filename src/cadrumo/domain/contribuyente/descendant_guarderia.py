"""Art. 81.2 guardería contribution behavior for descendants."""

from __future__ import annotations

from ...core import ART_81_1_MATERNIDAD_RELACIONES
from ...core.external_constants import DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR
from .descendant_maternity import DescendantMaternityMixin
from .family_types import (
    MAX_AGE_MENOR_TRES,
    NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS,
    MinimoDescendientesThresholds,
    months_of_year_between,
)


class DescendantGuarderiaMixin(DescendantMaternityMixin):
    """The guarderia spend facts a descendant carries."""

    def guarderia_art_81_1_meses(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
        dependencia_assimilation_available: bool = False,
    ) -> int:
        """Art. 81.1 months the guardería increment prorates by in *filing_year*.

        The increment is prorated by "el número de meses en que se cumplan de
        forma simultánea los requisitos exigidos en el artículo 81.1 y 2", and
        this answers the 81.1 half FOR THE INCREMENT — which is not the same
        question as :meth:`maternidad_contributing_meses`, even though every
        gate below is shared with it.

        Named for the ARTICLE HALF it answers, not for simultaneity, because it
        is only one side of the pair: :meth:`guarderia_simultaneous_meses` is
        where the two sides actually meet. The plain "simultaneity" name once sat
        here, one word away from that method, and the two were mistaken for each
        other by a reader holding the source open.

        The difference is the child's AGE, and it is the whole reason this
        method exists. The deducción itself runs only while the child is under
        three, so that method clips to :meth:`maternidad_eligible_meses`. The
        increment does not: Capítulo 18 states that where "el descendiente
        cumpla los tres años en el mes de enero" or "la madre comience a
        trabajar en el año en el que el hijo cumple esa edad, pero después de
        haberla cumplido", then "no se podrá aplicar la deducción por
        maternidad, si bien ello no impedirá aplicar el incremento". Reusing the
        deducción's own month count therefore forces the increment to zero in
        exactly the two cases the authority names as still qualifying.

        So the age CEILING is dropped and everything else is kept. The relación
        gate, the ordinary-mínimo test and the mother's own declared months all
        still bind, because the article's remaining requirements are hers and the
        child's entitlement to the mínimo — neither of which the birthday ends.
        The FLOOR is kept too: no month may precede the child being this
        taxpayer's, which is the entitling event rather than the age limb.

        Dropping only the ceiling cannot over-grant on its own, because the
        Art. 81.2 side bounds the pair and already returns ``0`` for every child
        past the period they turn three
        (:meth:`guarderia_qualifying_meses`).
        """
        if self.relacion not in ART_81_1_MATERNIDAD_RELACIONES:
            return 0
        if not self.is_eligible_ordinary(
            filing_year,
            thresholds=thresholds,
            dependencia_assimilation_available=dependencia_assimilation_available,
        ):
            return 0
        return len(self._guarderia_art_81_1_months(filing_year))

    def _guarderia_art_81_1_months(self, filing_year: int) -> frozenset[int]:
        """The Art. 81.1 months, clipped to the increment's own requirement window."""
        return frozenset(self.meses_madre_trabajo) & self._guarderia_requirement_months(filing_year)

    def guarderia_simultaneous_meses(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
        dependencia_assimilation_available: bool = False,
    ) -> int:
        """Months in which the Art. 81.1 AND Art. 81.2 requirements BOTH held.

        The proration basis the manual describes — "el número de meses en que se
        cumplan de forma simultánea los requisitos exigidos en el artículo 81.1
        y 2" — computed as what it says: an intersection of two month sets.

        The geometry is the whole point. Two sets of the same SIZES may share
        every month, some, or none, and the three have different correct
        answers; a ``min`` over their counts returns the same number for all
        three. AEAT's caso a is the partial case — mother May to August, nursery
        January to June, two shared months, ``1.000 ÷ 12 × 2 = 166,67`` — where
        the count reading yields four and 333,33, over-granting the deducción
        and so under-declaring tax.

        Falls back to the count ONLY where the Art. 81.2 months are genuinely
        unknown, which is the annual-total shape
        (:meth:`guarderia_qualifying_months` returning ``None``). There the
        record holds no month information to intersect, so a bound is the honest
        answer rather than a discarded one, and it is disclosed to the operator
        by the monthly-detail advisory rather than presented as measured.
        """
        mother = self.guarderia_art_81_1_meses(
            filing_year,
            thresholds=thresholds,
            dependencia_assimilation_available=dependencia_assimilation_available,
        )
        if mother <= 0:
            return 0
        nursery = self.guarderia_qualifying_months(filing_year)
        if nursery is None:
            return min(mother, self.guarderia_qualifying_meses(filing_year))
        return len(self._guarderia_art_81_1_months(filing_year) & nursery)

    def _guarderia_requirement_months(self, filing_year: int) -> frozenset[int]:
        """The Art. 81.1 requirement months for the increment: the deducción window without its age ceiling."""
        entitling = months_of_year_between(
            (self.birth_date.year, self.birth_date.month),
            (filing_year + 1, 1),
            filing_year,
        ) | self._maternidad_entry_window_months(filing_year)
        anchor = self.art_58_2_entry_date()
        if anchor is None:
            return entitling
        return frozenset(month for month in entitling if (filing_year, month) >= (anchor.year, anchor.month))

    def maternidad_alta_posterior_increment_applies(self, filing_year: int) -> bool:
        """Whether Art. 81.1's post-birth alta increment applies to this child in *filing_year*.

        Two conditions, both the operator's to supply and neither this method's
        to infer: a completion month must be declared
        (``alta_posterior_nacimiento_mes``), and *filing_year* must be at or
        after :data:`~cadrumo.core.external_constants.DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR`
        — the route did not exist before it, so a month recorded against an
        earlier filing carries no increment.

        Does not itself re-check :meth:`maternidad_contributing_meses`'s
        eligibility gate: a caller only consults this for a ``hijo_id`` already
        present in that method's contributing pairs, exactly as
        :meth:`meses_maternidad_por_descendiente` does.
        """
        return (
            self.alta_posterior_nacimiento_mes is not None
            and filing_year >= DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR
        )

    def guarderia_contributing_spend(self, filing_year: int) -> int:
        """Art. 81.2 guardería spend this descendant contributes in *filing_year*.

        The THIRD BIRTHDAY IS NOT A BOUNDARY HERE, and that is the whole subtlety
        of this method. Capítulo 18 says "En el período impositivo en que el hijo
        menor cumpla tres años, el incremento podrá resultar de aplicación
        respecto de los gastos incurridos con posterioridad al cumplimiento de
        dicha edad hasta el mes anterior a aquel en el que pueda comenzar el
        segundo ciclo de educación infantil." That sentence GRANTS the months
        after the birthday, which the under-three limb could not otherwise
        reach; it does not withdraw the months before it. Read as a restriction
        instead, it drops every pre-birthday month and hands a taxpayer zero on
        facts the authority works to a positive figure.

        The manual settles it with its own worked case rather than by wording:
        an elder child who "en septiembre cumple 3 años" is granted the
        increment over "6 meses completos (de enero a junio)", every one of them
        BEFORE the September birthday, for ``1.000 ÷ 12 × 6 = 500``. A
        post-birthday-only reading returns zero on exactly those facts, so the
        oracle decides the question the prose leaves open.

        So the whole period counts, and the declared months are taken as
        declared. The UPPER bound is still not derived, and that remains a
        deliberate non-derivation rather than an oversight. The statute ends the
        extension at the month before the second cycle of infant education may
        begin, which each region determines. The informative return reporting
        childcare custody is filed EXCLUSIVELY by the centre, never by the
        taxpayer, and the centre is required to report exactly those months.
        Re-deriving the boundary here would compute, from a calendar this
        application does not hold, a determination the law assigns to a party who
        does — and risk contradicting the return the authority already holds from
        that party. So the months a taxpayer can evidence are taken as the months
        the centre determined, and that evidence is the monthly detail.

        Returns ``0`` for a non-cohabiting descendant, and for the turning-three
        period when only an ANNUAL total is on record. The reason for that zero
        is the UPPER edge, not the birthday: a single yearly figure cannot be
        apportioned to a window whose closing month this application declines to
        derive. It is an unanswerable question about a figure the operator can
        replace with the monthly detail their centre already certified, and
        :meth:`guarderia_needs_monthly_detail` reports it so they are asked.
        """
        if not self.convive_con_contribuyente:
            return 0
        age_at_year_end = self.age_at_year_end(filing_year)
        if age_at_year_end > MAX_AGE_MENOR_TRES:
            return 0
        if self.gastos_guarderia_mensuales:
            # Every declared month counts in both periods: under three the child
            # qualifies throughout, and in the turning-three period the birthday
            # draws no line.
            return sum(entry.amount_euros for entry in self.gastos_guarderia_mensuales)
        if age_at_year_end < MAX_AGE_MENOR_TRES:
            # An annual total needs no apportioning while the child is under
            # three for the whole period.
            return self.gastos_guarderia_euros
        return 0

    def guarderia_qualifying_meses(self, filing_year: int) -> int:
        """Art. 81.2 qualifying MONTH count for this descendant in *filing_year*.

        The proration basis for the increment's per-child cap, which the manual
        states "se calculará proporcionalmente al número de meses en que se
        cumplan de forma simultánea los requisitos exigidos en el artículo 81.1
        y 2" and works as ``1.000 / 12 x meses``. This method answers the 81.2
        half; the caller intersects it with the 81.1 half.

        The month SELECTION mirrors :meth:`guarderia_contributing_spend` exactly
        rather than being re-derived, and that is deliberate: the two answer the
        same question about the same months, one in euros and one in count, so a
        second derivation is how a spend month and a proration month come to
        disagree. Any change to the month rules belongs in both or in neither.

        An ANNUAL TOTAL carries no month information, so the count falls back to
        the months the child was AGE-ELIGIBLE — alive and under three within the
        period. That is an approximation and is the one place this method
        returns a number the operator did not evidence. It is chosen over the
        two alternatives on the grounds that it invents nothing: assuming twelve
        reinstates the flat cap this proration exists to remove, and refusing
        outright drops the increment entirely for what is likely the commonest
        declaration shape. The approximation is disclosed to the operator rather
        than presented as a measured result.

        It is the ANNUAL TOTAL that keeps it an approximation, and nothing else.
        The Art. 81.1 side now stores which months the mother qualified, so the
        simultaneity intersection is real wherever the nursery months are known;
        against an annual total there is nothing on THIS side to intersect with,
        and the caller falls back to a bound that cannot see the geometry at all.
        A mother qualifying January to June and one qualifying July to December
        produce the same figure against the same annual total, which is exactly
        the blindness the month sets removed everywhere the months are declared.
        Only the operator can close it, by declaring the monthly detail their
        centre already certified; :meth:`guarderia_needs_monthly_detail` exists
        to ask them for it.

        Returns ``0`` for a non-cohabiting descendant and for a child past the
        period they turn three, matching the spend method's own zeroes — and,
        in the turning-three period with only an annual total, the same zero the
        spend method returns, for the same upper-edge reason. The age-eligible
        fallback is NOT reached there: it counts months under three, which in
        that period is a strictly narrower window than the increment's own, so
        using it would prorate by a basis the spend it pairs with does not use.
        """
        if not self.convive_con_contribuyente:
            return 0
        age_at_year_end = self.age_at_year_end(filing_year)
        if age_at_year_end > MAX_AGE_MENOR_TRES:
            return 0
        if self.gastos_guarderia_mensuales:
            return len(self.gastos_guarderia_mensuales)
        if age_at_year_end < MAX_AGE_MENOR_TRES:
            return self.age_eligible_guarderia_meses(filing_year)
        return 0

    def guarderia_qualifying_months(self, filing_year: int) -> frozenset[int] | None:
        """WHICH months this descendant's declared nursery spend covers, or ``None``.

        The Art. 81.2 half of the simultaneity intersection, as months rather
        than as their number. ``None`` means the months are genuinely unknown —
        an ANNUAL total carries no month information at all — and is distinct
        from an empty set, which means no month qualifies.

        Callers that receive ``None`` cannot intersect and must fall back to the
        count, which is a bound rather than an answer. That bound is honest
        there precisely because nothing in the record says which months the
        yearly figure covered; it is not the count-based reading this method
        exists to replace, which discarded month information the record DID
        hold.
        """
        if not self.convive_con_contribuyente:
            return frozenset[int]()
        if self.age_at_year_end(filing_year) > MAX_AGE_MENOR_TRES:
            return frozenset[int]()
        if self.gastos_guarderia_mensuales:
            declared = frozenset(entry.month for entry in self.gastos_guarderia_mensuales)
            return declared & self._segundo_ciclo_window(filing_year)
        return None

    def _segundo_ciclo_window(self, filing_year: int) -> frozenset[int]:
        """Months the Art. 81.2 gastos may fall in, bounded by the second-cycle ceiling.

        Art. 81.2 admits the gastos "hasta el mes anterior a aquel en el que PUEDA
        comenzar el segundo ciclo de educación infantil", and that ceiling applies
        ONLY in the período impositivo in which the child turns three. Outside that
        period every month is open: the AEAT 2020 caso works a two-year-old's
        NON-CONTIGUOUS nursery months — January to June plus OCTOBER and NOVEMBER —
        to eight months, so a ceiling applied generally would drop two months the
        authority counts.

        The month is the OPERATOR's to declare and is never inferred. AEAT writes
        "pueda comenzar" in the subjunctive in every year of the manual: the
        authority itself declines to fix it, because when the cycle may begin
        depends on the child's own región and centre. September is the month its
        worked examples happen to use, and defaulting to it would be exactly the
        confident month-selection rule this box has already been wrong with once.

        Undeclared, this returns EMPTY rather than open: the turning-three window
        cannot be computed, so the increment declines to grant it and the operator
        is told what to supply
        (:meth:`guarderia_needs_segundo_ciclo_month`). Refusing under-grants, which
        over-taxes; opening would over-grant, which under-declares. Between two
        wrong answers the recoverable one is the one the operator can see and fix.
        """
        if self.age_at_year_end(filing_year) != MAX_AGE_MENOR_TRES:
            return frozenset(range(1, 13))
        if self.segundo_ciclo_infantil_inicio_mes is None:
            return frozenset[int]()
        return frozenset(range(1, self.segundo_ciclo_infantil_inicio_mes))

    def age_eligible_guarderia_meses(self, filing_year: int) -> int:
        """Months of *filing_year* in which this descendant was alive and under three.

        Computable from the birth date alone, which is why the Art. 81.2 side of
        the proration never needed a stored month set the way the Art. 81.1 side
        does. A child born within the period is eligible from their birth month
        inclusive; one born earlier and still under three at year-end is eligible
        for the whole twelve.

        TOTAL over every input rather than correct only where it happens to be
        called. The sole production caller —
        :meth:`guarderia_qualifying_meses`'s annual-total fallback — reaches it
        under an "under three at year-end" guard, and that guard places the
        third birthday after the period, so the under-three ceiling below is
        inert on that path and only the birth month moves the answer. Deriving
        the ceiling regardless keeps the result true of the method's NAME rather
        than of one call site's guard, so that guard can move without silently
        changing the number; the ceiling is exercised by direct tests rather
        than through the fallback.

        Public for the same reason: it is the basis
        :meth:`guarderia_qualifying_meses` approximates by when only an annual
        total is on record, and the operator is told that is what the count
        rests on, so it is separately addressable and separately tested rather
        than observable only through that one branch.

        The month the child turns three is EXCLUDED, because this counts
        UNDER-THREE months and that month is not one. That makes this window
        strictly NARROWER than the one :meth:`guarderia_contributing_spend`
        applies in the turning-three period, where the birthday draws no line at
        all and every declared month counts. The two coincide only where this
        method is actually consulted — a child under three for the whole period
        — which is precisely why the fallback is confined to that branch. Using
        it in the turning-three period would prorate by an under-three basis
        while the spend it pairs with was measured on a wider window.
        """
        if self.birth_date.year > filing_year:
            return 0
        first_month = self.birth_date.month if self.birth_date.year == filing_year else 1
        third_birthday_year = self.birth_date.year + 3
        if third_birthday_year < filing_year:
            return 0
        # In the year the child turns three they are under three only until the
        # birthday month, which is itself excluded. This is an AGE boundary, not
        # the increment's: ``guarderia_contributing_spend`` draws no line at the
        # birthday in that period.
        last_month = self.birth_date.month - 1 if third_birthday_year == filing_year else 12
        return max(0, last_month - first_month + 1)

    def guarderia_needs_monthly_detail(self, filing_year: int) -> bool:
        """True when only an annual total is on record for the turning-three period.

        The one state where declared spend contributes nothing purely because of
        its SHAPE. Reported so the operator is told to supply the monthly
        breakdown their centre certified, rather than left to wonder why a
        declared figure produced no increase.
        """
        if not self.convive_con_contribuyente:
            return False
        if self.age_at_year_end(filing_year) != MAX_AGE_MENOR_TRES:
            return False
        return self.gastos_guarderia_euros > 0 and not self.gastos_guarderia_mensuales

    def guarderia_needs_segundo_ciclo_month(self, filing_year: int) -> bool:
        """True when declared spend is withheld only for want of the second-cycle month.

        Fires on exactly the population the ceiling governs: a cohabiting child
        turning three in this período impositivo, with monthly nursery spend on
        record and no declared month for when the second cycle may begin. There
        the window is unknowable and the increment declines to grant it, so the
        operator must be told which fact unlocks it — their centre files the
        modelo 233 informative return, so the month is documented for them.

        Deliberately silent for a child not turning three (no ceiling applies at
        all) and for the annual-total shape, which
        :meth:`guarderia_needs_monthly_detail` already reports for a different
        reason. Two advisories on one filing for one cause is noise, and noise is
        what teaches operators to stop reading the channel.
        """
        if not self.convive_con_contribuyente:
            return False
        if self.age_at_year_end(filing_year) != MAX_AGE_MENOR_TRES:
            return False
        if not self.gastos_guarderia_mensuales:
            return False
        return self.segundo_ciclo_infantil_inicio_mes is None

    def is_eligible_guarderia(self, filing_year: int) -> bool:
        """True when this descendant may carry an Art. 81.2 guardería increase at all.

        Wider than :meth:`is_eligible_menor_tres`, which tests age under three at
        year end and is the Art. 81.1 maternidad population. The guardería
        increase additionally reaches the period the child TURNS three. Getting
        that boundary wrong costs a full birth cohort rather than a minority
        case, and the increase reduces cuota directly rather than the base, so
        the error lands on tax owed at full value.

        The authority is explicit that the increase is not gated on the
        maternidad deduction's own eligibility — where the child turns three in
        January, or the mother starts work after the birthday, the deduction does
        not apply and that does NOT prevent the increase. Hence a separate
        predicate rather than a widened shared one.
        """
        if not self.convive_con_contribuyente:
            return False
        return self.age_at_year_end(filing_year) <= MAX_AGE_MENOR_TRES

    def is_eligible_minimo_incremento_menor_tres(self, filing_year: int) -> bool:
        """True when Art. 58.2 grants the bajo-3-años increase for this descendant.

        Two independent limbs, and the second is why this is separate from
        :meth:`is_eligible_menor_tres` rather than shared with it:

        * the ordinary limb — under three at the devengo instant Art. 61
          norma 3ª fixes; and
        * the adopción/acogimiento limb, granted "con independencia de la edad
          del menor, en el período impositivo en que se inscriba en el Registro
          Civil y en los dos siguientes".

        The second limb is PERIOD-scoped: whole tax periods counted from the
        entry period, so annual granularity suffices and no month-level figure
        is required. Art. 81.1's adoption clause instead runs "durante los tres
        años siguientes a la FECHA de la inscripción" — date-scoped, a
        different shape. One predicate serving both would silently apply one
        statute's window to the other's deduction, which is why the two are
        resolved apart.

        The second limb reads ``relacion`` rather than the presence of a date,
        which is what makes the statute's three-way split expressible. Art. 58.1
        assimilates "tutela y acogimiento"; Art. 58.2 names "adopción o
        acogimiento, tanto preadoptivo como permanente". So a tutela guardian
        and a TEMPORAL acogimiento carer both take the ordinary tranches and
        neither takes this increase, while a preadoptivo or permanente carer
        takes both. Keying the limb on a date alone would grant it to whoever
        recorded one, which is the over-grant the relación axis exists to close.

        The anchor is :meth:`art_58_2_entry_date` — the FIRST entitling event —
        so the three periods cap a fostered-then-adopted child's window rather
        than restarting on the adoption.
        """
        if not self.convive_con_contribuyente:
            return False
        if self.age_at_year_end(filing_year) < MAX_AGE_MENOR_TRES:
            return True
        entry_date = self.art_58_2_entry_date()
        if entry_date is None:
            return False
        periods_since_entry = filing_year - entry_date.year
        return 0 <= periods_since_entry <= NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS
