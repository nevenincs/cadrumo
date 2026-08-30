"""Pydantic v2 strict models for the :mod:`cadrumo.domain.deadlines` subpackage.

Every type that crosses a public boundary lives here as a strict, frozen
:class:`pydantic.BaseModel` (or :class:`enum.StrEnum` for closed
enumerations). No dataclasses; no bare ``dict[str, Any]``.

Consumed by :class:`cadrumo.domain.deadlines.DeadlineEngine` and re-exported
from :mod:`cadrumo.domain.deadlines`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from ...core import (
    IBAN_SHAPE_RE,
    OBJECT_TUPLE_ADAPTER,
    Modelo,
    Period,
    ThirdPartyDeclarationRole,
    iban_mod_97,
    normalise_iban,
)
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import (
    MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR,
    WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR,
)
from ...core.filing_year import FilingYear
from ...core.identity import SubjectTaxId
from ...core.time import UtcInstant, validate_utc_aware
from ..contribuyente.renta_codes import UE_EEA_COUNTRY_CODES, FiscalResidency
from .errors import DeadlineValidationError


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
        NO_APLICA: Internal projection sentinel for profiles that are
            not enrolled in IVA.
    """

    GENERAL = "GENERAL"
    SIMPLIFICADO = "SIMPLIFICADO"
    RECARGO_EQUIVALENCIA = "RECARGO_EQUIVALENCIA"
    REAGP = "REAGP"
    EXENTO = "EXENTO"
    NO_APLICA = "NO_APLICA"


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


class IrpfActivityKind(StrEnum):
    """Whether the taxpayer's activity is professional or sectorial, for retención.

    An ACTIVITY axis, independent of :class:`IrpfEstimationRegime` (a method)
    and :class:`IrpfIncomeCategory` (a rendimiento type). The independence is
    the reason it has to exist separately: a farmer may file estimación directa
    and sit in IVA general, so neither of those establishes the activity.

    Deliberately TWO members, and the narrowness is grounded rather than
    conservative. RIRPF art. 95 (RD 439/2007) states seven provisions that fix
    only FOUR distinct rates, and six of the seven sit in rate-identical pairs:
    inicio and the colectivos específicos both fix 7 %, agrícola/ganadera and
    forestal both 2 %, engorde de porcino/avicultura and estimación objetiva
    both 1 %. Only the 15 % general professional rate has a single legal source.
    So the one distinction the rate table can consume is professional
    (15 % / 7 %) against sectorial (2 % / 1 %); a member per activity would
    spend names on splits that select the same figure and then have to be kept
    true.

    Operator-declared OR derived, and the derivation now exists. This paragraph
    used to say the authority was there but the input was missing, which was true
    when it was written: the bundled Modelo 036 instrucciones carry the
    tipo-de-actividad code table and the sentence binding each IAE sección to its
    activity class -- exactly the granularity RIRPF art. 95.2.a keys on ("las
    actividades incluidas en las Secciones Segunda y Tercera") -- and the
    correspondence is registry data as the ``rirpf-art-95:selector-m036-*``
    parameters, with their own ``legal_refs`` rather than an if-chain. What was
    absent was a field holding a code.

    A ledger row now holds one. :func:`~domain.transactions.irpf_activity_kind_for`
    reads the registry selectors and returns a member of THIS enum, deliberately
    rather than a second classifier of its own: the apartado-level detail that
    agrícola/ganadera comes from art. 95.4.2.º and forestal from art. 95.5, both
    yielding 2 %, stays on the registry parameters where its ``legal_refs`` live.

    One limit is declared rather than latent. The Modelo 036 table's finest
    ganadero grain is B02, so the art. 95.4.1.º engorde de porcino/avicultura
    carve-out is not selectable and its parameter carries a deliberately EMPTY
    code set; both it and the general agrarian case return ``SECTORIAL``, which is
    right for both, and which of the two sectoral figures applies is not settled
    from this axis. ``iae_epigraph`` cannot narrow it either: the same
    instrucciones state the epígrafe is filled "solo para las actividades
    comprendidas dentro de los códigos de actividad A01, A02, A03, A04 y A05", so
    it is blank for precisely the B-series agrarian filers.

    KNOWN GAP in the two-member shape. Four of the ten codes -- A01 Arrendadores,
    A03 Resto empresariales, B04 Producción de mejillón, B05 Pesquera -- select
    NO art. 95 partition, so they are absent from every selector rather than
    forced into an arm. This enum cannot say that: ``None`` currently means
    "undeclared", and an empresarial filer for whom no activity rate applies is
    a different fact with different fail-closed behaviour. Whether that wants a
    third member or a different shape depends on what ends up reading the field,
    which is not settled while the field has no production consumer.

    Attributes:
        PROFESIONAL: An actividad profesional under RIRPF art. 95.1 --
            the 15 % general rate, or 7 % under the inicio or
            colectivos-específicos arms.
        SECTORIAL: An actividad agrícola, ganadera or forestal, or one whose
            rendimiento neto is determined by estimación objetiva -- RIRPF
            art. 95.4, 95.5 and 95.6.1.º, fixing 2 % or 1 %.
    """

    PROFESIONAL = "profesional"
    SECTORIAL = "sectorial"


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
    ``CADRUMO_DEADLINE_DUE_SOON_DAYS`` setting (default 14 days).
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

    Refund-only. AEAT's DR303 position 23 is a single dual-purpose field
    labelled ``Domiciliación/Devolución - IBAN``, so the record has somewhere to
    state a charge account too -- but this profile carries no separate charge
    account, and the export path must not infer one by reusing this account for
    a domiciliación del ingreso: nominating an account to RECEIVE a refund is
    not an authorisation to DEBIT it. The export path refuses that election
    unconditionally rather than make the inference.

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
        canonical = normalise_iban(value)
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


class ChargeAccount(BaseModel):
    """The cuenta de cargo AEAT may debit for a Modelo 303 domiciliación.

    This is deliberately distinct from :class:`RefundAccount`.  The DR303 DID
    page has one IBAN position labelled ``Domiciliación/Devolución - IBAN``,
    but that is a slot chosen by the filing's disposition, not authority to
    infer that a refund destination may be debited.  A charge account therefore
    contains exactly the affirmative debit instruction the operator recorded:
    one IBAN and no refund-only SWIFT, foreign-bank, or SEPA-mark fields.

    Like the refund account, this financial identity data exists only in the
    encrypted secure-object store and is read transiently when the export is
    composed.  It is never logged or copied to a plaintext side store.

    Attributes:
        iban: The authorised debit-account IBAN, canonicalised to the ISO 13616
            whitespace- and hyphen-stripped upper-case form.
    """

    model_config = _STRICT_FROZEN

    iban: str

    @field_validator("iban", mode="before")
    @classmethod
    def _validate_iban(cls, value: object) -> object:
        """Reject an absent or malformed debit-account IBAN at the domain boundary."""
        if not isinstance(value, str):
            raise DeadlineValidationError("charge-account iban must be a string")
        canonical = normalise_iban(value)
        if not canonical:
            raise DeadlineValidationError("charge-account iban must not be blank")
        if not IBAN_SHAPE_RE.match(canonical):
            raise DeadlineValidationError(
                f"charge-account iban {value!r} does not match the ISO 13616 shape",
            )
        if iban_mod_97(canonical) != 1:
            raise DeadlineValidationError(
                f"charge-account iban {value!r} fails the mod-97 check",
            )
        return canonical


class M303TaxTerritory(StrEnum):
    """Exclusive tax-territory authority for Modelo 303 identification."""

    COMMON_REGIME = "common_regime"
    FORAL = "foral_unsupported"


class M303RegimeComposition(StrEnum):
    """Closed composition of IVA regimes declared for Modelo 303."""

    GENERAL = "general"
    SIMPLIFIED = "simplified"
    MIXED = "mixed"


class ModeloIVAProfile(BaseModel):
    """IVA facts used by registry filing schedules.

    Attributes:
        roi_enrolled: Registered on the Registro de Operadores
            Intracomunitarios (ROI / VIES).
        oss_enrolled: Enrolled in the OSS / IOSS one-stop-shop regime.
        group_member_enrolled: Enrolled as a member entity in the IVA
            group-of-entities special regime; this is the Modelo 322
            role.
        group_dominant_entity_enrolled: Enrolled as the dominant
            entity of an IVA group-of-entities regime; this is the
            Modelo 353 role.
        intracommunity_operations_exceed_50000_eur: Modelo 349 cadence
            threshold.
        sii_enrolled: Enrolled in the SII (Suministro Inmediato de
            Información) — the near-real-time IVA ledger-submission
            system created by RD 596/2016. Mandatory for the monthly
            IVA collective; voluntary for everyone else. This records
            SII membership only; Modelo 303 monthly cadence is driven by
            monthly-liquidation facts such as REDEME or large-company
            status, not by voluntary SII alone.
        redeme_enrolled: Registered in REDEME (Registro de Devolución
            Mensual del IVA) — one of the mandatory-SII triggers.
        refund_account: The encrypted cuenta-devolución refund account
            AEAT pays a Modelo 303 refund into. ``None`` when no refund
            account is on file; a refund disposition with no refund
            account is refused at export rather than emitting an empty
            DID block.
        charge_account: The encrypted cuenta de cargo AEAT may debit when
            the operator elects domiciliación del ingreso. It is intentionally
            separate from ``refund_account``; a U export with no recorded
            charge account is refused rather than reusing a refund destination.
    """

    model_config = _STRICT_FROZEN

    tax_territory: M303TaxTerritory
    regime_composition: M303RegimeComposition
    roi_enrolled: bool = False
    oss_enrolled: bool = False
    group_member_enrolled: bool = False
    group_dominant_entity_enrolled: bool = False
    intracommunity_operations_exceed_50000_eur: bool = False
    sii_enrolled: bool = False
    redeme_enrolled: bool
    cash_accounting_regime_enrolled: bool
    voluntary_sii_enrolled: bool
    hydrocarbon_deposit_advance_payment_deduction_entitled: bool
    refund_account: RefundAccount | None = None
    charge_account: ChargeAccount | None = None


def _parse_modelo_identifier(value: object) -> Modelo:
    """Coerce a canonical modelo token into the closed Modelo enum."""
    if isinstance(value, Modelo):
        return value
    if isinstance(value, str):
        try:
            return Modelo(value)
        except ValueError as exc:
            raise DeadlineValidationError(f"modelo identifier {value!r} is not a supported AEAT modelo") from exc
    raise DeadlineValidationError(f"modelo identifier must be a string or Modelo, got {type(value).__name__}")


class CrossPeriodGroupMemberRoster(BaseModel):
    """Expected member roster for a grouped cross-period dependency.

    The roster is profile state, not a calculation artefact: grouped
    aggregate modelos such as Modelo 353 must know the complete member
    population before they can prove that every required upstream member
    filing was reconciled and accepted.
    """

    model_config = _STRICT_FROZEN

    source_modelo: Annotated[Modelo, BeforeValidator(_parse_modelo_identifier)] = Modelo.M322
    filing_year: FilingYear
    period: Period
    member_nifs: tuple[SubjectTaxId, ...] = Field(min_length=1)

    @field_validator("member_nifs", mode="before")
    @classmethod
    def _coerce_member_nifs(cls, value: object) -> object:
        if isinstance(value, tuple):
            tuple_validated: tuple[object, ...] = OBJECT_TUPLE_ADAPTER.validate_python(value)
            return tuple_validated
        if isinstance(value, list | set | frozenset):
            sequence_validated: tuple[object, ...] = OBJECT_TUPLE_ADAPTER.validate_python(value)
            return sequence_validated
        return value

    @field_validator("member_nifs")
    @classmethod
    def _validate_member_nifs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject duplicate members and give the roster a stable order.

        Each entry has already passed the canonical :data:`SubjectTaxId`
        contract, which trims, uppercases, and runs the AEAT checksum, so this
        validator only enforces the roster-level invariants. Deduplication must
        run after that normalisation: two spellings of one member would
        otherwise both count towards the expected fan-in.
        """
        if len(set(value)) != len(value):
            raise DeadlineValidationError("cross-period group member NIFs must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _validate_period_year_matches(self) -> CrossPeriodGroupMemberRoster:
        if self.period.filing_year != self.filing_year:
            raise DeadlineValidationError(
                f"cross-period group roster filing_year {self.filing_year} "
                f"does not match period year {self.period.filing_year}",
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
        tax_id: NIF / NIE / CIF, validated and normalised through the
            canonical :data:`SubjectTaxId` contract. Deadline computation
            and imported schedule state carry this identity, so it runs
            the AEAT checksum here rather than trusting an adjacent
            boundary to have run it.
        entity_type: The taxpayer's entity type (natural person, legal
            entity, or attribution entity). ``None`` when the operator
            has not yet declared it.
        declaration_roles: The filer's :class:`~core.ThirdPartyDeclarationRole`
            memberships -- orthogonal to ``entity_type`` and independent of
            it. Drives Modelo 347 claves C, D and E; empty when the operator
            has not declared any such role, which is the correct default
            for the overwhelming majority of filers.
        legal_entity_form: The recognised legal form when
            ``entity_type`` is ``LEGAL_ENTITY``; ``None`` otherwise.
        irpf_income_categories: The IRPF income categories a natural
            person declares (rendimientos). Empty when undeclared or
            when the taxpayer is not a natural person.
        irpf_estimation_regime: The IRPF estimation regime for
            economic-activity income. ``None`` when undeclared.
        irpf_activity_kind: Whether the economic activity is
            profesional or sectorial, for the RIRPF art. 95
            retención rate. Operator-declared and independent of
            the estimation regime. ``None`` when undeclared, which
            a consumer MUST treat as unknown rather than as either
            arm -- the wrong arm is 15 % against 2 %.
        iva_regime: The IVA regime the taxpayer files under.
        has_employees: Whether the taxpayer pays salaries with
            retención.
        colegio_concertado: Whether the withholder is a colegio concertado,
            which Modelo 111 declares in its own header field. ``None`` when
            undeclared: the producer refuses to file the modelo on an
            undeclared value rather than assert "not a concerted school" on
            the operator's behalf.
        pays_professionals_with_retencion: Whether the taxpayer pays
            professional fees subject to retención.
        professional_income_withholding_ge_70pct: Whether at least 70%
            of the taxpayer's prior-year professional income was
            already subject to withholding.
        art109_activity_income_withholding_ge_70pct: Whether the Art. 109
            RIRPF 70% income-coverage exception is met for covered
            professional, agricultural, livestock, or forestry activity
            income. For activity-start cases this is the current payment
            period coverage fact rather than a prior-year fact.
        pays_rent_with_retencion: Whether the taxpayer pays alquiler de
            local with retención.
        pays_capital_income_with_retencion: Whether the taxpayer pays
            capital-income rents subject to withholding.
        member_of_large_multinational_group: Whether the entity is the
            reporting parent of a multinational group above the
            country-by-country reporting threshold (Modelo 231).
        eu_business_seeking_spanish_iva_refund: Whether the taxpayer is
            an EU-established business, not established in Spanish IVA
            territory, requesting a refund of Spanish input IVA (Modelo
            361).
        reports_client_securities_insurance_annuities: Whether the entity
            is a financial or insurance intermediary that must report
            client securities, insurance and annuities (Modelo 189).
        does_intracomunitario: Whether the taxpayer conducts
            operaciones intracomunitarias.
        third_party_transactions_above_347_threshold: Whether the
            profile exceeded the applicable third-party transaction
            threshold during the prior year.
        bienes_extranjero_above_threshold: Whether the taxpayer holds
            bienes en el extranjero above the legal threshold.
        monedas_virtuales_extranjero_above_threshold: Whether the
            taxpayer holds virtual currencies abroad above the Modelo
            721 threshold.
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
        ley_49_2002_special_regime_option_declared: Whether the entity
            has declared the Modelo 036 option for the Title II Ley
            49/2002 special fiscal regime. ``None`` means undeclared.
        ley_49_2002_special_regime_option_date: Date declared for that
            option on Modelo 036. ``None`` means undeclared.
        ley_49_2002_special_regime_renunciation_declared: Whether the
            entity has declared renunciation of the Title II Ley
            49/2002 special regime. ``None`` means undeclared.
        ley_49_2002_special_regime_renunciation_date: Date declared
            for that renunciation on Modelo 036. ``None`` means
            undeclared.
    """

    model_config = _STRICT_FROZEN

    tax_id: SubjectTaxId
    entity_type: EntityType | None = None
    declaration_roles: frozenset[ThirdPartyDeclarationRole] = frozenset()
    legal_entity_form: LegalEntityForm | None = None
    irpf_income_categories: frozenset[IrpfIncomeCategory] = frozenset()
    irpf_estimation_regime: IrpfEstimationRegime | None = None
    irpf_activity_kind: IrpfActivityKind | None = None
    iva_regime: IVARegime
    has_employees: bool = False
    colegio_concertado: bool | None = None
    pays_professionals_with_retencion: bool = False
    professional_income_withholding_ge_70pct: bool = False
    art109_activity_income_withholding_ge_70pct: bool = False
    pays_rent_with_retencion: bool = False
    pays_capital_income_with_retencion: bool = False
    objective_estimation_prior_year_gross_income_eur: Decimal | None = None
    objective_estimation_prior_year_invoice_gross_income_eur: Decimal | None = None
    objective_estimation_prior_year_agri_livestock_forest_gross_eur: Decimal | None = None
    objective_estimation_prior_year_purchases_eur: Decimal | None = None
    objective_estimation_modulos_iae_epigraph: str = ""
    objective_estimation_modulos_module_1_units: Decimal | None = None
    objective_estimation_modulos_module_2_units: Decimal | None = None
    objective_estimation_modulos_module_3_units: Decimal | None = None
    objective_estimation_modulos_module_4_units: Decimal | None = None
    objective_estimation_modulos_module_5_units: Decimal | None = None
    objective_estimation_modulos_module_6_units: Decimal | None = None
    objective_estimation_modulos_module_7_units: Decimal | None = None
    does_intracomunitario: bool = False
    third_party_transactions_above_347_threshold: bool = False
    bienes_extranjero_above_threshold: bool = False
    monedas_virtuales_extranjero_above_threshold: bool = False
    iva: ModeloIVAProfile | None = None
    cross_period_group_member_rosters: tuple[CrossPeriodGroupMemberRoster, ...] = Field(default_factory=tuple)
    enrollment: ModeloEnrollment = Field(default_factory=ModeloEnrollment)
    fiscal_address_cadastral_reference: str = ""
    fiscal_address_is_habitual_vivienda: bool = False
    activity_start_date: date | None = None
    activity_end_date: date | None = None
    incn_prior_12_months: Decimal | None = None
    new_entity_first_two_profit_periods: bool | None = None
    ley_49_2002_special_regime_option_declared: bool | None = None
    ley_49_2002_special_regime_option_date: date | None = None
    ley_49_2002_special_regime_renunciation_declared: bool | None = None
    ley_49_2002_special_regime_renunciation_date: date | None = None
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

    Art. 96.3 LIRPF: when ``irpf_pagadores_count >= 2`` and this value
    exceeds €1,500, the work-income filing-exemption limit drops from the
    general €22,000 to the per-year reduced limit. Only meaningful when
    ``irpf_pagadores_count >= 2``; ``None`` when not declared.
    """
    irpf_pagadores_total_work_income: Decimal | None = None
    """Total rendimientos íntegros del trabajo for the year (all pagadores).

    Art. 96.2.a)/96.3 LIRPF: a Modelo 100 filing obligation arises when this
    total exceeds the applicable exemption limit — the general €22,000, or the
    per-year reduced limit (€15,876 for 2024 onward) when the multiple-pagadores
    condition is met. ``None`` when not declared, in which case a triggered
    multiple-pagadores condition surfaces a conservative advisory.
    """

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
        if self.fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR and irnr_representante_fiscal_required(
            self.country_of_fiscal_residence
        ):
            nif_missing = self.representante_fiscal_nif is None
            nombre_missing = self.representante_fiscal_nombre is None
            if nif_missing or nombre_missing:
                missing: list[str] = []
                if nif_missing:
                    missing.append("representante_fiscal_nif")
                if nombre_missing:
                    missing.append("representante_fiscal_nombre")
                raise DeadlineValidationError(
                    f"{' and '.join(missing)} required for non-EU/EEA non-resident "
                    "(Art. 47 LGT + Art. 10 TRLIRNR RDLeg 5/2004)",
                )
        return self

    def beckham_window_active(self, today: date) -> bool:
        """Return True if the Beckham window (Art. 93 LIRPF) is active on *today*.

        The window covers the year of election and the following five
        calendar years — six years total (RIRPF Art. 116.1). Year-7 and
        beyond return False; the taxpayer reverts to the general IRPF regime.
        Returns False for any non-IMPATRIADO profile regardless of date.

        Args:
            today: Reference date for the window check (caller supplies
                the canonical Europe/Madrid civil date in production; tests
                supply a fixed date).

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


_MULTIPLE_PAGADORES_SECONDARY_THRESHOLD = MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR


def resolve_multiple_pagadores_reduced_limit(filing_year: int | None) -> Decimal:
    """Return the Art. 96.3 LIRPF reduced work-income exemption limit for *filing_year*.

    The reduced limit is dated (14.000 € up to 2022, 15.000 € for 2023,
    15.876 € for 2024 onward); the authoritative per-year schedule lives in
    :data:`~cadrumo.core.external_constants.WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR`.
    A year before the earliest tabulated entry resolves to the earliest known
    amount; a year after the latest entry resolves to the latest known amount
    (forward-compatible until a new law revalues it); ``None`` resolves to the
    latest known amount so a year-agnostic operator surface uses the current
    figure.

    Args:
        filing_year: The year the work income was obtained, or ``None``.

    Returns:
        The reduced exemption limit in euros as a :class:`~decimal.Decimal`.
    """
    table = WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR
    if filing_year is None or filing_year >= max(table):
        return table[max(table)]
    if filing_year <= min(table):
        return table[min(table)]
    return table[filing_year]


def evaluate_multiple_pagadores_obligation(
    pagadores_count: int | None,
    secondary_income: Decimal | None,
    total_work_income: Decimal | None = None,
    filing_year: int | None = None,
) -> bool:
    """Return True when Art. 96.3 LIRPF mandates Modelo 100 filing.

    Art. 96.2.a) LIRPF (Ley 35/2006) exempts a natural person from filing when
    their rendimientos íntegros del trabajo do not exceed the general 22.000 €
    limit. Art. 96.3 LIRPF LOWERS that limit to a reduced, dated amount
    (15.876 € for 2024 onward) when the work income comes from more than one
    pagador AND the aggregate from the 2nd-and-subsequent pagadores strictly
    exceeds 1.500 €. The multiple-pagadores situation never obliges a filing by
    itself — it only drops the exemption limit — so the obligation arises only
    when total work income exceeds the applicable reduced limit.

    Args:
        pagadores_count: Number of pagadores the taxpayer received work
            income from during the year. ``None`` means undeclared.
        secondary_income: Sum of income from the 2nd and subsequent
            pagadores. ``None`` means undeclared.
        total_work_income: Total rendimientos íntegros del trabajo for the
            year. ``None`` means undeclared; the obligation then cannot be
            ruled out, so the rule surfaces conservatively rather than
            granting a false clear (``no-silent-under-declaration``).
        filing_year: The year the income was obtained, selecting the dated
            reduced limit. ``None`` uses the latest known reduced limit.

    Returns:
        ``True`` when the reduced-limit regime is active (count >= 2 AND
        secondary_income > 1,500) and either total work income is undeclared
        or it strictly exceeds the per-year reduced limit; ``False`` in every
        other case, including when count or secondary income is undeclared.
    """
    if pagadores_count is None or secondary_income is None:
        return False
    if not (pagadores_count >= 2 and secondary_income > _MULTIPLE_PAGADORES_SECONDARY_THRESHOLD):
        return False
    if total_work_income is None:
        return True
    return total_work_income > resolve_multiple_pagadores_reduced_limit(filing_year)


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

    Surfaces the resolved Ley 58/2003 art-27 recargo band. The application
    overview layer declares any executable continuation from the resolved
    modelo and period; the CLI resolves that declaration against its live
    command surface.

    Attributes:
        still_filable: True for every band -- art-27 self-assessments
            remain admissible past the original deadline; the surcharge
            is the only consequence. The flag exists so a future band
            for absolutely-time-barred filings can be added without
            reshaping the model.
        recargo_band: The :class:`RecargoBand` resolved from the
            completed-months window (Art. 27.2 LGT). It carries the legal
            reference for the band; read it as
            ``recovery.recargo_band.legal_ref`` rather than mirroring it
            onto this payload, so there is exactly one place a renderer
            can read the grounding from and no way for two copies to
            disagree.
    """

    model_config = _STRICT_FROZEN

    still_filable: bool = True
    recargo_band: RecargoBand


def _parse_modelo_deadline_period(value: object) -> Period:
    """Coerce runtime or persisted periods into :class:`~cadrumo.core.Period`.

    Runtime producers pass :class:`~cadrumo.core.Period`; JSON persistence
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
        period: The period covered as a typed :class:`~cadrumo.core.Period`
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

    modelo: Annotated[Modelo, BeforeValidator(_parse_modelo_identifier)]
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
    """The full filing schedule for a taxpayer profile for a given year.

    Attributes:
        profile: The :class:`TaxpayerProfile` the schedule was computed
            for.
        year: The target year.
        obligations: Tuple of :class:`ModeloDeadline` ordered by
            ``(closes_on, modelo, period)``.
        generated_at: UTC timestamp of when :meth:`DeadlineEngine.compute`
            built this schedule. The only non-deterministic field, and
            validated as UTC-aware rather than merely documented as such:
            a naive or offset timestamp on filing evidence is ambiguous
            about the day a window opened or closed.
    """

    model_config = _STRICT_FROZEN

    profile: TaxpayerProfile
    year: int = Field(ge=1900, le=2999)
    obligations: tuple[ModeloDeadline, ...]
    generated_at: UtcInstant

    @field_validator("generated_at")
    @classmethod
    def _require_utc_generated_at(cls, value: datetime) -> datetime:
        """Route the stamp through the canonical UTC-aware contract."""
        return validate_utc_aware(value)
