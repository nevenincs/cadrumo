"""Typed personal/family profile records for Modelo 100 inputs.

The records in this module describe factual people and family-unit flags.
They do not decide Modelo 100 legal treatment, minimum amounts, deduction
eligibility, or casilla formulas; those remain registry-owned.

:class:`DescendantInfo`, :class:`RentaDescendantProfile`, and
:class:`RentaAscendantProfile` feed :class:`RentaFamilyProfile`, whose helper
methods derive Art. 58 minimum counts and Art. 81 maternity/guardería amounts
from the factual profile records.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import ART_58_2_ENTITLING_RELACIONES, ART_81_1_MATERNIDAD_RELACIONES, DescendantRelacion
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import (
    ART_81_1_ENTRY_WINDOW_YEARS,
    CUSTODIA_COMPARTIDA_PRORRATA_FACTOR,
    DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR,
    MINIMO_DESCENDIENTE_MAX_AGE,
    MINIMO_MENOR_TRES_MAX_AGE,
    NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS,
)
from ...core.parsing import parse_iso8601_date
from ...core.time import today_madrid
from ._errors import ProfileValidationError

# Comunidad de Madrid "Por nacimiento o adopción de hijos" deducción autonómica
# (DL 1/2010, de 21 octubre, arts. 4 y 18.1). Ámbito temporal: the deducción
# applies in the period of nacimiento/adopción AND in each of the two following
# periods. The figure itself lives beside its Art. 58 / Art. 61 siblings in the
# curated external-constants layer; the alias keeps internal call sites stable.
_NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS = NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS


def within_multi_year_applicability_window(
    entry_year: int,
    filing_year: int,
    *,
    following_periods: int,
) -> bool:
    """Return whether *filing_year* is inside a multi-year applicability window.

    A reusable primitive for autonomic deducciones that apply in the period of
    a triggering event (a nacimiento, an adopción, a rehabilitación, ...) plus a
    fixed number of following periods. The window is the closed interval
    ``[entry_year, entry_year + following_periods]``; ``following_periods = 0``
    yields a single-year window.

    Args:
        entry_year: Calendar year of the triggering event.
        filing_year: The filing year whose eligibility is being tested.
        following_periods: Count of periods after ``entry_year`` in which the
            deducción remains applicable. Must be non-negative.
    """
    if following_periods < 0:
        raise ProfileValidationError("following_periods must be non-negative")
    return entry_year <= filing_year <= entry_year + following_periods


# Art. 58 thresholds sourced from the central authority: age < 25 (exclusive)
# for ordinary mínimo eligibility, age < 3 (exclusive) for the bajo-3-años
# supplement. The module-private aliases keep the internal call sites stable.
_MAX_AGE_ORDINARY = MINIMO_DESCENDIENTE_MAX_AGE
_MAX_AGE_MENOR_TRES = MINIMO_MENOR_TRES_MAX_AGE

# Art. 81.1 LIRPF: the adopción/acogimiento limb runs "durante los tres años
# siguientes a la fecha de la inscripción en el Registro Civil". Counted in
# YEARS from a date, unlike the Art. 58.2 limb above, which counts whole tax
# PERIODS from the entry period — hence a separate constant rather than a reuse
# of the period count, which would read as the same rule and is not.
_ART_81_1_ENTRY_WINDOW_YEARS = ART_81_1_ENTRY_WINDOW_YEARS


def _months_of_year_between(
    start: tuple[int, int],
    end: tuple[int, int],
    filing_year: int,
) -> frozenset[int]:
    """Months of *filing_year* inside the half-open ``(year, month)`` span ``[start, end)``.

    Compares ``(year, month)`` pairs rather than dates so a span anchored on a 29
    February event resolves in a non-leap year, where constructing the
    anniversary date raises. Half-open by design: both Art. 81.1 windows count
    their opening month in full and exclude the month the span runs out.
    """
    return frozenset(month for month in range(1, 13) if start <= (filing_year, month) < end)


def _coerce_iso_date_field(value: object) -> object:
    """Delegate for @field_validator date fields: parse ISO strings, pass through everything else."""
    if isinstance(value, str):
        return parse_iso8601_date(value)
    return value


class MinimoDescendientesThresholds(BaseModel):
    """The two Art. 58.1 / Art. 61 norma 2ª eligibility figures, per filing year.

    Both are registry ``money`` parameters the caller resolves for the filing
    year being computed; this domain layer performs no euro-figure lookup of
    its own (`aeat-registry-authority-flow`). Carrying them as one required
    argument rather than two optional ones is deliberate: an optional threshold
    would let a caller silently skip half the law and inflate the mínimo, which
    is the exact defect this record exists to close.

    Fields
    ------
    rentas_anuales_limite
        Art. 58.1 LIRPF ceiling on the descendant's own annual rentas excluding
        exempt income. Registry parameter
        ``renta-{year}-minimo-descendientes-rentas-anuales-limite-{year}``.
    declaracion_propia_rentas_limite
        Art. 61 norma 2ª LIRPF ceiling on the rentas in a descendant's OWN
        return. Registry parameter
        ``renta-{year}-minimo-descendientes-declaracion-propia-rentas-limite-{year}``.
    """

    model_config = _STRICT_FROZEN

    rentas_anuales_limite: Decimal = Field(ge=Decimal("0"))
    declaracion_propia_rentas_limite: Decimal = Field(ge=Decimal("0"))


class GuarderiaMonthSpend(BaseModel):
    """One month's guardería spend for one descendant (Art. 81.2 LIRPF).

    Month-granular because the statute is: the increase runs while the child is
    under three and, in the period the child TURNS three, extends to the spend
    "incurridos con posterioridad al cumplimiento de dicha edad" up to the month
    before the second cycle of infant education may begin. An annual total
    cannot express either boundary.

    The map these build is SPARSE by construction — a month with no spend simply
    has no entry — so nothing here encodes a window. That is deliberate and is
    the whole reason the shape is monthly primaries rather than a pre-split
    figure: every split shape would bake a boundary into stored data, and the
    upper boundary is not this application's to determine.
    """

    model_config = _STRICT_FROZEN

    month: int = Field(ge=1, le=12)
    amount_euros: int = Field(ge=0)


class DescendantInfo(BaseModel):
    """Structured per-descendant data for Art. 58 mínimo-por-descendientes.

    This record drives the mínimo-por-descendientes calculation (casilla 0513)
    and the bajo-3-años supplement (Art. 58.2).  It is intentionally richer
    than :class:`RentaDescendantProfile`, which models official-form rows.

    Fields
    ------
    birth_date
        Required date of birth.
    relacion
        The legal relationship linking this descendant to the contribuyente
        (:class:`~cadrumo.core.DescendantRelacion`). Defaults to
        :attr:`~cadrumo.core.DescendantRelacion.DESCENDIENTE`, so an absent
        fact means an ordinary descendant. Art. 58.1 assimilates tutela and
        acogimiento for the tranches while Art. 58.2 names only "adopción o
        acogimiento, tanto preadoptivo como permanente" for the increase, so
        the two clauses need this distinction drawn rather than inferred.
    inscripcion_registro_civil_date
        The Art. 58.2 entry event for an ADOPTION: the date the adoption was
        inscribed in the Registro Civil, or — where inscription is not
        required — the date of the resolución judicial o administrativa. One
        anchor with two legal sources, not two meanings, which is why it is one
        field. Permitted only on an
        :attr:`~cadrumo.core.DescendantRelacion.ADOPTADO` record.

        The date is the INSCRIPTION in the Registro Civil, which is what Art.
        58.2 counts from — not the adoption's *finalisation*. The two can fall
        in different periods, so the distinction is load-bearing rather than
        terminological.
    acogimiento_resolucion_date
        The Art. 58.2 entry event for an acogimiento: the date of the FIRST
        ENTITLING resolución — preadoptivo or permanente, the two shapes the
        statute names. Permitted on those records and on an ``ADOPTADO``
        record, because Art. 58.2's three periods are a CAP measured from the
        first entitling event rather than a count the later adoption restarts:
        a fostered-then-adopted child holds both dates and gets three periods
        in total, not six. A temporal placement is not entitling and therefore
        has no truthful value for this field.
    discapacidad_grado
        0 = sin discapacidad, 33 = grado ≥ 33 % < 65 %, 65 = grado ≥ 65 %.
        A disabled descendant remains mínimo-eligible regardless of age.
    convive_con_contribuyente
        Whether the descendant cohabits with the taxpayer (Art. 58.1 condition).
        Stays a FACT about the household and is never overloaded to carry the
        dependency case; the two are separate fields precisely so a filer who
        does not cohabit is not forced to misstate cohabitation to reach the
        allowance they are entitled to.
    dependencia_economica
        Whether the taxpayer contributes to this descendant's economic upkeep
        without cohabiting. ``None`` (the default) means UNSET, which never
        assimilates; only an explicit ``True`` does, and only when the filer
        declares no judicial anualidades. The authority states the entitled
        case in terms — a progenitor with no custody, not even shared, paying
        no anualidades, who nonetheless contributes economically. ``False`` is
        a real answer distinct from unset: it records that the question was put
        and declined.
    custodia_compartida
        Art. 61 LIRPF: when ``True``, both progenitors share custody under a
        judicial or administrative arrangement. The mínimo-por-descendientes
        and the bajo-3-años supplement for this child are split 50 % between
        them (Art. 61 prorrata). Default ``False`` (sole custody / not
        applicable). Setting this flag on a non-cohabiting descendant has no
        additional effect because eligibility already fails.
    rentas_anuales_euros
        The descendant's own annual rentas EXCLUDING exempt income, the figure
        Art. 58.1 LIRPF caps ("no tenga rentas anuales, excluidas las exentas,
        superiores a 8.000 euros"). ``None`` means the operator has not declared
        a figure, which does NOT exclude the descendant — see
        :meth:`is_eligible_ordinary` for why absence is read as "no rentas to
        declare" rather than as a disqualification.
    presenta_declaracion_propia
        Whether the descendant files their own IRPF return. Art. 61 norma 2ª
        LIRPF withdraws the mínimo entirely when a descendant who generates the
        entitlement "presenten declaración por este Impuesto con rentas
        superiores a 1.800 euros" — so this flag alone does not exclude; it
        excludes only in combination with ``rentas_anuales_euros`` above the
        norma 2ª threshold. Default ``False``.
    prorrata_minimo
        Explicit per-descendant answer to Art. 61 norma 1ª: does another
        contribuyente also hold the right to this descendant's mínimo?
        ``True`` prorates, ``False`` claims the full amount, and ``None``
        (the default) leaves the question unanswered so the caller may derive
        it from profile signals. An explicit value ALWAYS wins over both
        ``custodia_compartida`` and any derivation.
    meses_madre_trabajo_2024
        Months the mother worked while this child was under 3 years old during
        the 2024 filing year.  Used by Art. 81 LIRPF deducción maternidad:
        ``min(meses × 100, 1_200)`` per eligible child.  Valid range: 0–12.
        Default ``0`` (no deducción contribution from this child).
    alta_posterior_nacimiento_mes
        The calendar month (1-12) in which the mother — not registered with the
        Seguridad Social or a mutualidad at this child's birth — completed the
        30-day minimum contribution period Art. 81.1 LIRPF requires for the
        post-birth alta route ("que en dicho momento o en cualquier momento
        posterior estén dadas de alta ... con un período mínimo, en este último
        caso, de 30 días cotizados"). ``None`` (the default) means the ordinary
        case: no post-birth alta increment applies, whether because the mother
        was already registered at the birth or because none is declared. This is
        the mother's employment history, exactly as ``meses_madre_trabajo_2024``
        is, and this application does not hold it and must not infer it.

        The route itself is filing-year gated: LIRPF art. 81.1 reached only a
        mother already registered "en el momento del nacimiento" before filing
        year 2023 (see
        :data:`~cadrumo.core.external_constants.DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR`),
        so a declared month for an earlier filing year contributes no
        increment — see :meth:`maternidad_alta_posterior_increment_applies`.
    gastos_guarderia_euros
        Actual guardería / centro educación infantil autorizado expenses paid
        for this child (Art. 81.2 LIRPF), as an ANNUAL total.  Integer euros,
        ≥ 0. Default ``0`` (no guardería expenses declared for this child).
        Sufficient only while the child is under three for the whole period; it
        cannot express either month boundary the statute draws.
    gastos_guarderia_mensuales
        The same spend broken down by month, sparse: only months with spend
        appear. Required for the period in which the child turns three, because
        that period needs the post-birthday months separated and an annual total
        cannot be apportioned across a birthday. Mutually exclusive with
        ``gastos_guarderia_euros`` for one child — declaring both is refused
        rather than reconciled, so a descendant always has exactly one spend
        authority.
    death_date
        The date this descendant died, or ``None`` (the default) for a
        descendant who did not die. Art. 61 norma 4ª LIRPF turns on this fact
        twice, and the two limbs read it differently, which is why one date
        drives both rather than a bare "died this year" flag.

        A death IN the filing period replaces this descendant's Art. 58.1
        birth-order tranche with the norma 4ª flat cuantía, at any birth order
        — the flat figure coincides with the first-child tranche, so the
        substitution is invisible for a first child and worth 300 € to 2.100 €
        for a later one. The Art. 58.2 menor-3 supplement is NOT replaced: the
        AEAT manual states it "resulta aplicable en los casos en que el
        descendiente haya fallecido durante el período impositivo", so it is
        added on top of the flat figure exactly as it is on top of a tranche.

        A death BEFORE the devengo (31 December) additionally drops this
        descendant from the age ordering that ranks the survivors — the
        manual's "sin computar a estos efectos aquellos descendientes que, en
        su caso, hubieran fallecido en el ejercicio con anterioridad a la fecha
        de devengo del impuesto". The two limbs are deliberately NOT collapsed
        into one condition: the flat cuantía is owed on any death in the
        period, while the ordering exclusion is expressly conditioned on the
        death preceding the devengo, so a descendant who dies ON 31 December
        takes the flat figure and still occupies their rank. That case is
        degenerate but the clauses are worded differently, and reading them as
        one would be a choice neither text supports.

        A death in a PRIOR year makes this descendant no part of this period at
        all — see :meth:`meets_non_income_conditions`.
    nif
        Optional NIF/NIE; validated for shape when present.
    """

    model_config = _STRICT_FROZEN

    birth_date: date
    relacion: DescendantRelacion = DescendantRelacion.DESCENDIENTE
    inscripcion_registro_civil_date: date | None = None
    acogimiento_resolucion_date: date | None = None
    death_date: date | None = None
    discapacidad_grado: Literal[0, 33, 65] | None = None
    convive_con_contribuyente: bool = True
    dependencia_economica: bool | None = None
    custodia_compartida: bool = False
    rentas_anuales_euros: Decimal | None = Field(default=None, ge=Decimal("0"))
    presenta_declaracion_propia: bool = False
    prorrata_minimo: bool | None = None
    meses_madre_trabajo_2024: int = Field(default=0, ge=0, le=12)
    alta_posterior_nacimiento_mes: int | None = Field(default=None, ge=1, le=12)
    gastos_guarderia_euros: int = Field(default=0, ge=0)
    gastos_guarderia_mensuales: tuple[GuarderiaMonthSpend, ...] = ()
    nif: str | None = None

    @field_validator(
        "birth_date",
        "inscripcion_registro_civil_date",
        "acogimiento_resolucion_date",
        "death_date",
        mode="before",
    )
    @classmethod
    def _parse_date(cls, value: object) -> object:
        return _coerce_iso_date_field(value)

    @model_validator(mode="after")
    def _validate_death_date(self) -> DescendantInfo:
        """A death cannot precede the birth.

        The only ordering this record can judge without knowing a filing year.
        A future death date is deliberately NOT refused here: profiles are
        effective-dated and a record may legitimately be read while resolving
        an earlier filing year, so "after today" is not the same defect it is
        for an entry event, and refusing it would reject a truthful record.
        """
        if self.death_date is not None and self.death_date < self.birth_date:
            raise ProfileValidationError(
                f"death_date {self.death_date.isoformat()} precedes birth_date "
                f"{self.birth_date.isoformat()}; a descendant cannot die before being born.",
            )
        return self

    def died_in_period(self, filing_year: int) -> bool:
        """True when this descendant died during *filing_year*.

        The Art. 61 norma 4ª trigger for the FLAT cuantía, which the statute
        conditions on the fallecimiento alone with no reference to the devengo.
        """
        return self.death_date is not None and self.death_date.year == filing_year

    def died_before_devengo(self, filing_year: int) -> bool:
        """True when this descendant died in *filing_year* before its 31 December devengo.

        The trigger for the ORDERING limb only, which the AEAT manual conditions
        on the death falling "con anterioridad a la fecha de devengo del
        impuesto". Strictly narrower than :meth:`died_in_period`, and the gap
        between them is load-bearing rather than an oversight — see the
        ``death_date`` field documentation.
        """
        if self.death_date is None or not self.died_in_period(filing_year):
            return False
        return self.death_date < date(filing_year, 12, 31)

    @model_validator(mode="before")
    @classmethod
    def _infer_relacion_from_inscripcion(cls, data: object) -> object:
        """Read an unstated relación off an inscription date rather than guessing.

        A Registro Civil inscription date is the adoption anchor and nothing
        else carries it, so a record supplying one while saying nothing about
        the relación has already stated it — resolving that to
        :attr:`~cadrumo.core.DescendantRelacion.ADOPTADO` is a reading of the
        same information, not an inference about a case the operator left open.

        Deliberately NOT symmetric with the acogimiento date. That date is
        compatible with two members and the statute treats them oppositely, so
        picking one would be the guess this axis exists to remove; an
        acogimiento date with no stated relación is refused below instead, and
        the refusal names both members so the operator resolves it themselves.

        Runs ``mode="before"`` because the default makes an ABSENT relación and
        an explicitly-ordinary one indistinguishable afterwards, and those two
        get opposite treatment: absent is read, explicit is a contradiction the
        coherence check refuses.

        An explicit ``None`` counts as unstated, which is what lets every entry
        door express "the operator did not answer" without each inventing its
        own sentinel: the flag parser, the fact-index reader and the wizard
        projection all pass the optional token straight through. The key is then
        dropped so the field default applies.
        """
        if not isinstance(data, dict):
            return data
        # CAST-RATIONALE-PRE-VALIDATION-INPUT: untyped by construction, this
        # is raw pre-validation input, and pydantic re-validates every value
        # against the declared field type immediately after.
        # nosemgrep: no-cast-in-domain-application
        raw = cast("dict[str, object]", data)
        if raw.get("relacion") is not None:
            return raw
        if raw.get("inscripcion_registro_civil_date") is not None:
            return {**raw, "relacion": DescendantRelacion.ADOPTADO}
        return {key: value for key, value in raw.items() if key != "relacion"}

    @model_validator(mode="after")
    def _validate_guarderia_spend(self) -> DescendantInfo:
        """One spend authority per child, and a coherent monthly map.

        Refuses BOTH an annual total and a monthly breakdown for the same child.
        Reconciling two figures would mean choosing one silently, and whichever
        was chosen the other would sit in the record contradicting it; a filer
        reading their own profile could not tell which one reached the filing.

        Also refuses a repeated month, which is the only way a sparse map can be
        internally inconsistent: two entries for the same month are either a
        duplicate or a partial, and summing them silently would invent a figure
        the operator never stated.
        """
        months = [entry.month for entry in self.gastos_guarderia_mensuales]
        duplicates = sorted({month for month in months if months.count(month) > 1})
        if duplicates:
            raise ProfileValidationError(
                f"gastos_guarderia_mensuales declares month(s) {duplicates} more than once; "
                "give one entry per month carrying that month's total.",
            )
        if self.gastos_guarderia_mensuales and self.gastos_guarderia_euros > 0:
            raise ProfileValidationError(
                "gastos_guarderia_euros and gastos_guarderia_mensuales cannot both be declared for "
                "one descendant. The monthly breakdown is the authority where it exists; drop the "
                "annual total rather than stating the spend twice.",
            )
        return self

    @model_validator(mode="after")
    def _validate_entry_event_dates(self) -> DescendantInfo:
        """Enforce the entry-event dates' ordering and their relación coherence.

        Two rules, and they fail in deliberately different directions.

        ORDERING refuses: an entry event before the birth or in the future is
        not a fact about any real placement, exactly as the retired
        ``adoption_date`` refused the same shapes.

        COHERENCE refuses an entry date carried by a relación the statute
        excludes — a tutela guardian, a temporal acogimiento carer, or an
        explicitly-ordinary descendant. Tolerating it would leave an entitling
        anchor sitting on an excluded record, and the Art. 58.2 limb would then
        be reachable through the only date field those records have. That is
        the over-grant this axis was added to prevent, so it fails loudly at
        the boundary rather than being filtered later by whichever predicate
        happens to remember.

        The converse — an entitling relación with NO entry date — is VALID and
        silent here. The window limb simply cannot fire without an anchor, so
        the record under-grants; refusing it would block an operator from
        recording a placement whose date they do not yet hold, and a refusal to
        record is worse than a grant deferred. The calculate path raises a
        visible advisory for exactly that state.
        """
        self._refuse_out_of_range_entry_dates()
        self._refuse_incoherent_entry_dates()
        return self

    @model_validator(mode="after")
    def _validate_alta_posterior_coherence(self) -> DescendantInfo:
        """Refuse an alta-posterior month declared against zero worked months.

        ``meses_madre_trabajo_2024`` already counts the completion month as one
        of its declared months (the manual's own worked example counts May
        among the mellizos' eight months, not separately from them), so a month
        naming a completion event while the mother is declared to have worked
        zero months is not a state Art. 81.1 describes -- it is either a
        forgotten MESES_TRABAJO figure or a month named for the wrong child.
        Refusing here is the same call every other coherence rule on this
        record makes: a silent zero-effect acceptance would leave the operator
        believing the increment applies when nothing downstream can grant it.
        """
        if self.alta_posterior_nacimiento_mes is not None and self.meses_madre_trabajo_2024 <= 0:
            raise ProfileValidationError(
                "alta_posterior_nacimiento_mes is declared but meses_madre_trabajo_2024 is 0; the "
                "completion month is one of the declared working months, not separate from them. "
                "Declare meses_madre_trabajo_2024 as well, or drop alta_posterior_nacimiento_mes if "
                "this child's mother was already registered at the birth.",
            )
        return self

    def _refuse_out_of_range_entry_dates(self) -> None:
        """Refuse an entry event before the birth or in the future."""
        today = today_madrid()
        for field_name, value in (
            ("inscripcion_registro_civil_date", self.inscripcion_registro_civil_date),
            ("acogimiento_resolucion_date", self.acogimiento_resolucion_date),
        ):
            if value is None:
                continue
            if value < self.birth_date:
                raise ProfileValidationError(f"{field_name} {value} must be ≥ birth_date {self.birth_date}")
            if value > today:
                raise ProfileValidationError(
                    f"{field_name} {value} must not be in the future (today={today})",
                )

    def _refuse_incoherent_entry_dates(self) -> None:
        """Refuse an entry-event date the declared relación cannot carry."""
        if self.inscripcion_registro_civil_date is not None and self.relacion is not DescendantRelacion.ADOPTADO:
            raise ProfileValidationError(
                f"inscripcion_registro_civil_date is the Art. 58.2 anchor for an adoption and cannot be "
                f"carried by relacion={self.relacion.value!r}. Set relacion="
                f"{DescendantRelacion.ADOPTADO.value!r}, or record the placement date as "
                f"acogimiento_resolucion_date if this is an acogimiento.",
            )
        if self.acogimiento_resolucion_date is not None and self.relacion not in ART_58_2_ENTITLING_RELACIONES:
            entitling = ", ".join(sorted(member.value for member in ART_58_2_ENTITLING_RELACIONES))
            raise ProfileValidationError(
                f"acogimiento_resolucion_date is the first ENTITLING acogimiento resolución (Art. 58.2 "
                f"names acogimiento 'tanto preadoptivo como permanente') and cannot be carried by "
                f"relacion={self.relacion.value!r}; accepted values are {entitling}. A temporal "
                f"acogimiento is assimilated by Art. 58.1 for the tranches but excluded from the "
                f"Art. 58.2 increase, so it carries no entry date.",
            )

    @field_validator("nif")
    @classmethod
    def _validate_nif(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().upper()
        if not stripped:
            raise ProfileValidationError("nif must not be blank when provided")
        if len(stripped) not in (9,):
            raise ProfileValidationError(f"nif must be 9 characters, got {len(stripped)!r} for {value!r}")
        return stripped

    def age_at_year_end(self, filing_year: int) -> int:
        """Return the descendant's age at the end of *filing_year*, or at death.

        A descendant who died during the period is aged at their DEATH DATE, not
        at 31 December, and that distinction is load-bearing rather than
        pedantic. Aging them to year-end returns an age they never reached
        whenever their birthday falls between the death and 31 December, and the
        consequences are both silent and both against a bereaved filer: a child
        who died at 24 reads as 25 and fails the Art. 58.1 age limb outright, so
        the flat cuantía Art. 61 norma 4ª exists to grant is never reached; a
        toddler who died at two reads as three and loses the menor-tres
        increment this module's own aggregate promises them.

        Norma 4ª exists BECAUSE the deceased is absent at the devengo, so
        applying a 31-December test to someone the statute already treats as
        dead defeats the provision's own premise. The AEAT manual cited at
        :meth:`minimo_descendientes_estatal` grants the menor-tres increase to a
        descendant who died during the period, which is the same reading.

        A death in a PRIOR year is not aged here at all -- that descendant is
        already excluded by :meth:`meets_non_income_conditions`, which fails on
        ``death_date.year < filing_year`` before any age question is asked.
        """
        reference = date(filing_year, 12, 31)
        if self.death_date is not None and self.death_date.year == filing_year:
            reference = self.death_date
        age = reference.year - self.birth_date.year
        # Subtract one if the birthday has not yet occurred by the reference date.
        if (self.birth_date.month, self.birth_date.day) > (reference.month, reference.day):
            age -= 1
        return age

    def _entry_date(self) -> date:
        """The nacimiento/adopción entry date the Madrid deducción window measures from.

        ADOPTION-SPECIFIC, and that is the whole reason two named dates replaced
        one general field. The Madrid decree (DL 1/2010 art. 4) keys its window
        on "nacimiento o adopción" and names no acogimiento, so an acogimiento
        resolución must not move this anchor even though it does open the
        Art. 58.2 window — the two statutes count from different events for the
        same child, and a single entry date could serve only one of them.

        Reading the inscription field alone is sufficient rather than lucky:
        :meth:`_refuse_incoherent_entry_dates` guarantees it is populated only
        on an :attr:`~cadrumo.core.DescendantRelacion.ADOPTADO` record, so a
        present value is always an adoption. Absent, the birth is the event.
        """
        return (
            self.inscripcion_registro_civil_date
            if self.inscripcion_registro_civil_date is not None
            else self.birth_date
        )

    def art_58_2_entry_date(self) -> date | None:
        """The FIRST entitling entry event for the Art. 58.2 window, or ``None``.

        Art. 58.2's three periods are a cap rather than a restart: where the
        circumstances change — the authority's own worked example is an adoption
        following a fostering — the increase continues for the remaining periods
        up to a maximum of three. Anchoring on whichever event the record
        happens to hold would grant a fostered-then-adopted child up to six
        periods where the statute allows three, so the earliest entitling event
        is the anchor and the later one changes nothing.

        Returns ``None`` for a relación the statute excludes from the limb
        (tutela, temporal acogimiento, an ordinary descendant) and for an
        entitling relación whose date is not yet recorded.
        """
        if self.relacion not in ART_58_2_ENTITLING_RELACIONES:
            return None
        candidates = [
            value
            for value in (self.inscripcion_registro_civil_date, self.acogimiento_resolucion_date)
            if value is not None
        ]
        return min(candidates) if candidates else None

    def exceeds_rentas_cap(self, thresholds: MinimoDescendientesThresholds) -> bool:
        """True when a DECLARED rentas figure breaches the Art. 58.1 ceiling.

        Art. 58.1 LIRPF conditions the mínimo on the descendant holding no
        "rentas anuales, excluidas las exentas, superiores a" the ceiling, so
        the test is strictly greater-than: a descendant exactly AT the ceiling
        keeps the mínimo.

        An undeclared figure (``rentas_anuales_euros is None``) returns
        ``False`` — absence of data is not evidence of income. The alternative
        default would zero the mínimo for every descendant nobody has yet
        entered a figure for, which is the overwhelming majority (a young child
        has no rentas to declare) and would be a large silent UNDER-claim
        against the taxpayer. The residual over-claim risk — a descendant who
        really does earn above the ceiling whose figure was never entered — is
        the operator's to close by declaring the figure.
        """
        if self.rentas_anuales_euros is None:
            return False
        return self.rentas_anuales_euros > thresholds.rentas_anuales_limite

    def excluded_by_declaracion_propia(self, thresholds: MinimoDescendientesThresholds) -> bool:
        """True when Art. 61 norma 2ª withdraws the mínimo for this descendant.

        Norma 2ª bars the mínimo when the descendant who generates the
        entitlement "presenten declaración por este Impuesto con rentas
        superiores a" the norma 2ª figure. Both halves are required: filing a
        return is not disqualifying on its own (the AEAT manual is explicit
        that a descendant filing with "rentas iguales o inferiores a 1.800
        euros" leaves the mínimo intact), and rentas alone are governed by the
        separate Art. 58.1 ceiling.

        An undeclared rentas figure returns ``False`` for the same reason as
        :meth:`exceeds_rentas_cap`.
        """
        if not self.presenta_declaracion_propia:
            return False
        if self.rentas_anuales_euros is None:
            return False
        return self.rentas_anuales_euros > thresholds.declaracion_propia_rentas_limite

    def is_eligible_ordinary(
        self,
        filing_year: int,
        *,
        thresholds: MinimoDescendientesThresholds,
        dependencia_assimilation_available: bool = False,
    ) -> bool:
        """True when the descendant qualifies for the Art. 58.1 ordinary mínimo.

        Eligibility requires ALL of:

        * cohabiting with the taxpayer (Art. 58.1 "siempre que conviva con el
          contribuyente"), OR assimilated economic dependency — see
          :meth:`meets_non_income_conditions`;
        * age < 25 at year-end OR any degree of discapacidad;
        * annual rentas excluding exempt income at or below the Art. 58.1
          ceiling (:meth:`exceeds_rentas_cap`);
        * not excluded by the Art. 61 norma 2ª own-return rule
          (:meth:`excluded_by_declaracion_propia`).

        *thresholds* is a required keyword argument rather than an optional
        one so no caller can silently evaluate the age/cohabitation half of the
        law while skipping the two income conditions.
        """
        if self.exceeds_rentas_cap(thresholds):
            return False
        if self.excluded_by_declaracion_propia(thresholds):
            return False
        return self.meets_non_income_conditions(
            filing_year,
            dependencia_assimilation_available=dependencia_assimilation_available,
        )

    def meets_non_income_conditions(
        self,
        filing_year: int,
        *,
        dependencia_assimilation_available: bool = False,
    ) -> bool:
        """The half of Art. 58.1 that needs no ceiling: the household limb and age/discapacidad.

        Split out rather than inlined because one caller genuinely cannot supply
        the ceilings and does not need them. A descendant with NO declared rentas
        figure can never be excluded by either income condition — both read an
        absent figure as non-excluding — so for that descendant eligibility
        reduces exactly to this predicate. The calculate-path advisory that flags
        those descendants therefore asks this question directly instead of
        re-deriving it beside :meth:`is_eligible_ordinary`, which is how the two
        would drift.

        A descendant who died in a year BEFORE *filing_year* fails outright,
        ahead of every other condition. They were no part of this period, and
        the age limb would otherwise keep answering for them indefinitely —
        ``birth_date`` alone goes on satisfying "under 25 at year-end" for years
        after the death, so without this gate a bereaved filer would keep
        claiming the mínimo for a child who died long ago, and the norma 4ª
        flat cuantía would not apply either because that limb is scoped to a
        death IN the period. Gated here rather than in
        :meth:`is_eligible_ordinary` so the calculate-path advisory that asks
        this predicate directly cannot answer differently from the aggregate.

        The household limb is cohabitation OR assimilated economic dependency.
        The authority states the dependency case in terms: a progenitor without
        custody, not even shared, and paying no judicial anualidades, who
        nonetheless contributes to the descendant's economic upkeep "tendrá
        derecho a la aplicación del mínimo por descendientes". Cohabitation is
        therefore sufficient but not necessary, which is what an earlier reading
        of this predicate got wrong.

        Assimilation requires BOTH halves and neither is a default. The
        descendant must carry an explicit ``dependencia_economica = True`` — an
        unset field never assimilates, because the reachable-through-the-only-
        available-field shape is how an excluded case gets granted. And the
        caller must pass *dependencia_assimilation_available*, which the profile
        computes from the filer-level anualidades declaration.

        That flag defaults to ``False``, so a caller that forgets it gets the
        UNDER-granting answer rather than the claiming one. The default is the
        safe direction by construction rather than by convention.

        Not a public substitute for :meth:`is_eligible_ordinary`. Answering
        ``True`` here says only that the non-income conditions hold; a caller
        that HAS a rentas figure must still apply the ceilings.
        """
        if self.death_date is not None and self.death_date.year < filing_year:
            return False
        if not self.qualifies_on_household_limb(
            dependencia_assimilation_available=dependencia_assimilation_available,
        ):
            return False
        if self.discapacidad_grado and self.discapacidad_grado > 0:
            return True
        return self.age_at_year_end(filing_year) < _MAX_AGE_ORDINARY

    def qualifies_on_household_limb(self, *, dependencia_assimilation_available: bool = False) -> bool:
        """True when cohabitation holds, or economic dependency is assimilated in its place.

        Named and public because three surfaces ask this question and one of
        them — the advisory that discloses the assimilation to the operator —
        needs it apart from the age limb.
        """
        if self.convive_con_contribuyente:
            return True
        return self.dependencia_economica is True and dependencia_assimilation_available

    def assimilated_by_dependencia(self, *, dependencia_assimilation_available: bool = False) -> bool:
        """True when this descendant reaches the mínimo ONLY through the dependency limb.

        The disclosure predicate: a descendant who cohabits is not assimilated
        even when the dependency fact is also set, so the advisory reports only
        the households where the assimilation is actually load-bearing.
        """
        if self.convive_con_contribuyente:
            return False
        return self.dependencia_economica is True and dependencia_assimilation_available

    def is_eligible_menor_tres(self, filing_year: int) -> bool:
        """True when the descendant is under three at the devengo date and cohabits.

        Scoped to the Art. 81 deductions — the deducción por maternidad
        (art. 81.1) and the guardería incremento (art. 81.2). It is NOT the
        Art. 58.2 test: see
        :meth:`is_eligible_minimo_incremento_menor_tres`, which carries an
        additional limb this one deliberately lacks.

        Two known narrowings against the Art. 81 text, both in the
        over-taxing direction and both needing data this axis does not carry:
        art. 81.1 runs monthly "hasta que el menor alcance los tres años de
        edad" rather than testing age once at year-end, and art. 81.2 extends
        the guardería incremento through the period in which the child turns
        three, "respecto de los gastos incurridos con posterioridad al
        cumplimiento de dicha edad hasta el mes anterior a aquel en el que
        pueda comenzar el segundo ciclo de educación infantil". Both need
        month-level figures; ``gastos_guarderia_euros`` is an annual total, so
        widening this predicate alone would swap an under-grant for an
        over-grant.
        """
        if not self.convive_con_contribuyente:
            return False
        return self.age_at_year_end(filing_year) < _MAX_AGE_MENOR_TRES

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
        return _months_of_year_between(
            (self.birth_date.year, self.birth_date.month),
            (self.birth_date.year + _MAX_AGE_MENOR_TRES, self.birth_date.month),
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
            return frozenset()
        return _months_of_year_between(
            (anchor.year, anchor.month),
            (anchor.year + _ART_81_1_ENTRY_WINDOW_YEARS, anchor.month),
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
        ``meses_madre_trabajo_2024`` records whether the mother held contributory
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

        The declared months are CAPPED by the eligible window rather than
        trusted outright. An operator who counted correctly is unaffected,
        because their figure already lies inside the window; one who declared raw
        employment months has the over-claim removed. The cap can only ever
        reduce, so it cannot invent an entitlement.

        That window is :meth:`maternidad_eligible_meses`, which carries both of
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
        return min(self.meses_madre_trabajo_2024, self.maternidad_eligible_meses(filing_year))

    def guarderia_simultaneity_meses(
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
        return min(self.meses_madre_trabajo_2024, len(self._guarderia_requirement_months(filing_year)))

    def _guarderia_requirement_months(self, filing_year: int) -> frozenset[int]:
        """The Art. 81.1 requirement months for the increment: the deducción window without its age ceiling."""
        entitling = _months_of_year_between(
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
        if age_at_year_end > _MAX_AGE_MENOR_TRES:
            return 0
        if self.gastos_guarderia_mensuales:
            # Every declared month counts in both periods: under three the child
            # qualifies throughout, and in the turning-three period the birthday
            # draws no line.
            return sum(entry.amount_euros for entry in self.gastos_guarderia_mensuales)
        if age_at_year_end < _MAX_AGE_MENOR_TRES:
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
        than presented as a measured result. It stops being an approximation
        once the Art. 81.1 side stores WHICH months the mother qualified rather
        than how many, which is a persisted-shape change this method cannot make
        on its own.

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
        if age_at_year_end > _MAX_AGE_MENOR_TRES:
            return 0
        if self.gastos_guarderia_mensuales:
            return len(self.gastos_guarderia_mensuales)
        if age_at_year_end < _MAX_AGE_MENOR_TRES:
            return self.age_eligible_guarderia_meses(filing_year)
        return 0

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
        if self.age_at_year_end(filing_year) != _MAX_AGE_MENOR_TRES:
            return False
        return self.gastos_guarderia_euros > 0 and not self.gastos_guarderia_mensuales

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
        return self.age_at_year_end(filing_year) <= _MAX_AGE_MENOR_TRES

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
        if self.age_at_year_end(filing_year) < _MAX_AGE_MENOR_TRES:
            return True
        entry_date = self.art_58_2_entry_date()
        if entry_date is None:
            return False
        periods_since_entry = filing_year - entry_date.year
        return 0 <= periods_since_entry <= _NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS

    def entry_year(self) -> int:
        """Calendar year of the nacimiento/adopción event, for the Madrid deducción window.

        Scoped to the autonomic nacimiento/adopción deducción and NOT to
        Art. 58.2, which counts from a different event for the same child: see
        :meth:`_entry_date` for why an acogimiento resolución moves one anchor
        and not the other, and :meth:`art_58_2_entry_date` for the state anchor.
        """
        return self._entry_date().year

    def art_58_2_window_anchor_missing(
        self,
        filing_year: int,
        *,
        dependencia_assimilation_available: bool = False,
    ) -> bool:
        """True when an entitling relación has no entry date, so the limb cannot fire.

        The recordable state the coherence validators deliberately allow: an
        operator may declare an adoption or an entitling acogimiento before they
        hold the inscription or resolución date. Art. 58.2's age-independent
        increase then cannot be granted, because the window has nothing to
        measure from — an UNDER-grant, which is the safe direction, but a silent
        one unless something says so.

        Reports only the state that changes an outcome, so the advisory it feeds
        stays worth reading. A relación the statute excludes from the limb has
        no anchor to be missing. A descendant who fails the Art. 58.1 non-income
        conditions — not cohabiting, or over 25 with no discapacidad — carries no
        mínimo for the increase to attach to, so a missing date costs them
        nothing; a 30-year-old adopted descendant is the false positive this limb
        exists to suppress. And a descendant already under three takes the
        increase through the ordinary limb regardless.

        What remains is the older cohabiting adopted or fostered child, who is
        exactly the household the age-independent sentence was written for and
        the one currently granted nothing.

        The income ceilings are deliberately NOT applied. They need registry
        figures this layer does not resolve, and an absent rentas figure is
        non-excluding anyway, so the residual over-report is a descendant whose
        declared rentas breach the ceiling — a narrow case that already carries
        its own advisory.

        *dependencia_assimilation_available* is forwarded to the household limb
        for the same reason it exists there: a non-cohabiting descendant reaching
        the mínimo through the economic-dependency assimilation carries a real
        mínimo for the increase to attach to, so a missing anchor costs them
        exactly what it costs a cohabiting one. Omitting it took the predicate's
        ``False`` default and answered "no anchor missing" for that household —
        an under-grant reported to nobody, which is the one thing this disclosure
        exists to prevent.
        """
        if self.relacion not in ART_58_2_ENTITLING_RELACIONES:
            return False
        if not self.meets_non_income_conditions(
            filing_year,
            dependencia_assimilation_available=dependencia_assimilation_available,
        ):
            return False
        if self.age_at_year_end(filing_year) < _MAX_AGE_MENOR_TRES:
            return False
        return self.art_58_2_entry_date() is None

    def is_nacimiento_adopcion_eligible(
        self,
        filing_year: int,
        *,
        following_periods: int = _NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS,
    ) -> bool:
        """True when this descendant is inside the nacimiento/adopción window and cohabits.

        The Madrid nacimiento/adopción deducción (DL 1/2010 art. 4) requires both
        that the parent cohabits with the child ("Solo tendrán derecho a practicar
        la deducción los padres que convivan con los hijos nacidos o adoptados")
        and that the filing year falls inside the applicability window measured
        from the entry (nacimiento/adopción) year.
        """
        if not self.convive_con_contribuyente:
            return False
        return within_multi_year_applicability_window(
            self.entry_year(),
            filing_year,
            following_periods=following_periods,
        )

    def nacimiento_adopcion_prorrateo_share(self) -> Decimal:
        """Return this descendant's share of the deducción after prorrateo.

        When the child cohabits with both parents and they file individually the
        Madrid manual splits the amount equally between the two declarations
        (":data:`CUSTODIA_COMPARTIDA_PRORRATA_FACTOR`" / ``Decimal("0.5")``);
        otherwise the full amount accrues to this filer (``Decimal("1")``).
        ``custodia_compartida`` is the profile signal for the shared-cohabitation
        case that triggers the ÷2 prorrateo.
        """
        return CUSTODIA_COMPARTIDA_PRORRATA_FACTOR if self.custodia_compartida else Decimal("1")


class _RentaPersonProfileBase(BaseModel):
    """Private base for person-profile rows in the official Modelo 100 family section.

    Carries the shared :class:`~datetime.date` fields and their validators for
    :class:`RentaDescendantProfile` and :class:`RentaAscendantProfile`.
    Both subclasses declare the same ``tax_id``/``display_name``/
    ``disability_grade`` optional-text guard and the ``birth_date``/
    ``death_date`` ISO-8601 parser; extracting them here removes the
    duplicate without altering any field constraint.
    """

    model_config = _STRICT_FROZEN

    tax_id: str | None = None
    display_name: str | None = None
    birth_date: date
    disability_grade: str | None = None
    death_date: date | None = None

    @field_validator("tax_id", "display_name", "disability_grade")
    @classmethod
    def _optional_text_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ProfileValidationError("optional text fields must not be blank")
        return stripped

    @field_validator("birth_date", "death_date", mode="before")
    @classmethod
    def _parse_date(cls, value: object) -> object:
        return _coerce_iso_date_field(value)


class RentaDescendantProfile(_RentaPersonProfileBase):
    """One descendant row from the official Modelo 100 family section."""


class RentaAscendantProfile(_RentaPersonProfileBase):
    """One ascendant row from the official Modelo 100 family section."""

    cohabiting_descendant_count: int | None = Field(default=None, ge=0, le=10)


class RentaFamilyProfile(BaseModel):
    """Typed repeated family-member facts consumed by Modelo 100 bindings."""

    model_config = _STRICT_FROZEN

    schema_version: str = Field(default="1")
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

    @field_validator("schema_version")
    @classmethod
    def _schema_version_is_supported(cls, value: str) -> str:
        if value != "1":
            raise ProfileValidationError("schema_version must be '1'")
        return value

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
        :meth:`DescendantInfo.guarderia_simultaneity_meses` rather than the
        deducción's own :meth:`DescendantInfo.maternidad_contributing_meses`,
        and the distinction is load-bearing: the deducción stops at the child's
        third birthday while the increment does not, so reusing it forced this
        total to zero for a child turning three in January and for a mother who
        began work after the birthday — two cases Capítulo 18 names explicitly
        as still qualifying.

        The Art. 81.2 side is a real month set
        (:meth:`DescendantInfo.guarderia_qualifying_meses`); the Art. 81.1 side
        is only a COUNT, because the record stores how many months the mother
        qualified and never which ones. So this is a genuine intersection on one
        side and an upper bound on the other, and it over-states only when the
        two spans do not overlap — a mother qualifying January to April against
        nursery paid September to October. That residual is disclosed to the
        operator rather than presented as measured. It stops being an
        approximation once the Art. 81.1 side stores WHICH months the mother
        qualified rather than how many, which is a persisted-shape change beyond
        this method. The bound is preferred to a flat per-child cap, which
        over-grants every mid-year birth and every partial-year enrolment
        outright.

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
            meses = min(
                descendant.guarderia_qualifying_meses(filing_year),
                descendant.guarderia_simultaneity_meses(
                    filing_year,
                    thresholds=thresholds,
                    dependencia_assimilation_available=available,
                ),
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
        # Art. 61 norma 4ª limb two: the ordering that assigns "primero,
        # segundo, tercero…" is computed over the survivors ALONE. A descendant
        # who died before the devengo still contributes (limb one) but vacates
        # their rank, which is what moves each younger sibling down a tranche.
        # Keyed by POSITION rather than by the record itself: DescendantInfo is
        # a frozen pydantic model, so two identically-declared siblings — twins
        # with the same birth date and no distinguishing fact — compare equal,
        # and a value-keyed lookup would give them both the elder's rank.
        rank_by_position = {
            position: rank
            for rank, position in enumerate(
                position for position, d in enumerate(eligible) if not d.died_before_devengo(filing_year)
            )
        }
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


__all__ = [
    "DescendantInfo",
    "RentaAscendantProfile",
    "RentaDescendantProfile",
    "RentaFamilyProfile",
    "within_multi_year_applicability_window",
]
