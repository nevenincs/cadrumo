"""Typed, frozen values of the persona catalogue and the year envelope they are read under."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final, Literal, cast, override

from .inventory import REPO_ROOT

PERSONAS_ROOT: Path = REPO_ROOT / "dev" / "fixtures" / "personas"
"""The persona catalogue: ``identities.toml`` plus one directory per persona."""


CATALOGUE_FORMAT = 1
"""The only catalogue format this reader admits."""


BIOGRAPHICAL_DATE_KEYS: frozenset[str] = frozenset(
    {
        "taxpayer-birth-date",
        "spouse-birth-date",
        "taxpayer-marriage-date",
        "activity-start-date",
        "birth_date",
        "contract_start",
    }
)
"""Date fields describing a life or contract event, which may lie before the envelope floor."""


DECLARATIVE_BLOCKS: tuple[str, ...] = ("officers",)
"""Persona blocks no production operation records; a materialiser reports them as not loaded."""


_YEAR_TOKEN = re.compile(r"(?P<anchor>horizon|floor)(?:(?P<sign>[+-])(?P<offset>[0-9]+))?")


_REVERSE_CHARGE_SUFFIX = "_reverse_charge"


type IdentityKind = Literal["nif", "nie", "cif", "nif_iva"]


type IdentityField = Literal[
    "value",
    "full_name",
    "primer_apellido",
    "segundo_apellido",
    "nombre",
    "razon_social",
    "name",
    "surnames",
    "legal_name",
]


type DocumentRelation = Literal["specimen", "source"]


type DocumentGenerator = Literal["facturae"]


class PersonaCatalogueError(ValueError):
    """A persona file departs from the catalogue contract."""


def _fail(where: str, message: str) -> PersonaCatalogueError:
    return PersonaCatalogueError(f"{where}: {message}")


@dataclass(frozen=True, slots=True)
class ProvisionPeriods:
    """The tax periods one legal provision governs, as the registry's legal register declares them."""

    first: date
    last: date | None

    def governs(self, year: int) -> bool:
        """Whether the provision governs any tax period of calendar ``year``."""
        return self.first <= date(year, 12, 31) and (self.last is None or self.last >= date(year, 1, 1))


@dataclass(frozen=True, slots=True)
class YearEnvelope:
    """The registry's supported filing-year bounds, as the caller read them.

    ``provisions`` carries the governed periods of each legal provision a stated value is
    limited to (``governed_by``), so a value can follow a law that holds for some years only
    without the catalogue naming a year.
    """

    floor: int
    horizon: int
    provisions: tuple[tuple[str, ProvisionPeriods], ...] = ()

    def __post_init__(self) -> None:
        if self.floor > self.horizon:
            raise PersonaCatalogueError(f"envelope floor {self.floor} lies above its horizon {self.horizon}")

    def governs(self, provision: str, year: int) -> bool:
        """Whether ``provision`` governs ``year``; a provision the caller did not read is refused."""
        for reference, periods in self.provisions:
            if reference == provision:
                return periods.governs(year)
        raise PersonaCatalogueError(f"the envelope does not carry the governed periods of {provision!r}")


@dataclass(frozen=True, slots=True)
class YearToken:
    """``horizon`` or ``floor`` shifted by a whole number of years."""

    anchor: Literal["horizon", "floor"]
    offset: int

    @classmethod
    def parse(cls, text: object, *, where: str) -> YearToken:
        """Parse a token such as ``horizon-1`` or ``floor+2``; a literal year is refused."""
        match = _YEAR_TOKEN.fullmatch(text) if isinstance(text, str) else None
        if match is None:
            raise _fail(where, f"{text!r} is not a year token")
        magnitude = int(match["offset"] or "0")
        anchor = cast(Literal["horizon", "floor"], match["anchor"])
        return cls(anchor=anchor, offset=-magnitude if match["sign"] == "-" else magnitude)

    def resolve(self, envelope: YearEnvelope, *, biographical: bool = False) -> int:
        """Return the calendar year, refusing one outside the envelope unless it is a biographical early date."""
        year = self._shifted(envelope)
        if year > envelope.horizon or (year < envelope.floor and not biographical):
            raise PersonaCatalogueError(f"year token {self} resolves outside the supported envelope")
        return year

    def precedes_floor(self, envelope: YearEnvelope) -> bool:
        """Whether the token's year lies below the envelope floor, a year the application refuses."""
        return self._shifted(envelope) < envelope.floor

    def _shifted(self, envelope: YearEnvelope) -> int:
        return (envelope.horizon if self.anchor == "horizon" else envelope.floor) + self.offset

    @override
    def __str__(self) -> str:
        return self.anchor if self.offset == 0 else f"{self.anchor}{self.offset:+d}"


@dataclass(frozen=True, slots=True)
class PersonaDate:
    """A date whose year is a token; ``day`` may name the last day of the month."""

    year: YearToken
    month: int
    day: int | Literal["last"]
    biographical: bool

    def resolve(self, envelope: YearEnvelope) -> date:
        """Return the calendar date under ``envelope``."""
        year = self.year.resolve(envelope, biographical=self.biographical)
        day = calendar.monthrange(year, self.month)[1] if self.day == "last" else self.day
        return date(year, self.month, day)


@dataclass(frozen=True, slots=True)
class Identity:
    """One synthetic identifier bound to exactly one role."""

    role: str
    persona: str
    kind: IdentityKind
    value: str
    primer_apellido: str | None = None
    segundo_apellido: str | None = None
    nombre: str | None = None
    razon_social: str | None = None
    no_second_surname: bool = False
    """The holder is stated with a single surname; a blank ``segundo_apellido`` alone never says so."""
    renderings: tuple[tuple[int, str], ...] = ()
    """Shorter renderings the operator states, as (field width, text), for a field narrower than the name."""
    country: str | None = None
    primary: bool = False
    province: str | None = None
    """Two-digit Spanish province code (01-52) of the holder's domicile, where a filing names it."""
    ceuta_melilla_deduction: bool | None = None
    """Whether a payer's retención on this holder's rentas applied the LIRPF art. 68.4 Ceuta/Melilla deduction."""
    birth_date: PersonaDate | None = None
    """The holder's date of birth, where a fact derived from the holder's age at a date reads it."""

    @property
    def is_entity(self) -> bool:
        """Whether the holder is stated by a razón social rather than by a person's name parts."""
        return self.razon_social is not None

    @property
    def name(self) -> str | None:
        """The given name of a natural person, as the profile and the e-invoice name it."""
        return self.nombre

    @property
    def surnames(self) -> str | None:
        """A natural person's surnames in order, joined by one space; ``None`` for an entity."""
        parts = [part for part in (self.primer_apellido, self.segundo_apellido) if part is not None]
        return " ".join(parts) if parts else None

    @property
    def legal_name(self) -> str | None:
        """The razón social of an entity; ``None`` for a natural person."""
        return self.razon_social

    def field(self, name: IdentityField) -> str:
        """Return one field of the identity, refusing a field it does not carry.

        ``full_name`` is composed by the replay, which owns the official name rule.
        """
        found = getattr(self, name)
        if not isinstance(found, str):
            raise PersonaCatalogueError(f"identity {self.role} carries no {name}")
        return found


@dataclass(frozen=True, slots=True)
class IdentityRefusal:
    """A checksum-invalid value kept for identifier-refusal tests; never a role."""

    value: str
    kind: IdentityKind
    reason: str


@dataclass(frozen=True, slots=True)
class IdentityCatalogue:
    """Every identity of the catalogue, by role."""

    identities: tuple[Identity, ...]
    refusals: tuple[IdentityRefusal, ...]

    def role(self, role: str) -> Identity:
        """Return the identity bound to ``role``; an unknown role is refused."""
        for identity in self.identities:
            if identity.role == role:
                return identity
        raise PersonaCatalogueError(f"unknown identity role {role!r}")


@dataclass(frozen=True, slots=True)
class IdentityRef:
    """A reference to one field of an identity role."""

    role: str
    field: IdentityField = "value"


type ProfileValue = str | bool | tuple[str, ...] | PersonaDate | IdentityRef


@dataclass(frozen=True, slots=True)
class ProfileAnswer:
    """One wizard answer, keyed by the wizard question id, in file order."""

    question_id: str
    value: ProfileValue


@dataclass(frozen=True, slots=True)
class FieldValue:
    """One profile-schema fact no wizard question asks."""

    path: str
    value: str


@dataclass(frozen=True, slots=True)
class ActivityRow:
    """One censo activity row, keyed by the ``activities`` section's field keys."""

    values: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ProfileRow:
    """One row of a repeatable profile section, keyed by that section's field keys.

    A value is a string, a boolean, an identity reference or a date token, rendered as
    ``[profile]`` values are; the repeatable-row mutation records the row. A date records a
    past event, so, as a household row's dates, it may precede the envelope floor.
    """

    section: str
    values: tuple[tuple[str, ProfileValue], ...]


@dataclass(frozen=True, slots=True)
class Election:
    """One dated election: a wizard question, its answer and the year it applies to."""

    question: str
    value: str
    year: YearToken


@dataclass(frozen=True, slots=True)
class OwnAccountDesignation:
    """The modelo role an own account is designated for; an absent ``modelo`` covers every modelo."""

    role: Literal["charge", "refund"]
    modelo: str | None


@dataclass(frozen=True, slots=True)
class OwnAccount:
    """A bank account the persona holds, with the roles it is designated for."""

    label: str
    holding: Literal["titular", "cotitular"]
    iban: str
    designations: tuple[OwnAccountDesignation, ...]


GENERAL_BASES_CARRY_FAMILY: Final[str] = "renta_negative_general_bases_pending"
"""The family token of the negative general bases, whose boxes :data:`PRIOR_CARRY_BOXES` lists."""


PRIOR_CARRY_BOXES: tuple[str, ...] = ("1380", "1382", "1385", "1388")
"""The Modelo 100 boxes of the negative general bases still pending from the four previous ejercicios."""


@dataclass(frozen=True, slots=True)
class PriorCarries:
    """What the persona states is still pending, on one year's Modelo 100, for one family of earlier-ejercicio carries.

    ``family`` names the carries the statement speaks of; a carry of a family no
    statement names is never answered. The token is checked against the registry's
    attestation families where the statement is used, since this shared support
    module cannot import the domain. An empty ``pending`` is the statement
    that nothing is pending in that family. Otherwise each entry is a box with
    the amount pending in it (for the general bases, a box of
    :data:`PRIOR_CARRY_BOXES`), and a box of the family it does not name is
    stated to hold nothing.
    """

    year: YearToken
    family: str
    pending: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True, slots=True)
class HouseholdMember:
    """One descendant or ascendant row: canonical leaves plus the identity supplying its ``nif``."""

    identity: str | None
    leaves: tuple[tuple[str, str | PersonaDate], ...]


@dataclass(frozen=True, slots=True)
class WithholdingCertificate:
    """Retenciones soportadas a payer declared for one ejercicio and income class."""

    payer: str
    ejercicio: YearToken
    income_class: str
    origin: Literal["payer_certificate", "operator_declaration"]
    importe_integro: Decimal
    retencion: Decimal
    cotizaciones_seguridad_social: Decimal | None
    reducciones_aplicables: Decimal | None = None
    gastos_deducibles: Decimal | None = None


@dataclass(frozen=True, slots=True)
class WorkIncomeNoneStatement:
    """The taxpayer's statement that, for one ejercicio, no employer contribution, patrimonio protegido or other imputed work income exists."""

    ejercicio: YearToken


@dataclass(frozen=True, slots=True)
class CadastralValue:
    """The cadastral values of one IBI year the persona states for a property."""

    year: YearToken
    total: Decimal
    construccion: Decimal


@dataclass(frozen=True, slots=True)
class RentalLedgerLink:
    """The ledger rows whose reference starts with ``ref_prefix`` and the rental row they are linked to."""

    ref_prefix: str
    target: Literal["arrendamiento", "inmueble"]
    gasto: str | None
    """The registry property-expense concept of a link to the property; a link to the lease states none."""


@dataclass(frozen=True, slots=True)
class RentalProperty:
    """A let dwelling: the property row and the lease row the replay records, and the expectation inputs.

    ``monthly_rent``, ``days_let``, ``amortization_base``, ``amortization_rate``
    and its note are expectation inputs; the record holds none of them, since
    the rent comes from the ledger rows and the amortisation from the stored
    acquisition and cadastral values. The art. 23.2 rate is derived from the
    lease facts and is never stated.
    """

    id: str
    use: str
    tenant: str
    contract_start: PersonaDate
    monthly_rent: Decimal
    days_let: str
    amortization_base: Decimal
    amortization_rate: Decimal
    amortization_base_note: str | None
    situacion: str
    referencia_catastral: str
    naturaleza: str
    titularidad_regimen: str
    titular: str
    porcentaje_propiedad: Decimal
    importe_adquisicion: Decimal
    valor_suelo: Decimal
    adquisicion_titulo: str
    fecha_adquisicion: PersonaDate
    gastos_tributos_adquisicion: Decimal
    valores_catastrales: tuple[CadastralValue, ...]
    fecha_contrato: PersonaDate
    fecha_inicio: PersonaDate
    uso_vivienda: bool
    zona_tensionada: bool
    primer_arrendamiento_vivienda: bool
    arrendatario_pariente_art24: bool
    incumple_lau_17_6: bool
    ledger_links: tuple[RentalLedgerLink, ...]
    arrendado_desde: PersonaDate | None
    """The date the property was first let; ``None`` when the persona leaves the start unstated."""
    pendiente_intereses_reparacion: Decimal | None
    """What earlier years left pending of the interest and repairs that exceeded the rents; ``None`` when unstated."""


@dataclass(frozen=True, slots=True)
class Officer:
    """A company officer; no production operation records it."""

    identity: str
    role: str
    remunerated: bool


@dataclass(frozen=True, slots=True)
class FiledReturns:
    """Periods of one modelo and year the taxpayer has already filed, each produced from the persona's own data.

    ``iva_compensation_carried_in`` is the Modelo 303 compensation balance
    pending from the period before the first one listed; only a 303 block
    states it.
    """

    modelo: str
    year: YearToken
    periods: tuple[str, ...]
    iva_compensation_carried_in: Decimal | None


@dataclass(frozen=True, slots=True)
class CalculatedReturns:
    """Periods of one modelo and year the replay calculates from the persona's own data without filing them.

    A period belongs here, not in :class:`FiledReturns`, when the product
    cannot take it to filing grade from what the taxpayer holds locally; the
    persona's comment states why.
    """

    modelo: str
    year: YearToken
    periods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalObservation:
    """Casilla values of one return the taxpayer knows from his own copy, recorded as a local observation.

    The product keeps such a value at calculation grade: it feeds a later
    period's calculation and never establishes filing-grade readiness.
    """

    modelo: str
    year: YearToken
    period: str
    casillas: tuple[tuple[str, str], ...]
    reason: str


@dataclass(frozen=True, slots=True)
class AeatFiling:
    """A return the taxpayer filed with the AEAT, as its receipt and the filed declaration show it.

    The replay brings it in as the AEAT's own record: a justificante carrying
    ``csv`` and ``justificante`` presented on ``presented``, and the declaration's
    ``casillas``, admitted through the same receipt checks a captured filing
    passes. Unlike a :class:`LocalObservation` it reaches filing grade, so a later
    period's cross-period check can rely on it.
    """

    modelo: str
    year: YearToken
    period: str
    presented: PersonaDate
    csv: str
    justificante: str
    casillas: tuple[tuple[str, str], ...]
    reason: str


@dataclass(frozen=True, slots=True)
class PriorValueSource:
    """The earlier return an attested prior value stands in for."""

    modelo: str
    year: YearToken
    period: str


@dataclass(frozen=True, slots=True)
class AttestedPriorValue:
    """A figure the taxpayer states for a calculation's dependency on an earlier return the application does not hold.

    The replay submits it through the registered edit operation as an operator
    attestation, and only where the application holds nothing of ``sources``:
    where it holds a work unit, a filing record or an observation of one, that
    source governs and the entry is not submitted. One figure stands for every
    earlier return the binding reads, as the application records one attested
    value per binding naming each source it stands in for. ``derivation`` and
    ``legal_ref`` record where the figure comes from; the operation does not
    receive them.

    A binding the return's selected edition does not declare is refused as a
    stale or misspelt statement. ``where_declared`` states the figure only for
    the returns whose edition declares the binding, for a figure the persona
    holds across editions of which only some read it; the other editions skip
    the entry without a refusal.
    """

    modelo: str
    period: str
    year: YearToken
    binding: str
    value: Decimal
    sources: tuple[PriorValueSource, ...]
    derivation: str
    legal_ref: tuple[str, ...]
    where_declared: bool = False


@dataclass(frozen=True, slots=True)
class WorkInput:
    """Values the operator enters on one return because no record the application holds produces them.

    ``roles`` names each value by a registry identity (a casilla's
    ``continuidad_id`` or ``semantic_role``), which the materialiser resolves
    in the edition the law selects for the return, so no page-qualified casilla
    id of one edition is frozen here. The replay submits the resolved casillas
    through the registered declaration edit, before the return is first
    calculated, as an operator would type them; the application's own refusal
    of a value stands. ``sources`` states, per role, where the figure comes
    from, and ``reason`` why it is entered by hand; the edit operation receives
    neither. Only a casilla the edition leaves to the operator may be given,
    and a given value is never asserted back as an expected value of the same
    return.
    """

    modelo: str
    year: YearToken
    period: str
    roles: tuple[tuple[str, str], ...]
    sources: tuple[tuple[str, str], ...]
    reason: str


@dataclass(frozen=True, slots=True)
class LeasedPremises:
    """Premises the taxpayer rents for the activity from a landlord on whose rent he withholds.

    Every received ledger row from ``landlord`` that carries a retención is a
    rent payment for these premises. ``address`` holds the Modelo 180 structured
    address fields; the reader checks the two Catastro control characters of
    ``cadastral_reference``.
    """

    key: str
    landlord: str
    landlord_tax_status: str
    landlord_tax_regime: str
    landlord_province: str
    situation: str
    cadastral_reference: str | None
    modality: str
    address: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class InventoryBook:
    """The existencias book of one activity for one year, which the Modelo 100 Anexo D rows read.

    The book opens at ``opening_stock`` and closes on its movements at
    ``closing_stock``. ``purchases`` names the ledger rows that book its
    purchases; each becomes a purchase claiming its row, and the stock sold
    is what leaves ``closing_stock``. A book with no purchase closes at its
    opening. ``statement`` is the text of the taxpayer's statement that
    evidences both the closing and the prior year's closing it continues from.
    """

    activity: str
    year: YearToken
    valuation_method: str
    opening_stock: Decimal
    closing_stock: Decimal
    statement: str
    purchases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LedgerRow:
    """One bank movement with the invoice and classification facts behind it."""

    ref: str
    year: YearToken
    month: int
    day: int
    description: str
    amount: Decimal
    currency: str
    counterparty: str | None
    classification: Literal["BUSINESS", "PERSONAL"]
    category_id: str | None
    irpf_category: str | None
    iva_category: str | None
    taxable_base: Decimal | None
    iva_rate: Decimal | None
    iva_amount: Decimal | None
    recargo_amount: Decimal | None
    deduction_kind: str | None
    invoice_kind: Literal["issued", "received"] | None
    invoice_number: str | None
    retencion_rate: Decimal | None
    retencion_amount: Decimal | None
    document: str | None
    accrual: tuple[YearToken, int, int] | None = None
    """The year, month and day the gasto or ingreso accrues, where it differs from the movement and no invoice dates it."""

    def operation_date(self, envelope: YearEnvelope) -> date:
        """Return the movement's calendar date under ``envelope``."""
        return date(self.year.resolve(envelope), self.month, self.day)

    def accrual_date(self, envelope: YearEnvelope) -> date | None:
        """Return the stated accrual date under ``envelope``, or ``None`` when the row states none."""
        if self.accrual is None:
            return None
        year, month, day = self.accrual
        return date(year.resolve(envelope), month, day)

    @property
    def reverse_charge(self) -> bool:
        """Whether the row self-assesses its cuota, which the supplier's invoice therefore leaves out."""
        return self.iva_category is not None and self.iva_category.endswith(_REVERSE_CHARGE_SUFFIX)


@dataclass(frozen=True, slots=True)
class PersonaDocument:
    """A document attached to ledger rows: an existing file, or one generated from the row it evidences.

    Exactly one of ``path`` and ``generator`` is set. A generated document
    (``generator = "facturae"``) is the invoice its single attached row states,
    rendered by :mod:`cadrumo.tests.persona_invoices`, so it agrees with the row
    by construction.
    """

    id: str
    path: Path | None
    generator: DocumentGenerator | None
    media_type: str
    attach_to: tuple[str, ...]
    relation: DocumentRelation
    note: str | None


@dataclass(frozen=True, slots=True)
class ExpectedObligation:
    """Whether a modelo is due for the listed periods of one year."""

    modelo: str
    periods: tuple[str, ...]
    year: YearToken
    applicable: bool | Literal["unknown"]
    reason: str
    legal_ref: tuple[str, ...]
    grounding: Literal["verified", "cited", "unverified"]
    #: The coverage advice the calendar gives instead of a window row, when the law owes the
    #: modelo but its window is not yet published or its applicability is not yet decidable.
    calendar_advice: str | None = None


@dataclass(frozen=True, slots=True)
class ExpectedDeadline:
    """The statutory last day of one filing period."""

    modelo: str
    period: str
    year: YearToken
    statutory_end: PersonaDate
    note: str | None
    legal_ref: tuple[str, ...]
    grounding: Literal["verified", "cited", "unverified"] | None


@dataclass(frozen=True, slots=True)
class ExpectedValue:
    """Hand-derived casillas and concepts of one filing period."""

    modelo: str
    period: str
    year: YearToken
    counterparty: str | None
    casillas: tuple[tuple[str, str], ...]
    concepts: tuple[tuple[str, str], ...]
    parameters: tuple[tuple[str, str], ...]
    derivation: str | None
    legal_ref: tuple[str, ...]
    grounding: Literal["verified", "cited", "unverified"]
    reason: str | None
    #: The error code the application refuses this period with; ``reason`` states why.
    #: The casillas then record what the law gives, and are not compared.
    refusal: str | None = None
    #: The stage that refuses: the calculation itself, or its verification or export
    #: once the calculation has completed (a value wider than its export slot).
    refusal_stage: Literal["calculate", "verify", "export"] = "calculate"
    #: Casillas with the figure the law gives that the calculation leaves unresolved;
    #: ``reason`` states the gap. They are asserted not to carry that figure.
    not_sourced: tuple[tuple[str, str], ...] = ()
    #: A legal provision that holds for some tax periods only. The value replaces the one
    #: stated without it for the same modelo, period, year and counterparty in each year the
    #: provision governs, and states nothing in the other years.
    governed_by: str | None = None
    #: Amounts keyed by a registry identity of a casilla (its ``continuidad_id`` or
    #: ``semantic_role``) instead of a casilla id; the casilla is the one that identity
    #: names in the edition the law selects for the return.
    roles: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Expectations:
    """A persona's hand-grounded obligations, deadlines and values."""

    obligations: tuple[ExpectedObligation, ...]
    deadlines: tuple[ExpectedDeadline, ...]
    values: tuple[ExpectedValue, ...]


type BelowFloorBlock = Literal[
    "filed_returns",
    "calculated_returns",
    "local_observations",
    "aeat_filings",
    "attested_prior_values",
    "work_inputs",
    "prior_carries",
    "expectations.obligations",
    "expectations.deadlines",
    "expectations.values",
    "withholding_certificates",
    "work_income_none_statements",
]


_HISTORY_BLOCKS: Final[frozenset[BelowFloorBlock]] = frozenset(
    {"filed_returns", "calculated_returns", "local_observations", "aeat_filings"}
)


@dataclass(frozen=True, slots=True)
class BelowFloorRecord:
    """A dated persona record a read left out because its year resolves below the envelope floor.

    The application refuses every year below the floor, so such a record can be
    neither replayed nor compared; a return of a supported year that depends on
    it meets the application's own refusal instead.
    """

    block: BelowFloorBlock
    modelo: str
    year: YearToken
    periods: tuple[str, ...]

    @property
    def history(self) -> bool:
        """Whether the record is a return the replay records, rather than an expectation it compares."""
        return self.block in _HISTORY_BLOCKS

    def reason(self, envelope: YearEnvelope) -> str:
        """Why the record is left out under ``envelope``."""
        return (
            f"Modelo {self.modelo} {self.year} ({', '.join(self.periods)}) resolves below the supported "
            f"envelope floor {envelope.floor}, a year the application refuses"
        )


@dataclass(frozen=True, slots=True)
class Persona:
    """One canonical synthetic taxpayer with every file of its directory."""

    id: str
    title: str
    summary: str
    taxpayer: str
    fiscal_year: YearToken
    modelos: tuple[str, ...]
    as_of: PersonaDate
    profile: tuple[ProfileAnswer, ...]
    fields: tuple[FieldValue, ...]
    activities: tuple[ActivityRow, ...]
    elections: tuple[Election, ...]
    descendants: tuple[HouseholdMember, ...]
    ascendants: tuple[HouseholdMember, ...]
    household_families: tuple[str, ...]
    """The household families (``descendants``, ``ascendants``) the persona states, an empty one included.

    A family the persona lists as empty is a declaration that it has no member;
    a family it leaves out is unstated.
    """
    own_accounts: tuple[OwnAccount, ...]
    """The bank accounts the persona states as its own, each with the charge and refund roles it is designated for."""
    prior_carries: tuple[PriorCarries, ...]
    """The Modelo 100 returns whose pending negative bases of earlier ejercicios the persona states, one per year."""
    withholding_certificates: tuple[WithholdingCertificate, ...]
    rental_properties: tuple[RentalProperty, ...]
    officers: tuple[Officer, ...]
    filed_returns: tuple[FiledReturns, ...]
    calculated_returns: tuple[CalculatedReturns, ...]
    local_observations: tuple[LocalObservation, ...]
    aeat_filings: tuple[AeatFiling, ...]
    leased_premises: tuple[LeasedPremises, ...]
    inventory: tuple[InventoryBook, ...]
    ledger: tuple[LedgerRow, ...]
    documents: tuple[PersonaDocument, ...]
    expectations: Expectations
    identities: IdentityCatalogue
    below_floor: tuple[BelowFloorRecord, ...] = ()
    """The dated records a read under a lowered horizon left out, their year lying below the envelope floor."""
    attested_prior_values: tuple[AttestedPriorValue, ...] = ()
    """The figures the taxpayer states for earlier returns the application does not hold."""
    work_inputs: tuple[WorkInput, ...] = ()
    profile_rows: tuple[ProfileRow, ...] = ()
    """Rows of repeatable profile sections no wizard question and no dedicated block records."""
    """The casilla values the operator enters on a return because no record the application holds produces them."""
    work_income_none_statements: tuple[WorkIncomeNoneStatement, ...] = ()
    """The ejercicios whose Modelo 100 the taxpayer states holds no income of the work-income boxes no payer certificate fills."""

    def identity(self, reference: str | IdentityRef) -> str:
        """Return the value an identity role or a role field reference names."""
        ref = IdentityRef(role=reference) if isinstance(reference, str) else reference
        return self.identities.role(ref.role).field(ref.field)

    def declared_blocks(self) -> tuple[str, ...]:
        """Return the declarative blocks this persona fills, which no production operation records."""
        filled = {"officers": self.officers}
        return tuple(name for name in DECLARATIVE_BLOCKS if filled[name])


__all__ = [
    "BIOGRAPHICAL_DATE_KEYS",
    "CATALOGUE_FORMAT",
    "DECLARATIVE_BLOCKS",
    "GENERAL_BASES_CARRY_FAMILY",
    "PERSONAS_ROOT",
    "PRIOR_CARRY_BOXES",
    "ActivityRow",
    "AeatFiling",
    "AttestedPriorValue",
    "BelowFloorBlock",
    "BelowFloorRecord",
    "CadastralValue",
    "CalculatedReturns",
    "Election",
    "Expectations",
    "ExpectedDeadline",
    "ExpectedObligation",
    "ExpectedValue",
    "FieldValue",
    "FiledReturns",
    "HouseholdMember",
    "Identity",
    "IdentityCatalogue",
    "IdentityRef",
    "IdentityRefusal",
    "InventoryBook",
    "LeasedPremises",
    "LedgerRow",
    "LocalObservation",
    "Officer",
    "OwnAccount",
    "OwnAccountDesignation",
    "Persona",
    "PersonaCatalogueError",
    "PersonaDate",
    "PersonaDocument",
    "PriorCarries",
    "PriorValueSource",
    "ProfileAnswer",
    "ProfileRow",
    "ProfileValue",
    "ProvisionPeriods",
    "RentalLedgerLink",
    "RentalProperty",
    "WithholdingCertificate",
    "WorkInput",
    "YearEnvelope",
    "YearToken",
]
