"""Family-level Modelo 100 aggregation and proration behaviors."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import cast

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import CUSTODIA_COMPARTIDA_PRORRATA_FACTOR
from ._constants import SUPPORTED_PROFILE_SCHEMA_VERSION, ProfileSchemaVersion
from ._descendant import DescendantInfo
from ._family_types import (
    MAX_AGE_MENOR_TRES,
    MinimoDescendientesThresholds,
    RentaAscendantProfile,
    RentaDescendantProfile,
)
from .errors import ProfileValidationError


def _survivor_rank_by_position(eligible: Sequence[DescendantInfo], filing_year: int) -> dict[int, int]:
    """Rank the surviving descendants, vacating the rank of each who died before devengo.

    Art. 61 norma 4ª limb two: the ordering that assigns "primero, segundo,
    tercero…" is computed over the survivors ALONE. A descendant who died before
    the devengo still contributes their flat cuantía (limb one) but vacates their
    rank, which is what moves each younger sibling down a tranche. Omitting this
    limb over-grants the survivors as well as the deceased.

    Keyed by POSITION rather than by the record itself: DescendantInfo is a frozen
    pydantic model, so two identically-declared siblings — twins with the same
    birth date and no distinguishing fact — compare equal, and a value-keyed
    lookup would give them both the elder's rank.
    """
    return {
        position: rank
        for rank, position in enumerate(
            position for position, d in enumerate(eligible) if not d.died_before_devengo(filing_year)
        )
    }


class RentaFamilyProfile(BaseModel):
    """Typed repeated family-member facts consumed by Modelo 100 bindings."""

    model_config = _STRICT_FROZEN

    schema_version: ProfileSchemaVersion = Field(default=SUPPORTED_PROFILE_SCHEMA_VERSION)
    descendants: tuple[RentaDescendantProfile, ...] = ()
    ascendants: tuple[RentaAscendantProfile, ...] = ()
    descendientes: tuple[DescendantInfo, ...] = ()
    anualidades_alimentos_euros: Decimal | None = Field(default=None, ge=Decimal("0"))
    """Judicial anualidades por alimentos the filer PAYS, or ``None`` if undeclared.

    Filer-level rather than per-descendant, and that is the staged boundary
    rather than the intended end state. Art. 58 carves the dependency
    assimilation out where anualidades are satisfied, and the carve-out is
    per-child in the law; this profile cannot attribute a payment to one
    descendant, so a declared amount suppresses the assimilation for EVERY
    descendant until that attribution lands.

    Suppressing them all is the under-granting direction, which is the safe one
    to default to, but it is a real narrowing: a filer paying anualidades for one
    child and supporting another outside any court order loses the second child's
    assimilation too. The calculate path discloses that rather than leaving it
    silent.

    A declared ``0`` is an answer meaning none are paid and does NOT suppress;
    only a positive amount does. ``None`` means the question was never put.
    """
    cotizaciones_ss_madre_2024: int = Field(default=0, ge=0)
    """SS cotizaciones paid by the mother during 2024 (mirrors casilla 0013).

    The statutory ceiling on the Art. 81.2 guardería incremento, applied to the
    household total after the per-child proration
    (:meth:`RentaFamilyProfile.incremento_guarderia_0613` computes each child's
    own ``min(cap_anual / 12 × meses, su gasto)`` and sums them; this figure caps
    that sum). The annual cap is a registry ``money`` parameter resolved by the
    caller, never a literal here (`aeat-registry-authority-flow`).

    Default ``0`` (cap not declared; guardería incremento will be zero).
    """
    """Structured per-descendant data for Art. 58 mínimo calculation.

    Each entry carries birth / adoption date, discapacidad grade, and
    cohabitation flag.  The ``descendants`` tuple above models the
    official Modelo 100 form rows; this tuple drives the mínimo engine.
    """

    @field_validator("descendants", "ascendants", mode="before")
    @classmethod
    def _tuple_from_list(cls, value: object) -> object:
        if isinstance(value, list):
            # CAST-RATIONALE-DESCENDANTS-ASCENDANTS-COERCION: isinstance narrows
            # to list but not its element type; pydantic re-validates each
            # element against the field's declared item type after this
            # coercion.
            # nosemgrep: no-cast-in-domain-application
            return tuple(cast("list[object]", value))
        return value

    @field_validator("descendientes", mode="before")
    @classmethod
    def _descendientes_from_list(cls, value: object) -> object:
        if isinstance(value, list):
            # CAST-RATIONALE-DESCENDIENTES-COERCION: isinstance narrows to list
            # but not its element type; pydantic re-validates each element
            # against the field's declared item type after this coercion.
            # nosemgrep: no-cast-in-domain-application
            return tuple(cast("list[object]", value))
        return value

    # ------------------------------------------------------------------
    # Derived properties for Art. 58 mínimo-por-descendientes
    # ------------------------------------------------------------------

    @property
    def descendientes_count(self) -> int:
        """Total number of DescendantInfo entries."""
        return len(self.descendientes)

    @property
    def dependencia_assimilation_available(self) -> bool:
        """Whether the dependency assimilation may apply to ANY descendant this year.

        False as soon as the filer declares a positive anualidades figure. Art.
        58 carves the assimilation out where anualidades are satisfied, and
        because this profile cannot yet attribute a payment to a particular
        descendant the carve-out is applied to all of them.

        The narrowing is deliberate and one-directional: it withholds an
        allowance some filers are owed rather than granting one they are not.
        Reversing it needs per-child attribution, not a looser reading here.
        """
        return not (self.anualidades_alimentos_euros is not None and self.anualidades_alimentos_euros > 0)

    def dependencia_assimilated_indices(self, filing_year: int) -> tuple[int, ...]:
        """Indices of descendants reaching the mínimo ONLY through the dependency limb.

        The disclosure surface for a judgement the operator most needs to see:
        the allowance is being granted to a non-cohabiting filer on a declared
        economic-dependency fact, which is an assertion rather than an
        observation. Empty when the assimilation is unavailable or nothing
        relies on it.

        Applies the NON-INCOME conditions only, for the same reason
        :meth:`DescendantInfo.meets_non_income_conditions` exists: the caller is
        a calculate-path advisory that cannot resolve the registry ceilings.
        The narrowing is safe in this direction - a descendant excluded by a
        ceiling contributes nothing either way, so the worst case is one extra
        disclosure rather than a missing one.
        """
        available = self.dependencia_assimilation_available
        return tuple(
            index
            for index, descendant in enumerate(self.descendientes)
            if descendant.assimilated_by_dependencia(dependencia_assimilation_available=available)
            and descendant.meets_non_income_conditions(
                filing_year,
                dependencia_assimilation_available=available,
            )
        )

    def dependencia_suppressed_indices(self) -> tuple[int, ...]:
        """Indices whose declared dependency is suppressed by the anualidades carve-out.

        These descendants would be assimilated but for the filer's declared
        anualidades, which this model cannot yet attribute per child. Reported
        so the narrowing is visible to the filer it costs rather than silently
        withheld.
        """
        if self.dependencia_assimilation_available:
            return ()
        return tuple(
            index
            for index, descendant in enumerate(self.descendientes)
            if descendant.dependencia_economica is True and not descendant.convive_con_contribuyente
        )

    def descendientes_menores_3_year_end(self, filing_year: int) -> int:
        """Count of eligible descendientes whose age at year-end < 3 (Art. 58.2)."""
        return sum(1 for d in self.descendientes if d.is_eligible_menor_tres(filing_year))

    def descendientes_guarderia_count(self, filing_year: int) -> int:
        """Count of descendants who may carry an Art. 81.2 guardería increase.

        Wider than the Art. 58.2 menor-de-tres count by exactly the turning-three
        period. Kept separate rather than widening that count, which has its own
        registry binding and its own statutory meaning for the supplement.
        """
        return sum(1 for d in self.descendientes if d.is_eligible_guarderia(filing_year))

    def gastos_guarderia_reales(self, filing_year: int) -> int:
        """Sum of the Art. 81.2 guardería spend every descendant contributes in *filing_year*.

        Sums :meth:`DescendantInfo.guarderia_contributing_spend`, which applies
        the Art. 81.2 month rules per child: every declared month while the child
        is under three, and only the post-birthday months in the period the child
        turns three. The turning-three period is INCLUDED here and was not
        before, which is the campaign's largest measured under-grant — a full
        birth cohort rather than a minority case, reducing cuota directly.

        Year-parameterised rather than pinned to 2024 because the calculate path
        derives ``renta_family.gastos_guarderia_reales_{filing_year}`` for
        whatever year the registry declares a consumer for. A 2024-only accessor
        would have forced that path to keep its own parallel sum, which is how
        the monthly map could be declared and contribute nothing.
        """
        return sum(d.guarderia_contributing_spend(filing_year) for d in self.descendientes)

    def incremento_guarderia_0613(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
        cap_anual: Decimal,
    ) -> Decimal:
        """Art. 81.2 guardería increment (casilla 0613), prorated and capped PER CHILD.

        The manual states the increment "puede alcanzar hasta 1.000 euros
        anuales y se calculará proporcionalmente al número de meses en que se
        cumplan de forma simultánea los requisitos exigidos en el artículo 81.1
        y 2", and works it as ``1.000 / 12 x meses``. It then states the result
        as that child's own limit — "Límite del incremento: 166,67 euros" — so
        the cap is per child rather than a household total.

        Each child contributes ``min(cap_anual / 12 x meses, su gasto)`` and the
        contributions are SUMMED. The per-child bound is the load-bearing part:
        an aggregate ``min`` over the household lets one child's unused cap
        absorb another child's excess spend, and it is also what let the missing
        proration hide, because filtering one term of a household-wide ``min``
        reads as completing the month rules.

        *meses* is the SIMULTANEITY intersection the manual describes, taken as
        the smaller of the two sides. The Art. 81.1 side is
        :meth:`DescendantInfo.guarderia_art_81_1_meses` rather than the
        deducción's own :meth:`DescendantInfo.maternidad_contributing_meses`,
        and the distinction is load-bearing: the deducción stops at the child's
        third birthday while the increment does not, so reusing it forced this
        total to zero for a child turning three in January and for a mother who
        began work after the birthday — two cases Capítulo 18 names explicitly
        as still qualifying.

        BOTH sides are real month sets, so *meses* is a true intersection rather
        than a bound. That is what the article asks for — "el número de meses en
        que se cumplan de forma simultánea los requisitos" is a question about
        WHICH months, and only months can answer it.

        The manual's caso a is the case that forced it: a mother entitled May to
        August against nursery paid January to June shares exactly two months,
        and AEAT prints ``1.000 ÷ 12 × 2 = 166,67``. Taking ``min`` over the two
        COUNTS yields four and 333,33 — an over-grant of the deducción, which
        under-declares tax. Counts cannot distinguish that case from a
        containment or a disjoint one, because the sizes are the same in all
        three; the geometry only survives if the months do.

        Preferred to a flat per-child cap, which over-grants every mid-year
        birth and every partial-year enrolment outright.

        *cap_anual* is a registry ``money`` parameter the caller resolves per
        filing year; this method performs no euro-figure lookup of its own
        (`aeat-registry-authority-flow`).

        Returns ``Decimal("0")`` when no descendant qualifies, which is the
        legally correct zero rather than an under-declaration.
        """
        from ...core.money import round_to_cents

        available = self.dependencia_assimilation_available
        total = Decimal("0")
        for descendant in self.descendientes:
            meses = descendant.guarderia_simultaneous_meses(
                filing_year,
                thresholds=thresholds,
                dependencia_assimilation_available=available,
            )
            if meses <= 0:
                continue
            prorated_cap = round_to_cents(cap_anual / Decimal(12) * Decimal(meses))
            spend = Decimal(descendant.guarderia_contributing_spend(filing_year))
            total += min(prorated_cap, spend)
        return total

    def meses_maternidad_por_descendiente(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
    ) -> tuple[tuple[str, int], ...]:
        """The Art. 81.1 ``(hijo_id, meses)`` pairs this profile contributes in *filing_year*.

        Pairs :meth:`DescendantInfo.maternidad_contributing_meses` with the
        descendant's index, which is the identifier every other descendiente
        surface addresses a child by — the ``list`` renderer, the ``remove``
        verb, and the fact paths themselves. The deducción's own per-hijo cap
        then applies over these pairs rather than over a collapsed total, so a
        second child can never absorb a first child's unused months.

        Aggregates through the canonical record rather than summing the stored
        facts directly. The guardería path was broken for exactly one release by
        a second loop that read the raw fact under its own inline age test: the
        two diverged the moment the record learned a month rule, and a taxpayer
        could declare spend, see it stored, and receive nothing. One aggregation
        path per value is the lesson, and this is that path for Art. 81.1.

        Reads :attr:`dependencia_assimilation_available` off this profile rather
        than taking it as an argument, exactly as
        :meth:`descendientes_eligible_minimum` does, so the anualidades
        carve-out cannot be applied to the mínimo and skipped for the deducción
        that keys on it.

        Omits descendants contributing zero months, so an ineligible child and
        one whose mother declared no employment months are both simply absent
        rather than carrying a zero pair into the deducción.
        """
        available = self.dependencia_assimilation_available
        return tuple(
            (str(index), meses)
            for index, descendant in enumerate(self.descendientes)
            if (
                meses := descendant.maternidad_contributing_meses(
                    filing_year,
                    thresholds=thresholds,
                    dependencia_assimilation_available=available,
                )
            )
            > 0
        )

    def guarderia_needs_monthly_detail_indices(self, filing_year: int) -> tuple[int, ...]:
        """Indices whose declared spend contributes nothing only because of its shape."""
        return tuple(
            index
            for index, descendant in enumerate(self.descendientes)
            if descendant.guarderia_needs_monthly_detail(filing_year)
        )

    def guarderia_needs_segundo_ciclo_month_indices(self, filing_year: int) -> tuple[int, ...]:
        """Indices whose turning-three window is withheld for want of a declared month."""
        return tuple(
            index
            for index, descendant in enumerate(self.descendientes)
            if descendant.guarderia_needs_segundo_ciclo_month(filing_year)
        )

    def guarderia_cotizaciones_ceiling_is_unbounded(self, filing_year: int) -> bool:
        """True when the cotizaciones ceiling is NOT limited to the second-cycle window.

        The SECOND consumer of the second-cycle month, and the one this application
        does not compute. Art. 81 bounds it in the same período: "las cotizaciones a
        la Seguridad Social a computar serán las devengadas hasta el mes anterior a
        aquel en el que el hijo pueda iniciar el segundo ciclo".

        DELIBERATELY DISCLOSED RATHER THAN COMPUTED, for two reasons that survive
        each other. First, :attr:`cotizaciones_ss_madre_2024` is an ANNUAL scalar
        with no month axis, so limiting it would mean apportioning a yearly figure
        the operator supplied whole — inventing a number in the population this rule
        governs. Second and decisively, that figure is a HOUSEHOLD term while the
        ceiling is PER CHILD: a household with one child turning three and one
        younger has no single bounding month, and AEAT states no apportionment rule
        for that case. The second reason survives giving the field a month axis,
        which is why the axis is not the fix.

        So the operator is told the figure they supply must already be the bounded
        one. Do not wire this to the declared month without first settling the
        household-versus-per-child question; the registry formula's own comment
        records the same boundary being met and left alone on purpose.

        Fires only where it can change an outcome: a child turning three, spend on
        record, and a cotizaciones figure actually declared — with none declared the
        ceiling binds at zero and the increment is already nil for a reason the
        operator can see.
        """
        if self.cotizaciones_ss_madre_2024 <= 0:
            return False
        return any(
            descendant.convive_con_contribuyente
            and descendant.age_at_year_end(filing_year) == MAX_AGE_MENOR_TRES
            and bool(descendant.gastos_guarderia_mensuales)
            for descendant in self.descendientes
        )

    def descendientes_eligible_minimum(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
    ) -> int:
        """Count of descendientes eligible for the ordinary Art. 58.1 mínimo.

        A descendant is eligible when cohabiting, under 25 at year-end or
        carrying any discapacidad, within the Art. 58.1 rentas ceiling, and not
        excluded by Art. 61 norma 2ª — see
        :meth:`DescendantInfo.is_eligible_ordinary`.
        """
        available = self.dependencia_assimilation_available
        return sum(
            1
            for d in self.descendientes
            if d.is_eligible_ordinary(
                filing_year,
                thresholds=thresholds,
                dependencia_assimilation_available=available,
            )
        )

    def custodia_compartida_count(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
    ) -> int:
        """Count of eligible descendientes with custodia_compartida=True.

        Only eligible (Art. 58.1) descendants are counted; non-eligible ones
        carry no mínimo, so the prorrata has no effect. This counts the
        judicially-shared-custody trigger specifically, NOT every descendant
        whose mínimo ends up prorated under Art. 61 norma 1ª — an explicit
        ``prorrata_minimo`` answer or a derived second entitled filer prorates
        without shared custody.
        """
        return sum(
            1
            for d in self.descendientes
            if d.custodia_compartida
            and d.is_eligible_ordinary(
                filing_year,
                thresholds=thresholds,
                dependencia_assimilation_available=self.dependencia_assimilation_available,
            )
        )

    def minimo_prorrata_factor(
        self,
        descendant: DescendantInfo,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
        second_filer_indicated: bool = False,
    ) -> Decimal:
        """Return the Art. 61 norma 1ª prorrata factor for one descendant.

        Norma 1ª keys proration to ENTITLEMENT, not to custody: "Cuando dos o
        más contribuyentes tengan derecho a la aplicación del mínimo por
        descendientes ... respecto de los mismos ... descendientes, su importe
        se prorrateará entre ellos por partes iguales." Shared custody is one
        way two contribuyentes come to be entitled, not the rule itself, so it
        remains a trigger rather than the test.

        Precedence, highest first:

        1. ``descendant.prorrata_minimo`` — an explicit operator answer always
           wins, in both directions.
        2. ``descendant.custodia_compartida`` — the judicially shared-custody
           case, preserved as a trigger.
        3. *second_filer_indicated* — the caller's derivation from profile
           signals, used only when nothing above answered the question.

        Returns :data:`CUSTODIA_COMPARTIDA_PRORRATA_FACTOR` (``0.5``) when the
        descendant is mínimo-eligible and any of the above indicates a second
        entitled contribuyente, otherwise ``Decimal("1")``. A non-eligible
        descendant always returns ``Decimal("1")`` because there is no mínimo
        to prorate.
        """
        if not descendant.is_eligible_ordinary(
            filing_year,
            thresholds=thresholds,
            dependencia_assimilation_available=self.dependencia_assimilation_available,
        ):
            return Decimal("1")
        if descendant.prorrata_minimo is not None:
            return CUSTODIA_COMPARTIDA_PRORRATA_FACTOR if descendant.prorrata_minimo else Decimal("1")
        if descendant.custodia_compartida or second_filer_indicated:
            return CUSTODIA_COMPARTIDA_PRORRATA_FACTOR
        return Decimal("1")

    def minimo_descendientes_estatal(
        self,
        filing_year: int,
        *,
        birth_order_amounts: Sequence[Decimal],
        menor_tres_supplement: Decimal,
        fallecimiento_amount: Decimal,
        thresholds: MinimoDescendientesThresholds,
        second_filer_indicated: bool = False,
    ) -> Decimal:
        """Compute the Art. 58 mínimo por descendientes aggregate (casillas 0513/0514).

        Ranks every Art. 58.1-eligible descendant (age < 25 at year-end, or any
        discapacidad grade, and cohabiting) by ``birth_date`` ascending — the
        eldest eligible descendant is "el primero", matching the AEAT Renta
        manual's birth-order reading of Art. 58.1's "primero/segundo/tercero/
        cuarto y siguientes" tranches. Each eligible descendant contributes:

        * the birth-order tranche amount from *birth_order_amounts* (index 0
          for the 1st, index 1 for the 2nd, ... the last entry repeats for the
          4th and every subsequent descendant, per Art. 58.1's "cuarto y
          siguientes" wording);
        * plus *menor_tres_supplement* when the descendant is also
          Art. 58.2-eligible (age < 3 at year-end);
        * the sum is then multiplied by the descendant's Art. 61 norma 1ª
          prorrata factor (:meth:`minimo_prorrata_factor`), which is 0.5
          whenever a second contribuyente is also entitled to this
          descendant's mínimo — by explicit answer, by shared custody, or by
          the caller's *second_filer_indicated* derivation.

        No within-year temporal prorrateo is applied: Art. 58 (in force since
        01/01/2015, BOE-A-2014-12327) declares only the two numbered
        subsections above and no birth/adoption-date cutoff for descendientes.

        Art. 61 norma 4ª governs this aggregate rather than sitting outside it,
        and BOTH its limbs are applied here. The rule is easy to half-implement
        because its flat figure coincides with the first-child tranche, so a
        partial fix looks complete while leaving most of the over-grant standing.

        LIMB ONE, the flat cuantía. A descendant who dies in the period takes a
        FLAT amount rather than their birth-order tranche — "en caso de
        fallecimiento de un descendiente que genere derecho al mínimo por este
        concepto, la cuantía aplicable es de 2.400 euros". That figure equals
        the first-child tranche in every revision served today, so the
        substitution is worth nothing for a first child and 300 € to 2.100 € for
        a later one. It is supplied as *fallecimiento_amount*, its own registry
        parameter, and is deliberately not read off ``birth_order_amounts[0]``:
        the two are legally distinct figures that merely coincide.

        LIMB TWO, the ordering exclusion, is the one that is invisible on
        inspection. The deceased is dropped from the age ordering that ranks the
        survivors — "sin computar a estos efectos aquellos descendientes que …
        hubieran fallecido en el ejercicio con anterioridad a la fecha de devengo
        del impuesto". Because the tranches ascend with rank, dropping the
        deceased moves every younger sibling to a CHEAPER rank, so omitting this
        limb over-grants the survivors as well as the deceased. A fix carrying
        only limb one would pass any test that checks the deceased's own amount.

        The two limbs read ``death_date`` through different predicates and the
        difference is deliberate: :meth:`~DescendantInfo.died_in_period` for the
        cuantía, :meth:`~DescendantInfo.died_before_devengo` for the ordering.
        See the ``death_date`` field documentation for why they are not one
        condition.

        The Art. 58.2 menor-3 supplement is added on top of the flat cuantía,
        not replaced by it: the AEAT manual states the increase "resulta
        aplicable en los casos en que el descendiente haya fallecido durante el
        período impositivo". Replacing it would under-grant a bereaved filer.

        A descendant who died in a PRIOR year contributes nothing at all — they
        fail :meth:`~DescendantInfo.meets_non_income_conditions` and never reach
        the ranking.

        *birth_order_amounts*, *menor_tres_supplement*, *fallecimiento_amount*
        and *thresholds* are registry ``money`` parameters the caller resolves
        per filing year; this domain method performs no euro-figure lookup of
        its own (`aeat-registry-authority-flow`).

        Returns ``Decimal("0")`` when no descendant is Art. 58.1-eligible
        (including an empty ``descendientes`` tuple) — the legally correct
        zero for a childless filer, not an under-declaration. A descendant
        excluded by the rentas ceiling or the norma 2ª own-return rule
        contributes exactly zero, including its menor-3 supplement, because it
        never enters the birth-order ranking at all.
        """
        eligible = sorted(
            (
                d
                for d in self.descendientes
                if d.is_eligible_ordinary(
                    filing_year,
                    thresholds=thresholds,
                    dependencia_assimilation_available=self.dependencia_assimilation_available,
                )
            ),
            key=lambda d: d.birth_date,
        )
        if not eligible:
            return Decimal("0")
        if not birth_order_amounts:
            raise ProfileValidationError("birth_order_amounts must not be empty")
        rank_by_position = _survivor_rank_by_position(eligible, filing_year)
        total = Decimal("0")
        for position, descendant in enumerate(eligible):
            if descendant.died_in_period(filing_year):
                # Limb one: the flat cuantía displaces the tranche at any rank.
                amount = fallecimiento_amount
            else:
                ordinal = rank_by_position[position]
                tranche_index = min(ordinal, len(birth_order_amounts) - 1)
                amount = birth_order_amounts[tranche_index]
            if descendant.is_eligible_minimo_incremento_menor_tres(filing_year):
                amount += menor_tres_supplement
            total += amount * self.minimo_prorrata_factor(
                descendant,
                filing_year,
                thresholds=thresholds,
                second_filer_indicated=second_filer_indicated,
            )
        return total

    def custodia_compartida_advisory(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
    ) -> str | None:
        """Return the translated Art. 61 prorrata advisory string, or ``None``.

        Scoped to the judicially-shared-custody trigger only. A mínimo prorated
        because a second entitled filer was DERIVED from profile signals is
        surfaced separately on the calculate path, because that inference is
        the one the operator most needs to confirm.
        """
        from ...core.i18n import tr

        count = self.custodia_compartida_count(filing_year, thresholds=thresholds)
        if count > 0:
            return tr(
                "profile.descendiente.custodia_compartida_prorrata_applied",
                count=count,
            )
        return None

    # ------------------------------------------------------------------
    # Comunidad de Madrid "Por nacimiento o adopción de hijos" deducción
    # autonómica (DL 1/2010 arts. 4 y 18.1) — casilla 1039 framework primitives
    # ------------------------------------------------------------------

    def madrid_nacimiento_adopcion_eligible_count(self, filing_year: int) -> int:
        """Count of descendants inside the Madrid nacimiento/adopción window who cohabit.

        The raw (unweighted) eligible count; ``madrid_nacimiento_adopcion_weighted_count``
        applies the per-descendant prorrateo the registry cuantía is multiplied by.
        """
        return sum(1 for d in self.descendientes if d.is_nacimiento_adopcion_eligible(filing_year))

    def madrid_nacimiento_adopcion_weighted_count(self, filing_year: int) -> Decimal:
        """Prorrateo-weighted eligible-descendant count for the Madrid deducción.

        Each eligible descendant contributes its prorrateo share (``1``, or
        ``0.5`` under custodia compartida). The registry formula multiplies this
        weighted count by the per-child cuantía (721,70 € for 2023+ entries), so
        the per-descendant prorrateo the registry schema cannot express is
        computed here in Python and passed to the registry as a resolved value.
        """
        total = Decimal("0")
        for descendant in self.descendientes:
            if descendant.is_nacimiento_adopcion_eligible(filing_year):
                total += descendant.nacimiento_adopcion_prorrateo_share()
        return total

    def unidad_familiar_otros_miembros_base(self) -> Decimal:
        """Base imponible of unidad-familiar members OTHER than the filer.

        Framework primitive for the autonomic double income-limit gate (the
        unidad-familiar 61.860 € límite). For a monoparental/single filer the
        other members are the filer's cohabiting children, whose own base
        imponible the profile does not hold and is treated as zero; the filer's
        own base (casillas 0435 + 0460) is added by the registry formula. A
        conyugal unit's spouse base is not persisted, so the derived-fact
        injector supplies this term only for the determinable single-filer case
        and the trigger stays advisory-only otherwise (fail-closed, no
        over-claim).
        """
        return Decimal("0")
