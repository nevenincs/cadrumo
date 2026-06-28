"""Pydantic v2 strict models for the :mod:`aeat.domain.deadlines` subpackage.

Every type that crosses a public boundary lives here as a strict, frozen
:class:`pydantic.BaseModel` (or :class:`enum.StrEnum` for closed
enumerations). No dataclasses; no bare ``dict[str, Any]``.

Consumed by :class:`aeat.domain.deadlines.DeadlineEngine` and re-exported
from :mod:`aeat.domain.deadlines`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from ...core import IBAN_SHAPE_RE, Modelo, Period, iban_mod_97
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR
from ..contribuyente._renta_codes import UE_EEA_COUNTRY_CODES, FiscalResidency
from ._errors import DeadlineValidationError


class IVARegime(StrEnum):
    """The IVA regime a taxpayer files under.

    Registry deadline applicability can reference this value. The closed
    set tracks the IVA regimes the project supports.

    Attributes:
        GENERAL: Régimen general (Ley 37/1992 LIVA).
        SIMPLIFICADO: Régimen simplificado (módulos), coordinated with
            IRPF estimación objetiva.
        RECARGO_EQUIVALENCIA: Recargo de equivalencia for retail traders.
        REAGP: Régimen especial de la agricultura, ganadería y pesca.
        EXENTO: IVA-exempt activity.
    """

    GENERAL = "GENERAL"
    SIMPLIFICADO = "SIMPLIFICADO"
    RECARGO_EQUIVALENCIA = "RECARGO_EQUIVALENCIA"
    REAGP = "REAGP"
    EXENTO = "EXENTO"


class EntityType(StrEnum):
    """The taxpayer's entity type — the most consequential taxpayer axis.

    Entity type selects the tax (IRPF vs Impuesto sobre Sociedades vs
    régimen de atribución de rentas), and the tax selects the modelos,
    the calendar, and the rate schedule. Grounded in Ley 35/2006 LIRPF
    (BOE-A-2006-20764), Ley 27/2014 LIS (BOE-A-2014-12328), and LIRPF
    Title X Section 2 (régimen de atribución de rentas).

    Attributes:
        NATURAL_PERSON: Persona física — an IRPF taxpayer
            (contribuyente del IRPF).
        LEGAL_ENTITY: A legal entity with personalidad jurídica — a
            contribuyente del Impuesto sobre Sociedades.
        ATTRIBUTION_ENTITY: An entity without legal personality
            (comunidad de bienes, sociedad civil sin objeto mercantil,
            herencia yacente) under the régimen de atribución de rentas;
            income is taxed in the hands of each member.
    """

    NATURAL_PERSON = "natural_person"
    LEGAL_ENTITY = "legal_entity"
    ATTRIBUTION_ENTITY = "attribution_entity"


class LegalEntityForm(StrEnum):
    """The recognised legal form of an Impuesto sobre Sociedades entity.

    Only meaningful when :class:`EntityType` is ``LEGAL_ENTITY``; the
    sub-form drives the IS rate schedule (LIS Art. 29). Grounded in the
    AEAT distinction between sociedades civiles and comunidades de
    bienes and the project registry ``legal/is.toml``.

    Attributes:
        SL: Sociedad de responsabilidad limitada (S.L. / S.R.L.).
        SA: Sociedad anónima (S.A.).
        SAL: Sociedad Anónima Laboral (Ley 44/2015 Art. 1). Majority of
            share capital held by worker-shareholders. Eligible for
            reserva especial dotación under Ley 44/2015 Art. 14.
        SLL: Sociedad Limitada Laboral (Ley 44/2015 Art. 1). Same
            régimen as SAL but limited-liability form. Eligible for
            the same reserva especial under Ley 44/2015 Art. 14.
        COOPERATIVA: Sociedad cooperativa — IS with a reduced rate.
        SOCIEDAD_CIVIL_MERCANTIL: Sociedad civil con personalidad
            jurídica y objeto mercantil — an IS contribuyente since 2016.
        SIN_FINES_LUCRATIVOS: Asociación / fundación / entidad sin fines
            lucrativos — IS contribuyente, partially exempt.
        OTHER: Any other recognised legal form.
    """

    SL = "sl"
    SA = "sa"
    SAL = "sal"
    SLL = "sll"
    COOPERATIVA = "cooperativa"
    SOCIEDAD_CIVIL_MERCANTIL = "sociedad_civil_mercantil"
    SIN_FINES_LUCRATIVOS = "sin_fines_lucrativos"
    OTHER = "other"


class IrpfIncomeCategory(StrEnum):
    """An IRPF income category (rendimiento) a natural person declares.

    For a natural person the quarterly / informational modelo
    obligations derive from the income category, not from being a
    natural person as such. Grounded in Ley 35/2006 LIRPF
    (BOE-A-2006-20764).

    Attributes:
        ACTIVIDAD_ECONOMICA: Rendimientos de actividades económicas
            (autónomo / empresario / profesional) — LIRPF Arts. 27-32.
            The only category that triggers Modelo 130 / 131.
        TRABAJO: Rendimientos del trabajo (employment) — LIRPF
            Arts. 17-20.
        CAPITAL_INMOBILIARIO: Rendimientos del capital inmobiliario
            (immovable property / rental) — LIRPF Arts. 22-24.
        CAPITAL_MOBILIARIO: Rendimientos del capital mobiliario
            (dividends, interest) — LIRPF Arts. 25-26.
        GANANCIAS_PATRIMONIALES: Ganancias y pérdidas patrimoniales
            (capital gains) — LIRPF Arts. 33-39.
        PENSION: Pensión — a rendimiento del trabajo for IRPF purposes
            (LIRPF Art. 17.2.a), modelled separately so a pensioner
            profile is explicit.
    """

    ACTIVIDAD_ECONOMICA = "actividad_economica"
    TRABAJO = "trabajo"
    CAPITAL_INMOBILIARIO = "capital_inmobiliario"
    CAPITAL_MOBILIARIO = "capital_mobiliario"
    GANANCIAS_PATRIMONIALES = "ganancias_patrimoniales"
    PENSION = "pension"


class IrpfEstimationRegime(StrEnum):
    """The IRPF method for determining net economic-activity income.

    A closed regime choice for a natural person with rendimientos de
    actividades económicas (LIRPF Arts. 16, 28-31; RIRPF RD 439/2007).
    The regime selects Modelo 130 vs Modelo 131 and the
    deductible-expense computation.

    Attributes:
        DIRECTA_NORMAL: Estimación directa normal — full accounting;
            pago fraccionado on Modelo 130.
        DIRECTA_SIMPLIFICADA: Estimación directa simplificada — applies
            below the INCN threshold; pago fraccionado on Modelo 130.
        OBJETIVA: Estimación objetiva (módulos) — net income from
            signos, índices y módulos; pago fraccionado on Modelo 131.
    """

    DIRECTA_NORMAL = "directa_normal"
    DIRECTA_SIMPLIFICADA = "directa_simplificada"
    OBJETIVA = "objetiva"


class IrpfSpecialRegime(StrEnum):
    """IRPF special-regime category for natural persons.

    Most taxpayers file under the general IRPF regime. The ``IMPATRIADO``
    value represents the régimen especial aplicable a los trabajadores
    desplazados a territorio español (LIRPF Art. 93, "Ley Beckham"),
    introduced by Ley 62/2003 and extended by Ley 26/2014. Under this
    regime the taxpayer files Modelo 151 (not Modelo 100) and is taxed
    at the flat IRNR rate on Spanish-source income.

    Grounded in LIRPF Ley 35/2006 Art. 93 (BOE-A-2006-20764) and
    RIRPF RD 439/2007 Arts. 113-120 (BOE-A-2007-6820).

    Attributes:
        GENERAL: Standard IRPF — files Modelo 100, subject to the
            progressive tarifa general / del ahorro.
        IMPATRIADO: Régimen especial impatriados (Art. 93 LIRPF) —
            files Modelo 151, taxed at the flat IRNR rate. The regime
            has a six-year window triggered by the opt-in election date
            (``special_regime_start_date`` on the profile).
    """

    GENERAL = "general"
    IMPATRIADO = "impatriado"


class ObligationStatus(StrEnum):
    """Status of a single :class:`ModeloDeadline` against a reference date.

    :attr:`UPCOMING` and :attr:`DUE_SOON` are differentiated by the
    ``AEAT_DEADLINE_DUE_SOON_DAYS`` setting (default 14 days).
    :attr:`FILED` and :attr:`NOT_APPLICABLE` are reserved for downstream
    consumers — the engine never produces them.

    Attributes:
        UPCOMING: Window opens in the future or is open but more than
            ``due_soon_days`` ahead of close.
        DUE_SOON: Window closes within ``due_soon_days`` of the
            reference date.
        DUE_TODAY: Reference date is the close date.
        OVERDUE: Reference date is past the close date.
        FILED: Downstream marker for filings already submitted.
        NOT_APPLICABLE: Downstream marker for obligations the profile
            no longer triggers.
    """

    UPCOMING = "UPCOMING"
    DUE_SOON = "DUE_SOON"
    DUE_TODAY = "DUE_TODAY"
    OVERDUE = "OVERDUE"
    FILED = "FILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ModeloEnrollment(BaseModel):
    """AEAT enrollment facts used by registry filing schedules."""

    model_config = _STRICT_FROZEN

    large_company: bool = False
    public_administration_budget_gt_6000000: bool = False


class RefundAccount(BaseModel):
    """The cuenta-devolución refund account AEAT pays a Modelo 303 refund into.

    Groups the IBAN with the foreign-bank block used for a non-SEPA
    account. Every field is sensitive financial identity data: per the
    ``sensitive-financial-data-secure-storage-only`` invariant it lives
    only in the encrypted secure-object store (``sensitivity="financial"``
    on the profile schema), is read transiently into memory at export
    time, and is never written to plaintext, logs, or a side store.

    The IBAN is validated structurally at this boundary — country code,
    check digits, BBAN length, and the ISO 13616 mod-97 residue — so a
    malformed IBAN is rejected on input rather than deferred to
    fichero-write time.

    Attributes:
        iban: The refund account IBAN (canonical, whitespace- and
            hyphen-stripped, upper-cased). ``None`` when no refund
            account is on file.
        swift_bic: SWIFT-BIC of the bank for a non-SEPA account.
        bank_name: Bank name for a non-SEPA (Resto Países) account.
        bank_address: Bank address for a non-SEPA account.
        bank_city: Bank city for a non-SEPA account.
        bank_country_code: ISO 3166-1 alpha-2 country code of the bank
            for a non-SEPA account.
        sepa_marca: The derived Marca SEPA token (``"1"`` Cuenta España /
            ``"2"`` UE SEPA / ``"3"`` Resto Países). Derived from the
            account country at export, not an operator input.
    """

    model_config = _STRICT_FROZEN

    iban: str | None = None
    swift_bic: str = ""
    bank_name: str = ""
    bank_address: str = ""
    bank_city: str = ""
    bank_country_code: str = ""
    sepa_marca: str = ""

    @field_validator("iban", mode="before")
    @classmethod
    def _validate_iban(cls, value: object) -> object:
        """Reject a malformed IBAN at the secure-storage boundary.

        Strips whitespace and hyphens, upper-cases, then enforces the
        ISO 13616 shape (``CC kk BBAN``, total 15–34 chars) and the
        mod-97 residue check. ``None`` and the empty string mean "no
        refund account on file" and pass through as ``None``.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            raise DeadlineValidationError("refund-account iban must be a string")
        canonical = value.replace(" ", "").replace("-", "").upper()
        if not canonical:
            return None
        if not IBAN_SHAPE_RE.match(canonical):
            raise DeadlineValidationError(
                f"refund-account iban {value!r} does not match the ISO 13616 shape",
            )
        if iban_mod_97(canonical) != 1:
            raise DeadlineValidationError(
                f"refund-account iban {value!r} fails the mod-97 check",
            )
        return canonical


class ModeloIVAProfile(BaseModel):
    """IVA facts used by registry filing schedules.

    Attributes:
        roi_enrolled: Registered on the Registro de Operadores
            Intracomunitarios (ROI / VIES).
        oss_enrolled: Enrolled in the OSS / IOSS one-stop-shop regime.
        intracommunity_operations_exceed_50000_eur: Modelo 349 cadence
            threshold.
        sii_enrolled: Enrolled in the SII (Suministro Inmediato de
            Información) — the near-real-time IVA ledger-submission
            system created by RD 596/2016. Mandatory for the monthly
            IVA collective; voluntary for everyone else.
        redeme_enrolled: Registered in REDEME (Registro de Devolución
            Mensual del IVA) — one of the mandatory-SII triggers.
        refund_account: The encrypted cuenta-devolución refund account
            AEAT pays a Modelo 303 refund into. ``None`` when no refund
            account is on file; a refund disposition with no refund
            account is refused at export rather than emitting an empty
            DID block.
    """

    model_config = _STRICT_FROZEN

    roi_enrolled: bool = False
    oss_enrolled: bool = False
    intracommunity_operations_exceed_50000_eur: bool = False
    sii_enrolled: bool = False
    redeme_enrolled: bool = False
    refund_account: RefundAccount | None = None


class CrossPeriodGroupMemberRoster(BaseModel):
    """Expected member roster for a grouped cross-period dependency.

    The roster is profile state, not a calculation artefact: grouped
    aggregate modelos such as Modelo 353 must know the complete member
    population before they can prove that every required upstream member
    filing was reconciled and accepted.
    """

    model_config = _STRICT_FROZEN

    source_modelo: str = Field(default=Modelo.M322.value, min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: Period
    member_nifs: tuple[str, ...] = Field(min_length=1)

    @field_validator("member_nifs", mode="before")
    @classmethod
    def _coerce_member_nifs(cls, value: object) -> object:
        if isinstance(value, tuple):
            return value
        if isinstance(value, list | set | frozenset):
            return tuple(value)
        return value

    @field_validator("member_nifs")
    @classmethod
    def _validate_member_nifs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(str(item).strip().upper() for item in value)
        if any(not item for item in cleaned):
            raise DeadlineValidationError("cross-period group member NIFs must be non-blank")
        if len(set(cleaned)) != len(cleaned):
            raise DeadlineValidationError("cross-period group member NIFs must be unique")
        return tuple(sorted(cleaned))

    @model_validator(mode="after")
    def _validate_period_year_matches(self) -> CrossPeriodGroupMemberRoster:
        if self.period.year != self.filing_year:
            raise DeadlineValidationError(
                f"cross-period group roster filing_year {self.filing_year} "
                f"does not match period year {self.period.year}",
            )
        return self


def is_ue_eee_country_code(country_code: str | None) -> bool:
    """Return True when ``country_code`` is in the EU + EEA country set."""
    if country_code is None:
        return False
    return country_code.upper() in UE_EEA_COUNTRY_CODES


def irnr_representante_fiscal_required(country_code: str | None) -> bool:
    """Return True when an IRNR fiscal residence country requires representante fiscal."""
    return country_code is not None and not is_ue_eee_country_code(country_code)


class TaxpayerProfile(BaseModel):
    """The profile of a Spanish taxpayer for filing-deadline computation.

    Carries the structured three-axis taxpayer model — entity type,
    tax regime, and special enrolments — alongside the flat filing
    facts the deadline engine consumes today.

    Attributes:
        tax_id: NIF / NIE / CIF. Stored verbatim, no normalisation.
        entity_type: The taxpayer's entity type (natural person, legal
            entity, or attribution entity). ``None`` when the operator
            has not yet declared it.
        legal_entity_form: The recognised legal form when
            ``entity_type`` is ``LEGAL_ENTITY``; ``None`` otherwise.
        irpf_income_categories: The IRPF income categories a natural
            person declares (rendimientos). Empty when undeclared or
            when the taxpayer is not a natural person.
        irpf_estimation_regime: The IRPF estimation regime for
            economic-activity income. ``None`` when undeclared.
        iva_regime: The IVA regime the taxpayer files under.
        has_employees: Whether the taxpayer pays salaries with
            retención.
        pays_professionals_with_retencion: Whether the taxpayer pays
            professional fees subject to retención.
        professional_income_withholding_ge_70pct: Whether at least 70%
            of the taxpayer's prior-year professional income was
            already subject to withholding.
        pays_rent_with_retencion: Whether the taxpayer pays alquiler de
            local with retención.
        pays_capital_income_with_retencion: Whether the taxpayer pays
            capital-income rents subject to withholding.
        uses_objective_estimation_irpf: Whether the taxpayer computes
            IRPF economic-activity income under estimación objetiva.
            Kept in lockstep with ``irpf_estimation_regime``: when the
            regime is ``OBJETIVA`` this flag is forced ``True``. The
            registry ``schedule_predicates`` / ``model_selectors`` that
            test ``uses_objective_estimation_irpf`` still resolve.
        does_intracomunitario: Whether the taxpayer conducts
            operaciones intracomunitarias.
        third_party_transactions_above_347_threshold: Whether the
            profile exceeded the applicable third-party transaction
            threshold during the prior year.
        bienes_extranjero_above_threshold: Whether the taxpayer holds
            bienes en el extranjero above the legal threshold.
        iva: IVA-specific filing facts that can change filing cadence.
        cross_period_group_member_rosters: Expected group-member rosters
            keyed by upstream modelo, filing year, and period. These
            rosters let cross-period aggregate modelos prove complete
            member fan-in before verification, filing, or export.
        enrollment: AEAT enrollment facts that can change filing cadence.
        notes: Free-form notes for the user. Never consumed by the
            engine.
        irpf_special_regime: The IRPF special regime in effect for
            this taxpayer. ``None`` when undeclared (treated as
            ``GENERAL`` by engine consumers). ``IMPATRIADO`` activates
            the Ley Beckham path (LIRPF Art. 93): the CLI refuses
            Modelo 100 in favour of Modelo 151 and the obligation
            engine suppresses Modelo 100 deadlines.
        special_regime_start_date: The date of the opt-in election for
            the special regime. Required to compute the six-year window
            for ``IMPATRIADO`` (RIRPF Art. 116). ``None`` when
            undeclared or when ``irpf_special_regime`` is ``GENERAL``.
        fiscal_residency: Fiscal residency category. ``None`` treated as
            ``RESIDENT_IRPF`` by engine consumers. ``NON_RESIDENT_IRNR``
            routes the taxpayer to IRNR (TRLIRNR RDLeg 5/2004 Art. 2):
            the engine suppresses IRPF-resident deadlines and will
            activate IRNR obligations (Modelos 210/216/247) when
            their registry entries are wired.
        country_of_fiscal_residence: ISO 3166-1 alpha-2 code of the
            country of fiscal residence. Required when
            ``fiscal_residency`` is ``NON_RESIDENT_IRNR``; ``None`` is
            valid only for IRPF residents.
    """

    model_config = _STRICT_FROZEN

    tax_id: str = Field(min_length=1)
    entity_type: EntityType | None = None
    legal_entity_form: LegalEntityForm | None = None
    irpf_income_categories: frozenset[IrpfIncomeCategory] = frozenset()
    irpf_estimation_regime: IrpfEstimationRegime | None = None
    iva_regime: IVARegime
    has_employees: bool = False
    pays_professionals_with_retencion: bool = False
    professional_income_withholding_ge_70pct: bool = False
    pays_rent_with_retencion: bool = False
    pays_capital_income_with_retencion: bool = False
    uses_objective_estimation_irpf: bool = False
    objective_estimation_prior_year_gross_income_eur: Decimal | None = None
    objective_estimation_prior_year_invoice_gross_income_eur: Decimal | None = None
    objective_estimation_prior_year_purchases_eur: Decimal | None = None
    does_intracomunitario: bool = False
    third_party_transactions_above_347_threshold: bool = False
    bienes_extranjero_above_threshold: bool = False
    iva: ModeloIVAProfile = Field(default_factory=ModeloIVAProfile)
    cross_period_group_member_rosters: tuple[CrossPeriodGroupMemberRoster, ...] = Field(default_factory=tuple)
    enrollment: ModeloEnrollment = Field(default_factory=ModeloEnrollment)
    fiscal_address_cadastral_reference: str = ""
    fiscal_address_is_habitual_vivienda: bool = False
    activity_start_date: date | None = None
    activity_end_date: date | None = None
    incn_prior_12_months: Decimal | None = None
    new_entity_first_two_profit_periods: bool | None = None
    tributacion_estado_porcentaje: Decimal | None = None
    establecimiento_type: str = ""
    elected_withholding_pct: str = ""
    vivienda_office_total_m2: Decimal | None = None
    vivienda_office_office_m2: Decimal | None = None
    iae_epigraph: str = ""
    notes: str = ""
    irpf_special_regime: IrpfSpecialRegime | None = None
    special_regime_start_date: date | None = None
    fiscal_residency: FiscalResidency | None = None
    country_of_fiscal_residence: str | None = None
    representante_fiscal_nif: str | None = None
    """NIF/NIE of the fiscal representative in Spain.

    Required when ``fiscal_residency`` is ``NON_RESIDENT_IRNR`` and the
    country is outside the EU/EEA (Art. 47 LGT + Art. 10 TRLIRNR RDLeg 5/2004).
    """
    representante_fiscal_nombre: str | None = None
    """Full name of the fiscal representative in Spain.

    Required together with ``representante_fiscal_nif`` for the same cases.
    """
    sal_socios_trabajadores_count: int | None = None
    sal_reserva_especial_dotada: Decimal | None = None
    sal_capital_social: Decimal | None = None
    irpf_pagadores_count: int | None = None
    """Number of pagadores (income payers) the taxpayer received income from.

    When ``>= 2`` and ``irpf_pagadores_secondary_income > 1500``, filing
    Modelo 100 is mandatory under Art. 96.3 LIRPF regardless of the total
    income threshold. ``None`` when not declared (treated as "not known").
    """
    irpf_pagadores_secondary_income: Decimal | None = None
    """Sum of income received from the 2nd and subsequent pagadores.

    Art. 96.3 LIRPF: declaración obligatoria when this value exceeds
    €1,500. Only meaningful when ``irpf_pagadores_count >= 2``; ``None``
    when not declared.
    """
    days_in_spain: dict[int, int] = Field(default_factory=dict)
    """Days of physical presence in Spain per calendar year.

    Maps year (e.g. 2024) to number of days. Used to assess proximity to
    the Art. 9 LIRPF habitual residence threshold (183 days). The advisory
    ``RESIDENCY_BOUNDARY_NEAR`` is triggered when any declared year falls
    in the 150-215 day range -- close enough to the threshold that the
    operator should verify the actual count carefully.

    Recorded via ``--days-in-spain YYYY=NDAYS`` on the profile.
    """

    @field_validator("days_in_spain", mode="before")
    @classmethod
    def _coerce_days_in_spain_keys(cls, value: object) -> object:
        """Accept JSON-serialised ``dict[int, int]`` where keys arrive as strings.

        ``model_dump_json()`` serialises integer dict keys as JSON string keys
        (e.g. ``{"2024": 165}``). Without this coercion,
        ``model_validate_json`` would reject those string keys against the
        ``dict[int, int]`` annotation. Numeric-string keys are cast to ``int``
        here; non-numeric keys are left unchanged so the subsequent validation
        step reports them cleanly.
        """
        if not isinstance(value, dict):
            return value
        coerced: dict[object, object] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.isdigit():
                coerced[int(k)] = v
            else:
                coerced[k] = v
        return coerced

    @field_validator("cross_period_group_member_rosters", mode="before")
    @classmethod
    def _coerce_cross_period_group_member_rosters(cls, value: object) -> object:
        """Accept JSON arrays for the strict tuple roster field."""
        if isinstance(value, tuple):
            return value
        if isinstance(value, list | set | frozenset):
            return tuple(value)
        return value

    @field_validator("irpf_income_categories", mode="before")
    @classmethod
    def _coerce_income_categories(cls, value: object) -> object:
        """Accept any iterable of categories under strict mode.

        ``strict=True`` rejects a JSON array for a ``frozenset`` field,
        so a model loaded from ``model_dump_json`` would fail. Coercing
        a list / tuple / set into a ``frozenset`` here keeps the JSON
        persistence roundtrip loss-free while the field stays a typed,
        order-independent ``frozenset`` on the model.
        """
        if isinstance(value, frozenset):
            return value
        if isinstance(value, list | tuple | set):
            return frozenset(value)
        return value

    @field_validator(
        "objective_estimation_prior_year_gross_income_eur",
        "objective_estimation_prior_year_invoice_gross_income_eur",
        "objective_estimation_prior_year_purchases_eur",
        mode="before",
    )
    @classmethod
    def _coerce_objective_estimation_decimal(cls, value: object) -> object:
        """Accept JSON-serialised Decimals for declared EO volume facts."""
        if value is None or isinstance(value, Decimal):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return Decimal(stripped)
            except InvalidOperation as exc:
                raise DeadlineValidationError(
                    "objective-estimation declared volume must be a decimal"
                ) from exc
        return value

    @model_validator(mode="after")
    def _check_objective_estimation_consistency(self) -> Self:
        """Reject a regime that contradicts ``uses_objective_estimation_irpf``.

        ``irpf_estimation_regime`` is the structured tax-regime axis;
        ``uses_objective_estimation_irpf`` is the legacy boolean that
        the registry ``schedule_predicates`` and ``model_selectors``
        still test. The two must not contradict: a non-objective
        regime declared together with a ``True`` boolean is rejected,
        and an ``OBJETIVA`` regime declared with a ``False`` boolean is
        rejected. The boolean is *derived* from the regime by the
        ``mode="before"`` validator below, so this check only fires
        when a caller bypasses that derivation. When the regime is
        undeclared the boolean is left untouched so existing profiles
        keep working until the engine is rewired.
        """
        regime = self.irpf_estimation_regime
        if regime is None:
            return self
        wants_objective = regime is IrpfEstimationRegime.OBJETIVA
        if wants_objective != self.uses_objective_estimation_irpf:
            raise DeadlineValidationError(
                f"irpf_estimation_regime {regime.value!r} contradicts "
                f"uses_objective_estimation_irpf={self.uses_objective_estimation_irpf}; "
                "the objective-estimation boolean must be True only for the "
                "OBJETIVA regime",
            )
        return self

    @model_validator(mode="after")
    def _check_impatriado_requires_start_date(self) -> Self:
        """Reject an IMPATRIADO regime declared without a start date.

        The six-year Beckham window (RIRPF Art. 116) cannot be computed
        without the opt-in election date. Any caller that constructs an
        IMPATRIADO profile without a ``special_regime_start_date`` has an
        incomplete model — reject it at the boundary so downstream
        consumers never see a nil start date for an active impatriado.
        """
        if self.irpf_special_regime is IrpfSpecialRegime.IMPATRIADO and self.special_regime_start_date is None:
            raise DeadlineValidationError(
                "special_regime_start_date is required when "
                "irpf_special_regime is IMPATRIADO (Art. 93 LIRPF / RIRPF Art. 116)",
            )
        return self

    @model_validator(mode="after")
    def _check_non_resident_requires_country(self) -> Self:
        """Reject a NON_RESIDENT_IRNR profile declared without a country code.

        The IRNR regime (TRLIRNR RDLeg 5/2004 Art. 2) is defined by the
        absence of habitual residence in Spain; the country of actual fiscal
        residence is therefore mandatory for any meaningful downstream
        computation (EU/EEA status, convenio lookup, Modelo 210 routing).
        """
        if self.fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR and self.country_of_fiscal_residence is None:
            raise DeadlineValidationError(
                "country_of_fiscal_residence is required when "
                "fiscal_residency is NON_RESIDENT_IRNR (TRLIRNR RDLeg 5/2004 Art. 2)",
            )
        return self

    @model_validator(mode="after")
    def _check_representante_fiscal_required(self) -> Self:
        """Require a fiscal representative for non-EU/EEA non-residents.

        Art. 47 LGT + Art. 10 TRLIRNR RDLeg 5/2004: taxpayers fiscally
        resident outside the EU/EEA (and outside Spain) must appoint a
        representative in Spain. Both NIF and name are required together;
        partial declaration is rejected.
        """
        if (
            self.fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR
            and irnr_representante_fiscal_required(self.country_of_fiscal_residence)
        ):
            nif_missing = self.representante_fiscal_nif is None
            nombre_missing = self.representante_fiscal_nombre is None
            if nif_missing or nombre_missing:
                missing = []
                if nif_missing:
                    missing.append("representante_fiscal_nif")
                if nombre_missing:
                    missing.append("representante_fiscal_nombre")
                raise DeadlineValidationError(
                    f"{' and '.join(missing)} required for non-EU/EEA non-resident "
                    "(Art. 47 LGT + Art. 10 TRLIRNR RDLeg 5/2004)",
                )
        return self

    @model_validator(mode="before")
    @classmethod
    def _derive_objective_estimation_flag(cls, data: object) -> object:
        """Derive ``uses_objective_estimation_irpf`` from the regime axis.

        When the structured ``irpf_estimation_regime`` is supplied
        without an explicit ``uses_objective_estimation_irpf``, the
        boolean is set from the regime (``OBJETIVA`` ⇒ ``True``) so the
        registry conditions that still test the boolean keep resolving
        correctly. An explicit boolean is left in place for the
        consistency check above to adjudicate.
        """
        if not isinstance(data, dict):
            return data
        data_map: dict[object, object] = {k: v for k, v in data.items()}
        regime = data_map.get("irpf_estimation_regime")
        if regime is None or "uses_objective_estimation_irpf" in data:
            return data
        parsed = regime if isinstance(regime, IrpfEstimationRegime) else IrpfEstimationRegime(regime)
        derived = dict(data)
        derived["uses_objective_estimation_irpf"] = parsed is IrpfEstimationRegime.OBJETIVA
        return derived

    def beckham_window_active(self, today: date) -> bool:
        """Return True if the Beckham window (Art. 93 LIRPF) is active on *today*.

        The window covers the year of election and the following five
        calendar years — six years total (RIRPF Art. 116.1). Year-7 and
        beyond return False; the taxpayer reverts to the general IRPF regime.
        Returns False for any non-IMPATRIADO profile regardless of date.

        Args:
            today: Reference date for the window check (caller supplies
                ``date.today()`` in production; tests supply a fixed date).

        Returns:
            True only when ``irpf_special_regime is IMPATRIADO`` and
            ``start_date.year <= today.year <= start_date.year + 5``.
        """
        if self.irpf_special_regime is not IrpfSpecialRegime.IMPATRIADO or self.special_regime_start_date is None:
            return False
        return self.special_regime_start_date.year <= today.year <= self.special_regime_start_date.year + 5

    @property
    def ue_eee_status(self) -> bool:
        """True when ``country_of_fiscal_residence`` is in the EU + EEA (post-Brexit).

        ``GB`` is excluded from 2021-01-01 (Brexit transition end).
        Returns ``False`` when ``country_of_fiscal_residence`` is ``None``
        (i.e., for IRPF-resident profiles).
        """
        if self.country_of_fiscal_residence is None:
            return False
        return is_ue_eee_country_code(self.country_of_fiscal_residence)

    @property
    def convenio_aplicable(self) -> str | None:
        """BOE reference for the applicable double-taxation treaty, or ``None``.

        Derived from ``country_of_fiscal_residence`` via a static lookup
        of treaties signed by Spain. Returns ``None`` when no treaty is
        registered for the country or when the country is not set.

        The lookup covers treaties that are most frequently encountered
        in IRNR practice; it is not exhaustive. The BOE identifiers
        follow the ``BOE-A-YYYY-NNNNN`` scheme used in the official Boletín
        Oficial del Estado. References:
        - España-UK: BOE-A-2014-5171
        - España-Alemania: BOE-A-2012-3669
        - España-Francia: BOE-A-1997-21331
        - España-EE.UU.: BOE-A-1990-28246
        - España-Países Bajos: BOE-A-1972-674
        - España-Marruecos: BOE-A-1985-9280
        """
        if self.country_of_fiscal_residence is None:
            return None
        return _CONVENIO_BY_COUNTRY.get(self.country_of_fiscal_residence.upper())

    @property
    def residency_boundary_near(self) -> bool:
        """True when any declared year's presence count falls in the 150-215 day window.

        Art. 9 LIRPF: habitual residence in Spain is presumed when the
        taxpayer is present for more than 183 days in a calendar year.
        Days 150-215 form a boundary zone where the actual residency
        determination requires careful verification -- either because the
        taxpayer may cross the threshold (150-182) or because they already
        exceed it but by a modest margin (184-215) that could be disputed.

        Returns ``False`` when ``days_in_spain`` is empty.
        """
        return any(150 <= days <= 215 for days in self.days_in_spain.values())


_MULTIPLE_PAGADORES_SECONDARY_THRESHOLD = MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR


def evaluate_multiple_pagadores_obligation(
    pagadores_count: int | None,
    secondary_income: Decimal | None,
) -> bool:
    """Return True when Art. 96.3 LIRPF mandates Modelo 100 filing.

    Art. 96.3 LIRPF (Ley 35/2006) establishes that a natural person whose
    rendimientos del trabajo come from more than one pagador is obliged to
    file if the aggregate income received from the 2nd and subsequent
    pagadores exceeds €1,500. The rule applies independently of the general
    income thresholds in Art. 96.2.

    Args:
        pagadores_count: Number of pagadores the taxpayer received work
            income from during the year. ``None`` means undeclared.
        secondary_income: Sum of income from the 2nd and subsequent
            pagadores. ``None`` means undeclared.

    Returns:
        ``True`` when both conditions are confirmed (count >= 2 AND
        secondary_income > 1,500); ``False`` in every other case,
        including when either value is undeclared.
    """
    if pagadores_count is None or secondary_income is None:
        return False
    return pagadores_count >= 2 and secondary_income > _MULTIPLE_PAGADORES_SECONDARY_THRESHOLD


# Static lookup: ISO 3166-1 alpha-2 → BOE reference for double-taxation treaties
# signed by Spain. Source: AEAT Convenios de doble imposición.
_CONVENIO_BY_COUNTRY: dict[str, str] = {
    "GB": "BOE-A-2014-5171 España-UK",
    "DE": "BOE-A-2012-3669 España-Alemania",
    "FR": "BOE-A-1997-21331 España-Francia",
    "US": "BOE-A-1990-28246 España-EE.UU.",
    "NL": "BOE-A-1972-674 España-Países Bajos",
    "MA": "BOE-A-1985-9280 España-Marruecos",
}


class RecargoBand(BaseModel):
    """One Ley 58/2003 art-27 recargo band loaded from the registry TOML.

    The bracket table at
    ``registry/aeat/legal/ley-58-2003-recargo-bands.toml`` carries the
    surcharge schedule for self-assessments filed after the deadline
    without prior AEAT notice. Each row materialises into one
    :class:`RecargoBand`; the :class:`Recovery` value attached to an
    OVERDUE :class:`ModeloDeadline` references the resolved band
    by ``id``.

    Attributes:
        id: Stable identifier (``completed_months_0``, ``after_12_months``,
            ...). Used by the CLI for per-band rendering.
        min_completed_months: Inclusive lower bound on the completed-months
            window this band covers. Art. 27.2 LGT counts only COMPLETED
            months of delay; a fractional month does not count.
        max_completed_months: Inclusive upper bound, or ``None`` for the
            open-ended ``after_12_months`` band.
        surcharge_pct: Recargo percentage applied on the cuota.
        interest_applies: True only for the after-12-months band; the
            CLI renders the interest hint when set.
        legal_ref: Stable corpus reference (``ley-58-2003:art-27.2``).
    """

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1, max_length=64)
    min_completed_months: int = Field(ge=0)
    max_completed_months: int | None = None
    surcharge_pct: Decimal
    interest_applies: bool = False
    legal_ref: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _validate_window(self) -> Self:
        if self.max_completed_months is not None and self.max_completed_months < self.min_completed_months:
            raise DeadlineValidationError(
                f"RecargoBand {self.id}: max_completed_months ({self.max_completed_months}) "
                f"is below min_completed_months ({self.min_completed_months})",
            )
        return self


class Recovery(BaseModel):
    r"""Operator-facing recovery payload attached to an OVERDUE obligation.

    Surfaces the resolved Ley 58/2003 art-27 recargo band plus a runnable
    next-action command the operator can copy. The CLI's calendar
    renderer surfaces ``recovery\\t<band_id>\\t<surcharge_pct>%\\t<next_command>``
    underneath each OVERDUE entry.

    Attributes:
        still_filable: True for every band -- art-27 self-assessments
            remain admissible past the original deadline; the surcharge
            is the only consequence. The flag exists so a future band
            for absolutely-time-barred filings can be added without
            reshaping the model.
        recargo_band: The :class:`RecargoBand` resolved from the
            completed-months window (Art. 27.2 LGT).
        legal_ref: Same as ``recargo_band.legal_ref``; carried at the
            top level so renderers do not dereference.
        next_command: Literal shell command the operator can copy to
            calculate the late filing.
    """

    model_config = _STRICT_FROZEN

    still_filable: bool = True
    recargo_band: RecargoBand
    legal_ref: str = Field(min_length=1, max_length=128)
    next_command: str = Field(min_length=1, max_length=256)


def _parse_modelo_deadline_period(value: object) -> Period:
    """Coerce runtime or persisted periods into :class:`~aeat.core.Period`.

    Runtime producers pass :class:`~aeat.core.Period`; JSON persistence
    restores it from ``{"filing_year": ..., "code": ...}``.
    """
    if isinstance(value, Period):
        return value
    if isinstance(value, dict):
        return Period.model_validate(value)
    raise ValueError(f"deadline period must be a Period or period dict, got {type(value).__name__}")


class ModeloDeadline(BaseModel):
    """A single filing obligation in a :class:`Schedule`.

    Attributes:
        modelo: The modelo string identifier; carried as a plain
            ``str`` on this record so JSON round-tripping is loss-free
            for downstream consumers.
        period: The period covered as a typed :class:`~aeat.core.Period`
            (e.g. ``Period.from_year_and_code(2026, "1T")``).
        opens_on: The first day the AEAT filing window accepts the
            modelo for this period.
        closes_on: The last day the AEAT filing window accepts the
            modelo for this period.
        payment_cutoff_on: The cutoff for direct-debit payment, if
            applicable. ``None`` when there is no payment leg.
        status: The :class:`ObligationStatus` against the reference
            ``today`` used by :meth:`DeadlineEngine.compute`.
        applies_because: Human-readable explanation of why the profile
            is obliged to file this modelo, resolved from the registry
            deadline applicability rule.
        boe_references: Tuple of opaque BOE / Manual práctico citation
            keys. Stable identifiers, never URLs.
        recovery: Resolved :class:`Recovery` payload when ``status`` is
            ``OVERDUE``; ``None`` for every other status. Populated by
            the deadline engine using the days-late window and the
            registry's recargo bracket table.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1)
    period: Annotated[Period, BeforeValidator(_parse_modelo_deadline_period)]
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    status: ObligationStatus
    applies_because: str = Field(min_length=1)
    boe_references: tuple[str, ...] = Field(default_factory=tuple)
    recovery: Recovery | None = None

    @model_validator(mode="after")
    def _check_window_order(self) -> ModeloDeadline:
        """Reject obligations whose ``opens_on`` is after ``closes_on``."""
        if self.opens_on > self.closes_on:
            raise DeadlineValidationError(f"opens_on ({self.opens_on}) is after closes_on ({self.closes_on})")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise DeadlineValidationError(
                f"payment_cutoff_on ({self.payment_cutoff_on}) is after closes_on ({self.closes_on})",
            )
        return self


class Schedule(BaseModel):
    """The full filing schedule for an autónomo for a given year.

    Attributes:
        profile: The :class:`TaxpayerProfile` the schedule was computed
            for.
        year: The target year.
        obligations: Tuple of :class:`ModeloDeadline` ordered by
            ``(closes_on, modelo, period)``.
        generated_at: UTC timestamp of when :meth:`DeadlineEngine.compute`
            built this schedule. The only non-deterministic field.
    """

    model_config = _STRICT_FROZEN

    profile: TaxpayerProfile
    year: int = Field(ge=1900, le=2999)
    obligations: tuple[ModeloDeadline, ...]
    generated_at: datetime
