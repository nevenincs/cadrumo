"""Validated descendant facts and core Art. 58 eligibility behavior."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import ART_58_2_ENTITLING_RELACIONES, DescendantRelacion
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time import today_madrid
from .errors import ProfileValidationError
from ._family_types import (
    MAX_AGE_MENOR_TRES,
    MAX_AGE_ORDINARY,
    GuarderiaMonthSpend,
    MinimoDescendientesThresholds,
    coerce_iso_date_field,
)


class DescendantRecordFields(BaseModel):
    """Canonical field vocabulary shared by domain records and projections."""

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
    meses_madre_trabajo: tuple[int, ...] = ()
    alta_posterior_nacimiento_mes: int | None = Field(default=None, ge=1, le=12)
    segundo_ciclo_infantil_inicio_mes: int | None = Field(default=None, ge=1, le=12)
    gastos_guarderia_euros: int = Field(default=0, ge=0)
    gastos_guarderia_mensuales: tuple[GuarderiaMonthSpend, ...] = ()
    nif: str | None = None


class DescendantRecordBase(DescendantRecordFields):
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
    meses_madre_trabajo
        WHICH calendar months (1-12, ascending, no repeats) the mother met the
        Art. 81.1 requirements for this child. Used by the deducción maternidad
        as a count — ``min(meses × 100, 1_200)`` per eligible child — and by the
        Art. 81.2 guardería increment as a SET.

        The months rather than their number, because Art. 81.2 prorates by "el
        número de meses en que se cumplan de forma simultánea los requisitos
        exigidos en el artículo 81.1 y 2": an INTERSECTION with the declared
        nursery months, which a count cannot express. A mother entitled May to
        August against nursery paid January to June shares two months and the
        manual works ``1.000 ÷ 12 × 2 = 166,67``, where a count-based
        ``min(4, 6)`` yields four and 333,33 — an over-grant of the deducción,
        which under-declares tax. Default ``()`` (no deducción contribution
        from this child).
    alta_posterior_nacimiento_mes
        The calendar month (1-12) in which the mother — not registered with the
        Seguridad Social or a mutualidad at this child's birth — completed the
        30-day minimum contribution period Art. 81.1 LIRPF requires for the
        post-birth alta route ("que en dicho momento o en cualquier momento
        posterior estén dadas de alta ... con un período mínimo, en este último
        caso, de 30 días cotizados"). ``None`` (the default) means the ordinary
        case: no post-birth alta increment applies, whether because the mother
        was already registered at the birth or because none is declared. This is
        the mother's employment history, exactly as ``meses_madre_trabajo``
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

    @field_validator(
        "birth_date",
        "inscripcion_registro_civil_date",
        "acogimiento_resolucion_date",
        "death_date",
        mode="before",
    )
    @classmethod
    def _parse_date(cls, value: object) -> object:
        return coerce_iso_date_field(value)

    @model_validator(mode="after")
    def _validate_death_date(self) -> DescendantRecordBase:
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
    def _validate_guarderia_spend(self) -> DescendantRecordBase:
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
    def _validate_entry_event_dates(self) -> DescendantRecordBase:
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

    @field_validator("meses_madre_trabajo")
    @classmethod
    def _validate_meses_madre_trabajo(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Refuse a month outside 1-12, a repeat, or an unsorted set.

        Canonical ascending order is enforced rather than applied, so the record
        has exactly one representation of a given set and a save-then-reload
        round-trip cannot reorder it. A repeat is refused rather than collapsed:
        a month either qualified or it did not, so a second mention is a
        transcription slip, and silently collapsing it would hide the slip while
        changing nothing the operator could see.
        """
        for month in value:
            if not (1 <= month <= 12):
                raise ProfileValidationError(
                    f"meses_madre_trabajo names month {month}, outside 1-12.",
                )
        if len(set(value)) != len(value):
            repeated = sorted({month for month in value if value.count(month) > 1})
            raise ProfileValidationError(
                f"meses_madre_trabajo declares month(s) {repeated} more than once.",
            )
        if list(value) != sorted(value):
            raise ProfileValidationError(
                f"meses_madre_trabajo must be ascending; got {list(value)}.",
            )
        return value

    @model_validator(mode="after")
    def _validate_alta_posterior_coherence(self) -> DescendantRecordBase:
        """Refuse an alta-posterior month incoherent with the declared working months.

        Two rules, both about the same single source of truth.

        The completion month is one OF the declared months (the manual's own
        worked example counts May among the mellizos' eight, not separately from
        them), so naming it against an empty set is not a state Art. 81.1
        describes -- it is either a forgotten month set or a month named for the
        wrong child.

        And it must be the FIRST of them. The post-birth alta route exists for a
        mother NOT registered at the birth, so her entitlement opens exactly when
        she completes the 30 days: AEAT's caso a has her start work in May,
        complete the period in May, and be entitled "de mayo a agosto ambos
        incluidos". Now that the months are carried rather than counted, the
        month is derivable from the set, and this field's remaining job is to
        record the ROUTE. Requiring the two to agree keeps that from becoming a
        second source of truth for one fact -- a divergence refuses instead of
        letting the pair disagree silently.

        This rule runs on construction and on every reload, because the fact
        readers rebuild the record through ``DescendantInfo(...)``; assignment is
        closed by ``frozen=True``. It does NOT run on ``model_copy(update=...)``,
        which skips validators by design and will happily produce a record whose
        alta month is not the first of its set. Nothing reaches that today -- no
        production caller copies a ``DescendantInfo`` -- so a future
        descendant-editing path must reconstruct rather than copy, or re-validate
        after copying.
        """
        if self.alta_posterior_nacimiento_mes is None:
            return self
        if not self.meses_madre_trabajo:
            raise ProfileValidationError(
                "alta_posterior_nacimiento_mes is declared but meses_madre_trabajo is empty; the "
                "completion month is one of the declared working months, not separate from them. "
                "Declare meses_madre_trabajo as well, or drop alta_posterior_nacimiento_mes if "
                "this child's mother was already registered at the birth.",
            )
        first = self.meses_madre_trabajo[0]
        if self.alta_posterior_nacimiento_mes != first:
            raise ProfileValidationError(
                f"alta_posterior_nacimiento_mes is {self.alta_posterior_nacimiento_mes} but the "
                f"declared working months open at {first}. The post-birth alta route entitles the "
                "mother from the month she completes the 30 days, so the two name one event and "
                "must agree.",
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
        return self.age_at_year_end(filing_year) < MAX_AGE_ORDINARY

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
        return self.age_at_year_end(filing_year) < MAX_AGE_MENOR_TRES
