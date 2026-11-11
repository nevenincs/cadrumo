"""Read the canonical persona catalogue under ``dev/fixtures/personas`` into typed, frozen values.

The catalogue is data only; its contract is the catalogue's own README. This
reader parses and validates it and nothing more: it resolves identity roles,
refuses an unknown format, field, role or year, and checks each ledger row's
amount against its invoice figures. Year tokens stay tokens. The supported
filing-year envelope is declared by the registry, which this core-only package
cannot read, so the caller hands it in as a :class:`YearEnvelope` and every
token is checked against it here; a materialiser that reaches the registry
builds the envelope from it and resolves the tokens it submits.
"""

from __future__ import annotations

import calendar
import csv
import dataclasses
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Final, Literal, cast, override

from ..core.decimal.grammar import try_parse_canonical_decimal
from ..core.iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from .inventory import REPO_ROOT
from .run_artifact import file_inputs_digest

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

DECLARATIVE_BLOCKS: tuple[str, ...] = ("rental_properties", "officers")
"""Persona blocks no production operation records; a materialiser reports them as not loaded."""

#: An application error or refusal code, the token a refused operation settles with.
_ERROR_CODE: Final = re.compile(r"(?:ERROR|REFUSED)(?:_[A-Z0-9]+)+")
#: A calendar coverage advice the overview gives for a modelo it cannot place in a window.
_CALENDAR_ADVICE: Final = ("applicable_window_missing", "applicability_undetermined")
_YEAR_TOKEN = re.compile(r"(?P<anchor>horizon|floor)(?:(?P<sign>[+-])(?P<offset>[0-9]+))?")
_REVERSE_CHARGE_SUFFIX = "_reverse_charge"
_IDENTITY_FIELDS = ("value", "name", "surnames", "legal_name")

type IdentityKind = Literal["nif", "nie", "cif", "nif_iva"]
type IdentityField = Literal["value", "name", "surnames", "legal_name"]
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
    name: str | None = None
    surnames: str | None = None
    legal_name: str | None = None
    country: str | None = None
    primary: bool = False
    province: str | None = None
    """Two-digit Spanish province code (01-52) of the holder's domicile, where a filing names it."""
    ceuta_melilla_deduction: bool | None = None
    """Whether a payer's retención on this holder's rentas applied the LIRPF art. 68.4 Ceuta/Melilla deduction."""

    def field(self, name: IdentityField) -> str:
        """Return one field of the identity, refusing a field it does not carry."""
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


@dataclass(frozen=True, slots=True)
class RentalProperty:
    """Declarative facts of a let dwelling; no production operation records them."""

    id: str
    use: str
    tenant: str
    contract_start: PersonaDate
    monthly_rent: Decimal
    days_let: str
    amortization_base: Decimal
    amortization_rate: Decimal
    amortization_base_note: str | None
    reduccion_art_23_2: str


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

    The book records no movement: it opens at ``opening_stock`` and closes on
    its movements, so ``closing_stock`` equals it. ``statement`` is the text of
    the taxpayer's statement that evidences both the closing and the prior
    year's closing it continues from.
    """

    activity: str
    year: YearToken
    valuation_method: str
    opening_stock: Decimal
    closing_stock: Decimal
    statement: str


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
    #: The error code the application refuses this period's calculation with; ``reason``
    #: states why. The casillas then record what the law gives, and are not compared.
    refusal: str | None = None
    #: Casillas with the figure the law gives that the calculation leaves unresolved;
    #: ``reason`` states the gap. They are asserted not to carry that figure.
    not_sourced: tuple[tuple[str, str], ...] = ()
    #: A legal provision that holds for some tax periods only. The value replaces the one
    #: stated without it for the same modelo, period, year and counterparty in each year the
    #: provision governs, and states nothing in the other years.
    governed_by: str | None = None


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
    "expectations.obligations",
    "expectations.deadlines",
    "expectations.values",
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

    def identity(self, reference: str | IdentityRef) -> str:
        """Return the value an identity role or a role field reference names."""
        ref = IdentityRef(role=reference) if isinstance(reference, str) else reference
        return self.identities.role(ref.role).field(ref.field)

    def declared_blocks(self) -> tuple[str, ...]:
        """Return the declarative blocks this persona fills, which no production operation records."""
        filled = {"rental_properties": self.rental_properties, "officers": self.officers}
        return tuple(name for name in DECLARATIVE_BLOCKS if filled[name])


# -- generic TOML readers ------------------------------------------------------------------------------------------


type _Table = Mapping[str, object]


def _table(value: object, where: str) -> _Table:
    if not isinstance(value, dict):
        raise _fail(where, "expected a table")
    return cast(_Table, value)


def _tables(value: object, where: str) -> tuple[_Table, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise _fail(where, "expected an array of tables")
    return tuple(_table(item, f"{where}[{index}]") for index, item in enumerate(cast(list[object], value)))


def _keys(table: _Table, where: str, *, required: frozenset[str], optional: frozenset[str] = frozenset()) -> None:
    unknown = set(table) - required - optional
    if unknown:
        raise _fail(where, f"unknown fields {sorted(unknown)}")
    missing = required - set(table)
    if missing:
        raise _fail(where, f"missing fields {sorted(missing)}")


def _string(table: _Table, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise _fail(where, f"{key} must be a non-empty string")
    return value


def _optional_string(table: _Table, key: str, where: str) -> str | None:
    return None if key not in table else _string(table, key, where)


def _bool(table: _Table, key: str, where: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise _fail(where, f"{key} must be a boolean")
    return value


def _strings(table: _Table, key: str, where: str) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in cast(list[object], value)):
        raise _fail(where, f"{key} must be an array of strings")
    return tuple(cast(list[str], value))


def _choice[Choice: str](value: str, choices: tuple[Choice, ...], where: str) -> Choice:
    for choice in choices:
        if value == choice:
            return choice
    raise _fail(where, f"{value!r} is not one of {list(choices)}")


def _amount(text: object, where: str) -> Decimal:
    parsed = try_parse_canonical_decimal(text, signed=True) if isinstance(text, str) else None
    if parsed is None or text != str(parsed):
        raise _fail(where, f"{text!r} is not a canonical decimal amount")
    return parsed


def _string_map(table: _Table, key: str, where: str) -> tuple[tuple[str, str], ...]:
    if key not in table:
        return ()
    mapping = _table(table[key], f"{where}.{key}")
    if not all(isinstance(value, str) for value in mapping.values()):
        raise _fail(where, f"{key} values must be strings")
    return tuple((name, cast(str, value)) for name, value in mapping.items())


def _date(value: object, where: str, *, biographical: bool) -> PersonaDate:
    table = _table(value, where)
    _keys(table, where, required=frozenset({"year", "month", "day"}))
    month = table["month"]
    day = table["day"]
    if not isinstance(month, int) or isinstance(month, bool) or not 1 <= month <= 12:
        raise _fail(where, "month must be 1..12")
    if day != "last" and (not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 31):
        raise _fail(where, 'day must be 1..31 or "last"')
    return PersonaDate(
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        month=month,
        day=cast(int | Literal["last"], day),
        biographical=biographical,
    )


def _read_toml(path: Path) -> _Table:
    where = str(path.relative_to(REPO_ROOT))
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise _fail(where, f"not TOML: {error}") from None
    if document.get("format") != CATALOGUE_FORMAT:
        raise _fail(where, f"format must be {CATALOGUE_FORMAT}, found {document.get('format')!r}")
    return document


# -- identities ----------------------------------------------------------------------------------------------------


_KINDS: tuple[IdentityKind, ...] = ("nif", "nie", "cif", "nif_iva")
_PROVINCE = re.compile(r"0[1-9]|[1-4][0-9]|5[0-2]")


def _identity(table: _Table, where: str) -> Identity:
    _keys(
        table,
        where,
        required=frozenset({"role", "persona", "kind", "value"}),
        optional=frozenset(
            {"name", "surnames", "legal_name", "country", "primary", "province", "ceuta_melilla_deduction"}
        ),
    )
    province = _optional_string(table, "province", where)
    if province is not None and _PROVINCE.fullmatch(province) is None:
        raise _fail(where, f"province must be a two-digit Spanish province code 01-52, found {province!r}")
    return Identity(
        role=_string(table, "role", where),
        persona=_string(table, "persona", where),
        kind=_choice(_string(table, "kind", where), _KINDS, where),
        value=_string(table, "value", where),
        name=_optional_string(table, "name", where),
        surnames=_optional_string(table, "surnames", where),
        legal_name=_optional_string(table, "legal_name", where),
        country=_optional_string(table, "country", where),
        primary=_bool(table, "primary", where) if "primary" in table else False,
        province=province,
        ceuta_melilla_deduction=(
            _bool(table, "ceuta_melilla_deduction", where) if "ceuta_melilla_deduction" in table else None
        ),
    )


def parse_identity_catalogue(document: _Table, *, where: str = "identities.toml") -> IdentityCatalogue:
    """Validate a parsed ``identities.toml``: one value per role, one role per value."""
    if document.get("format") != CATALOGUE_FORMAT:
        raise _fail(where, f"format must be {CATALOGUE_FORMAT}, found {document.get('format')!r}")
    _keys(document, where, required=frozenset({"format", "convention", "identities"}), optional=frozenset({"refusals"}))
    identities = tuple(
        _identity(table, f"{where} identities[{index}]")
        for index, table in enumerate(_tables(document["identities"], where))
    )
    for attribute in ("role", "value"):
        seen = [getattr(identity, attribute) for identity in identities]
        if len(set(seen)) != len(seen):
            raise _fail(where, f"an identity {attribute} is declared twice")
    refusals: list[IdentityRefusal] = []
    for index, table in enumerate(_tables(document.get("refusals"), f"{where} refusals")):
        here = f"{where} refusals[{index}]"
        _keys(table, here, required=frozenset({"value", "kind", "reason"}))
        refusals.append(
            IdentityRefusal(
                value=_string(table, "value", here),
                kind=_choice(_string(table, "kind", here), _KINDS, here),
                reason=_string(table, "reason", here),
            )
        )
    if {refusal.value for refusal in refusals} & {identity.value for identity in identities}:
        raise _fail(where, "a refusal value is also bound to a role")
    return IdentityCatalogue(identities=identities, refusals=tuple(refusals))


@cache
def identity_catalogue() -> IdentityCatalogue:
    """Return the catalogue's ``identities.toml``."""
    return parse_identity_catalogue(_read_toml(PERSONAS_ROOT / "identities.toml"))


# -- persona.toml --------------------------------------------------------------------------------------------------

_PERSONA_TABLES = frozenset(
    {
        "format",
        "persona",
        "clock",
        "profile",
        "fields",
        "activities",
        "elections",
        "household",
        "own_accounts",
        "withholding_certificates",
        "rental_properties",
        "officers",
        "filed_returns",
        "calculated_returns",
        "local_observations",
        "aeat_filings",
        "leased_premises",
        "inventory",
    }
)
_DESCENDANT_LEAVES = frozenset(
    {
        "birth_date",
        "relacion",
        "inscripcion_registro_civil",
        "acogimiento_resolucion",
        "fallecimiento",
        "discapacidad",
        "convivencia",
        "dependencia_economica",
        "custodia_compartida",
        "rentas_anuales",
        "declaracion_propia",
        "prorrata_minimo",
        "meses_madre_trabajo",
        "alta_posterior_nacimiento_mes",
        "segundo_ciclo_infantil_inicio_mes",
        "gastos_guarderia",
        "gastos_guarderia_mensuales",
    }
)
_ASCENDANT_LEAVES = frozenset({"birth_date", "fallecimiento", "convivientes"})


class _Roles:
    """Resolve every role a persona names, refusing an unknown one or another persona's."""

    def __init__(self, catalogue: IdentityCatalogue, persona_id: str) -> None:
        self._catalogue = catalogue
        self._persona_id = persona_id

    def __call__(self, role: object, where: str) -> str:
        if not isinstance(role, str):
            raise _fail(where, "an identity role must be a string")
        try:
            identity = self._catalogue.role(role)
        except PersonaCatalogueError as error:
            raise _fail(where, str(error)) from None
        if identity.persona != self._persona_id:
            raise _fail(where, f"identity role {role!r} belongs to persona {identity.persona!r}")
        return role


def _profile_value(question_id: str, value: object, where: str, roles: _Roles) -> ProfileValue:
    if isinstance(value, str | bool):
        return value
    if isinstance(value, list):
        return _strings({question_id: value}, question_id, where)
    table = _table(value, where)
    if "identity" in table:
        _keys(table, where, required=frozenset({"identity"}), optional=frozenset({"field"}))
        field = _choice(_string(table, "field", where), _IDENTITY_FIELDS, where) if "field" in table else "value"
        return IdentityRef(role=roles(table["identity"], where), field=field)
    return _date(table, where, biographical=question_id in BIOGRAPHICAL_DATE_KEYS)


def _household(rows: object, where: str, leaves: frozenset[str], roles: _Roles) -> tuple[HouseholdMember, ...]:
    members: list[HouseholdMember] = []
    for index, table in enumerate(_tables(rows, where)):
        here = f"{where}[{index}]"
        _keys(table, here, required=frozenset(), optional=leaves | {"identity"})
        values: list[tuple[str, str | PersonaDate]] = []
        for key, value in table.items():
            if key == "identity":
                continue
            if key == "birth_date":
                values.append((key, _date(value, f"{here}.{key}", biographical=True)))
            elif isinstance(value, str):
                values.append((key, value))
            else:
                raise _fail(here, f"{key} must be the leaf's canonical string")
        identity = roles(table["identity"], here) if "identity" in table else None
        members.append(HouseholdMember(identity=identity, leaves=tuple(values)))
    return tuple(members)


def _own_account_designation(table: _Table, where: str, modelos: tuple[str, ...]) -> OwnAccountDesignation:
    _keys(table, where, required=frozenset({"role"}), optional=frozenset({"modelo"}))
    modelo = _optional_string(table, "modelo", where)
    if modelo is not None and modelo not in modelos:
        raise _fail(where, f"modelo {modelo!r} is not one of the persona's modelos {list(modelos)}")
    return OwnAccountDesignation(
        role=_choice(_string(table, "role", where), ("charge", "refund"), where), modelo=modelo
    )


def _own_account(table: _Table, where: str, modelos: tuple[str, ...]) -> OwnAccount:
    _keys(table, where, required=frozenset({"label", "holding", "iban"}), optional=frozenset({"designations"}))
    iban = normalise_iban(_string(table, "iban", where))
    if not IBAN_SHAPE_RE.match(iban) or iban_mod_97(iban) != 1:
        raise _fail(where, "iban is not a checksum-valid ISO 13616 account number")
    return OwnAccount(
        label=_string(table, "label", where),
        holding=_choice(_string(table, "holding", where), ("titular", "cotitular"), where),
        iban=iban,
        designations=tuple(
            _own_account_designation(item, f"{where} designations[{index}]", modelos)
            for index, item in enumerate(_tables(table.get("designations"), where))
        ),
    )


def _check_designations(accounts: tuple[OwnAccount, ...], where: str) -> None:
    """Refuse two designations of one role and scope, which the register holds once."""
    keys = [(item.role, item.modelo) for account in accounts for item in account.designations]
    if len(keys) != len(set(keys)):
        raise _fail(where, "two designations state one role and scope")


def _withholding(table: _Table, where: str, roles: _Roles) -> WithholdingCertificate:
    _keys(
        table,
        where,
        required=frozenset({"payer", "ejercicio", "income_class", "origin", "importe_integro", "retencion"}),
        optional=frozenset({"cotizaciones_seguridad_social"}),
    )
    cotizaciones = table.get("cotizaciones_seguridad_social")
    return WithholdingCertificate(
        payer=roles(table["payer"], where),
        ejercicio=YearToken.parse(table["ejercicio"], where=f"{where}.ejercicio"),
        income_class=_string(table, "income_class", where),
        origin=_choice(_string(table, "origin", where), ("payer_certificate", "operator_declaration"), where),
        importe_integro=_amount(table["importe_integro"], f"{where}.importe_integro"),
        retencion=_amount(table["retencion"], f"{where}.retencion"),
        cotizaciones_seguridad_social=None if cotizaciones is None else _amount(cotizaciones, where),
    )


def _rental(table: _Table, where: str, roles: _Roles) -> RentalProperty:
    _keys(
        table,
        where,
        required=frozenset(
            {
                "id",
                "use",
                "tenant",
                "contract_start",
                "monthly_rent",
                "days_let",
                "amortization_base",
                "amortization_rate",
                "reduccion_art_23_2",
            }
        ),
        optional=frozenset({"amortization_base_note"}),
    )
    return RentalProperty(
        id=_string(table, "id", where),
        use=_string(table, "use", where),
        tenant=roles(table["tenant"], where),
        contract_start=_date(table["contract_start"], f"{where}.contract_start", biographical=True),
        monthly_rent=_amount(table["monthly_rent"], where),
        days_let=_string(table, "days_let", where),
        amortization_base=_amount(table["amortization_base"], where),
        amortization_rate=_amount(table["amortization_rate"], where),
        amortization_base_note=_optional_string(table, "amortization_base_note", where),
        reduccion_art_23_2=_string(table, "reduccion_art_23_2", where),
    )


def _officer(table: _Table, where: str, roles: _Roles) -> Officer:
    _keys(table, where, required=frozenset({"identity", "role", "remunerated"}))
    return Officer(
        identity=roles(table["identity"], where),
        role=_string(table, "role", where),
        remunerated=_bool(table, "remunerated", where),
    )


_FILED_PERIODS: Final[tuple[str, ...]] = ("1T", "2T", "3T", "4T", "0A")
"""The period codes a filed return may name, in the order their windows close within a year."""
_IVA_COMPENSATION_MODELO: Final[str] = "303"


def _filed_returns(table: _Table, where: str) -> FiledReturns:
    _keys(
        table,
        where,
        required=frozenset({"modelo", "year", "periods"}),
        optional=frozenset({"iva_compensation_carried_in"}),
    )
    modelo = _string(table, "modelo", where)
    periods = _return_periods(table, where)
    carried = table.get("iva_compensation_carried_in")
    if carried is not None and modelo != _IVA_COMPENSATION_MODELO:
        raise _fail(where, f"only a Modelo {_IVA_COMPENSATION_MODELO} block states iva_compensation_carried_in")
    return FiledReturns(
        modelo=modelo,
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        periods=periods,
        iva_compensation_carried_in=None
        if carried is None
        else _amount(carried, f"{where}.iva_compensation_carried_in"),
    )


def _return_periods(table: _Table, where: str) -> tuple[str, ...]:
    periods = _strings(table, "periods", where)
    for period in periods:
        _choice(period, _FILED_PERIODS, where)
    if list(periods) != sorted(set(periods), key=_FILED_PERIODS.index):
        raise _fail(where, "periods must be distinct and in calendar order")
    return periods


def _calculated_returns(table: _Table, where: str) -> CalculatedReturns:
    _keys(table, where, required=frozenset({"modelo", "year", "periods"}))
    return CalculatedReturns(
        modelo=_string(table, "modelo", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        periods=_return_periods(table, where),
    )


def _local_observation(table: _Table, where: str) -> LocalObservation:
    _keys(table, where, required=frozenset({"modelo", "year", "period", "casillas", "reason"}))
    casillas = _table(table["casillas"], f"{where}.casillas")
    if not casillas:
        raise _fail(where, "casillas must name at least one casilla")
    values: list[tuple[str, str]] = []
    for casilla, value in sorted(casillas.items()):
        _amount(value, f"{where}.casillas.{casilla}")
        values.append((casilla, cast(str, value)))
    return LocalObservation(
        modelo=_string(table, "modelo", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        period=_choice(_string(table, "period", where), _FILED_PERIODS, where),
        casillas=tuple(values),
        reason=_string(table, "reason", where),
    )


_ADDRESS_REQUIRED: Final = frozenset(
    {
        "province_code",
        "municipality_code",
        "municipality",
        "locality",
        "postal_code",
        "street_type",
        "street_name",
        "number_type",
        "house_number",
    }
)
_ADDRESS_OPTIONAL: Final = frozenset(
    {"number_qualifier", "block", "portal", "staircase", "floor", "door", "complement"}
)

_CADASTRAL_WEIGHTS: Final = (13, 15, 12, 5, 4, 17, 9, 21, 3, 7, 1)
_CADASTRAL_CONTROL_LETTERS: Final = "MQWERTYUIOPASDFGHJKLBZX"
_CADASTRAL_REFERENCE: Final = re.compile(r"[0-9A-Z]{14}[0-9]{4}[A-Z]{2}")


_AEAT_CSV: Final = re.compile(r"[A-Z0-9]{16}")
_JUSTIFICANTE_NUMBER: Final = re.compile(r"[0-9]{13}")


def _aeat_filing(table: _Table, where: str) -> AeatFiling:
    _keys(
        table,
        where,
        required=frozenset({"modelo", "year", "period", "presented", "csv", "justificante", "casillas", "reason"}),
    )
    casillas = _table(table["casillas"], f"{where}.casillas")
    if not casillas:
        raise _fail(where, "casillas must name at least one casilla")
    values: list[tuple[str, str]] = []
    for casilla, value in sorted(casillas.items()):
        _amount(value, f"{where}.casillas.{casilla}")
        values.append((casilla, cast(str, value)))
    csv_code = _string(table, "csv", where)
    if _AEAT_CSV.fullmatch(csv_code) is None:
        raise _fail(where, "csv is the 16-character Código Seguro de Verificación, uppercase letters and digits")
    number = _string(table, "justificante", where)
    if _JUSTIFICANTE_NUMBER.fullmatch(number) is None:
        raise _fail(where, "justificante is the 13-digit número de justificante")
    return AeatFiling(
        modelo=_string(table, "modelo", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        period=_choice(_string(table, "period", where), _FILED_PERIODS, where),
        presented=_date(table["presented"], f"{where}.presented", biographical=False),
        csv=csv_code,
        justificante=number,
        casillas=tuple(values),
        reason=_string(table, "reason", where),
    )


def _cadastral_character_value(character: str) -> int:
    if character.isdigit():
        return int(character)
    # Catastro numbers the alphabet with Ñ after N, so every letter after N moves up by one.
    return ord(character) - ord("A") + (1 if character <= "N" else 2)


def cadastral_control_characters(reference: str) -> str:
    """Return the two Catastro control letters of an 18-character urban cadastral reference.

    The first letter checks the parcel (characters 1-7), the second the map
    sheet (characters 8-14), each followed by the four-digit property number:
    the weighted sum of those eleven characters, modulo 23, indexes the
    control alphabet.
    """
    controls = ""
    for part in (reference[0:7], reference[7:14]):
        characters = part + reference[14:18]
        total = sum(
            weight * _cadastral_character_value(character)
            for weight, character in zip(_CADASTRAL_WEIGHTS, characters, strict=True)
        )
        controls += _CADASTRAL_CONTROL_LETTERS[total % len(_CADASTRAL_CONTROL_LETTERS)]
    return controls


def _cadastral_reference(value: object, where: str) -> str:
    if not isinstance(value, str) or _CADASTRAL_REFERENCE.fullmatch(value) is None:
        raise _fail(where, "cadastral_reference must be a 20-character urban cadastral reference")
    if cadastral_control_characters(value[:18]) != value[18:]:
        raise _fail(where, "cadastral_reference control characters do not match the Catastro algorithm")
    return value


def _leased_premises(table: _Table, where: str, roles: _Roles) -> LeasedPremises:
    _keys(
        table,
        where,
        required=frozenset(
            {
                "key",
                "landlord",
                "landlord_tax_status",
                "landlord_tax_regime",
                "landlord_province",
                "situation",
                "modality",
                "address",
            }
        ),
        optional=frozenset({"cadastral_reference"}),
    )
    address = _table(table["address"], f"{where}.address")
    _keys(address, f"{where}.address", required=_ADDRESS_REQUIRED, optional=_ADDRESS_OPTIONAL)
    if not all(isinstance(value, str) for value in address.values()):
        raise _fail(f"{where}.address", "address values must be strings")
    reference = table.get("cadastral_reference")
    return LeasedPremises(
        key=_string(table, "key", where),
        landlord=roles(table["landlord"], f"{where}.landlord"),
        landlord_tax_status=_string(table, "landlord_tax_status", where),
        landlord_tax_regime=_string(table, "landlord_tax_regime", where),
        landlord_province=_string(table, "landlord_province", where),
        situation=_string(table, "situation", where),
        cadastral_reference=None
        if reference is None
        else _cadastral_reference(reference, f"{where}.cadastral_reference"),
        modality=_string(table, "modality", where),
        address=tuple((key, cast(str, value)) for key, value in address.items()),
    )


def _inventory_book(table: _Table, where: str) -> InventoryBook:
    _keys(
        table,
        where,
        required=frozenset({"activity", "year", "valuation_method", "opening_stock", "closing_stock", "statement"}),
    )
    opening = _amount(table["opening_stock"], f"{where}.opening_stock")
    closing = _amount(table["closing_stock"], f"{where}.closing_stock")
    if opening < 0 or closing < 0:
        raise _fail(where, "existencias are valued at a nonnegative amount")
    if closing != opening:
        raise _fail(where, "a book with no movement closes at its opening stock")
    return InventoryBook(
        activity=_string(table, "activity", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        valuation_method=_string(table, "valuation_method", where),
        opening_stock=opening,
        closing_stock=closing,
        statement=_string(table, "statement", where),
    )


def filed_period_order(period: str) -> int:
    """The calendar position of a filed period code within its year."""
    return _FILED_PERIODS.index(period)


# -- ledger.csv ----------------------------------------------------------------------------------------------------

LEDGER_COLUMNS: tuple[str, ...] = (
    "ref",
    "year",
    "month",
    "day",
    "description",
    "amount",
    "currency",
    "counterparty",
    "classification",
    "category_id",
    "irpf_category",
    "iva_category",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "recargo_amount",
    "deduction_kind",
    "invoice_kind",
    "invoice_number",
    "retencion_rate",
    "retencion_amount",
    "document",
)
"""The ``ledger.csv`` header, in order."""

LEDGER_ACCRUAL_COLUMNS: tuple[str, ...] = ("accrual_year", "accrual_month", "accrual_day")
"""Optional trailing ``ledger.csv`` columns: a row's accrual date, stated where the devengo criterion needs it."""


def _cell(row: Mapping[str, str], column: str) -> str | None:
    return row[column] or None


def _cell_amount(row: Mapping[str, str], column: str, where: str) -> Decimal | None:
    text = _cell(row, column)
    return None if text is None else _amount(text, f"{where}.{column}")


def _ledger_row(row: Mapping[str, str], where: str, roles: _Roles) -> LedgerRow:
    month, day = int(row["month"]), int(row["day"])
    counterparty = _cell(row, "counterparty")
    invoice_kind = _cell(row, "invoice_kind")
    ledger_row = LedgerRow(
        ref=row["ref"],
        year=YearToken.parse(row["year"], where=f"{where}.year"),
        month=month,
        day=day,
        description=row["description"],
        amount=_amount(row["amount"], f"{where}.amount"),
        currency=row["currency"],
        counterparty=None if counterparty is None else roles(counterparty, where),
        classification=_choice(row["classification"], ("BUSINESS", "PERSONAL"), where),
        category_id=_cell(row, "category_id"),
        irpf_category=_cell(row, "irpf_category"),
        iva_category=_cell(row, "iva_category"),
        taxable_base=_cell_amount(row, "taxable_base", where),
        iva_rate=_cell_amount(row, "iva_rate", where),
        iva_amount=_cell_amount(row, "iva_amount", where),
        recargo_amount=_cell_amount(row, "recargo_amount", where),
        deduction_kind=_cell(row, "deduction_kind"),
        invoice_kind=None if invoice_kind is None else _choice(invoice_kind, ("issued", "received"), where),
        invoice_number=_cell(row, "invoice_number"),
        retencion_rate=_cell_amount(row, "retencion_rate", where),
        retencion_amount=_cell_amount(row, "retencion_amount", where),
        document=_cell(row, "document"),
        accrual=_accrual(row, where),
    )
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise _fail(where, "month or day out of range")
    if not ledger_row.ref or not ledger_row.description or ledger_row.currency != "EUR":
        raise _fail(where, "a row needs a ref, a description and EUR")
    _check_invoice_arithmetic(ledger_row, where)
    return ledger_row


def _accrual(row: Mapping[str, str], where: str) -> tuple[YearToken, int, int] | None:
    cells = [row.get(column) or None for column in LEDGER_ACCRUAL_COLUMNS]
    if all(cell is None for cell in cells):
        return None
    year, month, day = cells
    if year is None or month is None or day is None:
        raise _fail(where, "an accrual date states its year, month and day")
    accrual = (YearToken.parse(year, where=f"{where}.accrual_year"), int(month), int(day))
    if not 1 <= accrual[1] <= 12 or not 1 <= accrual[2] <= 31:
        raise _fail(where, "accrual month or day out of range")
    return accrual


def _check_invoice_arithmetic(row: LedgerRow, where: str) -> None:
    """``|amount| = base + iva + recargo - retencion``, with IVA left out under reverse charge."""
    if row.taxable_base is None:
        return
    iva = Decimal(0) if row.reverse_charge or row.iva_amount is None else row.iva_amount
    total = row.taxable_base + iva + (row.recargo_amount or 0) - (row.retencion_amount or 0)
    if abs(row.amount) != total:
        raise _fail(where, f"amount {row.amount} differs from its invoice figures {total}")


def _parse_ledger(text: str, *, where: str, roles: _Roles) -> tuple[LedgerRow, ...]:
    """Parse ``ledger.csv`` text; a header other than :data:`LEDGER_COLUMNS`, optionally followed by
    :data:`LEDGER_ACCRUAL_COLUMNS`, is refused."""
    reader = csv.DictReader(text.splitlines())
    if tuple(reader.fieldnames or ()) not in (LEDGER_COLUMNS, LEDGER_COLUMNS + LEDGER_ACCRUAL_COLUMNS):
        raise _fail(
            where, f"header must be {','.join(LEDGER_COLUMNS)}, optionally with {','.join(LEDGER_ACCRUAL_COLUMNS)}"
        )
    rows = tuple(_ledger_row(row, f"{where}:{index + 2}", roles) for index, row in enumerate(reader))
    refs = [row.ref for row in rows]
    if len(set(refs)) != len(refs):
        raise _fail(where, "a ledger ref is repeated")
    return rows


# -- documents.toml and expectations.toml --------------------------------------------------------------------------


def _documents(document: _Table, where: str, persona_id: str, refs: frozenset[str]) -> tuple[PersonaDocument, ...]:
    _keys(document, where, required=frozenset({"format", "persona", "documents"}))
    if document["persona"] != persona_id:
        raise _fail(where, "persona differs from its directory")
    documents: list[PersonaDocument] = []
    for index, table in enumerate(_tables(document["documents"], where)):
        here = f"{where} documents[{index}]"
        _keys(
            table,
            here,
            required=frozenset({"id", "media_type", "attach_to", "relation"}),
            optional=frozenset({"note", "path", "generator"}),
        )
        if ("path" in table) == ("generator" in table):
            raise _fail(here, "a document names exactly one of path and generator")
        path: Path | None = None
        generator: DocumentGenerator | None = None
        attach_to = _strings(table, "attach_to", here)
        if "path" in table:
            path = REPO_ROOT / _string(table, "path", here)
            if not path.is_file():
                raise _fail(here, "the referenced specimen does not exist")
        else:
            generator = _choice(_string(table, "generator", here), ("facturae",), here)
            if len(attach_to) != 1:
                raise _fail(here, "a generated document is the invoice of exactly one row")
        if not set(attach_to) <= refs:
            raise _fail(here, "attach_to names a ref the ledger does not hold")
        documents.append(
            PersonaDocument(
                id=_string(table, "id", here),
                path=path,
                generator=generator,
                media_type=_string(table, "media_type", here),
                attach_to=attach_to,
                relation=_choice(_string(table, "relation", here), ("specimen", "source"), here),
                note=_optional_string(table, "note", here),
            )
        )
    return tuple(documents)


_GROUNDING: tuple[Literal["verified", "cited", "unverified"], ...] = ("verified", "cited", "unverified")


def _expectations(document: _Table, where: str, persona_id: str, roles: _Roles) -> Expectations:
    _keys(
        document,
        where,
        required=frozenset({"format", "persona"}),
        optional=frozenset({"obligations", "deadlines", "values"}),
    )
    if document["persona"] != persona_id:
        raise _fail(where, "persona differs from its directory")
    obligations: list[ExpectedObligation] = []
    for index, table in enumerate(_tables(document.get("obligations"), where)):
        here = f"{where} obligations[{index}]"
        _keys(
            table,
            here,
            required=frozenset({"modelo", "periods", "year", "applicable", "reason", "legal_ref", "grounding"}),
            optional=frozenset({"calendar_advice"}),
        )
        applicable = table["applicable"]
        if not isinstance(applicable, bool) and applicable != "unknown":
            raise _fail(here, 'applicable must be a boolean or "unknown"')
        calendar_advice = _optional_string(table, "calendar_advice", here)
        if calendar_advice is not None:
            calendar_advice = _choice(calendar_advice, _CALENDAR_ADVICE, f"{here}.calendar_advice")
            if applicable is not True:
                raise _fail(here, "a calendar advice stands in for the window row of an owed modelo")
        obligations.append(
            ExpectedObligation(
                modelo=_string(table, "modelo", here),
                periods=_strings(table, "periods", here),
                year=YearToken.parse(table["year"], where=f"{here}.year"),
                applicable=cast(bool | Literal["unknown"], applicable),
                reason=_string(table, "reason", here),
                legal_ref=_strings(table, "legal_ref", here),
                grounding=_choice(_string(table, "grounding", here), _GROUNDING, here),
                calendar_advice=calendar_advice,
            )
        )
    deadlines: list[ExpectedDeadline] = []
    for index, table in enumerate(_tables(document.get("deadlines"), where)):
        here = f"{where} deadlines[{index}]"
        _keys(
            table,
            here,
            required=frozenset({"modelo", "period", "year", "statutory_end"}),
            optional=frozenset({"note", "legal_ref", "grounding"}),
        )
        deadlines.append(
            ExpectedDeadline(
                modelo=_string(table, "modelo", here),
                period=_string(table, "period", here),
                year=YearToken.parse(table["year"], where=f"{here}.year"),
                statutory_end=_date(table["statutory_end"], f"{here}.statutory_end", biographical=False),
                note=_optional_string(table, "note", here),
                legal_ref=_strings(table, "legal_ref", here) if "legal_ref" in table else (),
                grounding=_choice(_string(table, "grounding", here), _GROUNDING, here)
                if "grounding" in table
                else None,
            )
        )
    values: list[ExpectedValue] = []
    for index, table in enumerate(_tables(document.get("values"), where)):
        here = f"{where} values[{index}]"
        _keys(
            table,
            here,
            required=frozenset({"modelo", "period", "year", "legal_ref", "grounding"}),
            optional=frozenset(
                {
                    "counterparty",
                    "casillas",
                    "concepts",
                    "parameters",
                    "derivation",
                    "reason",
                    "refusal",
                    "not_sourced",
                    "governed_by",
                }
            ),
        )
        grounding = _choice(_string(table, "grounding", here), _GROUNDING, here)
        governed_by = _optional_string(table, "governed_by", here)
        legal_ref = _strings(table, "legal_ref", here)
        if governed_by is not None and governed_by not in legal_ref:
            raise _fail(here, "the provision a value is governed by is one of its legal references")
        reason = _optional_string(table, "reason", here)
        if grounding == "unverified" and reason is None:
            raise _fail(here, "an unverified expectation says what is missing in its reason")
        refusal = _optional_string(table, "refusal", here)
        if refusal is not None:
            if _ERROR_CODE.fullmatch(refusal) is None:
                raise _fail(here, "a refusal names the application error code")
            if reason is None:
                raise _fail(here, "a refusal says in its reason why the application refuses")
        casillas = _string_map(table, "casillas", here)
        not_sourced = _string_map(table, "not_sourced", here)
        if not_sourced:
            if reason is None:
                raise _fail(here, "a not-sourced casilla says in its reason what source is missing")
            if refusal is not None:
                raise _fail(here, "a refused period sources no casilla, so it states none as not sourced")
            if {casilla for casilla, _amount in not_sourced} & {casilla for casilla, _amount in casillas}:
                raise _fail(here, "a casilla is either compared or stated as not sourced")
        values.append(
            ExpectedValue(
                modelo=_string(table, "modelo", here),
                period=_string(table, "period", here),
                year=YearToken.parse(table["year"], where=f"{here}.year"),
                counterparty=roles(table["counterparty"], here) if "counterparty" in table else None,
                casillas=casillas,
                concepts=_string_map(table, "concepts", here),
                parameters=_string_map(table, "parameters", here),
                derivation=_optional_string(table, "derivation", here),
                legal_ref=legal_ref,
                grounding=grounding,
                reason=reason,
                refusal=refusal,
                not_sourced=not_sourced,
                governed_by=governed_by,
            )
        )
    return Expectations(obligations=tuple(obligations), deadlines=tuple(deadlines), values=tuple(values))


def _value_key(value: ExpectedValue) -> tuple[str, str, str, str | None]:
    return (value.modelo, value.period, str(value.year), value.counterparty)


def values_in_force(values: tuple[ExpectedValue, ...], envelope: YearEnvelope) -> tuple[tuple[int, ExpectedValue], ...]:
    """Each stated value with its resolved year, as the law of that year holds it.

    Values limited to a provision (``governed_by``) replace every plain value of their
    modelo, period, year and counterparty in a year the provision governs, and are dropped
    in the other years. Values of one key following two different provisions in the same
    year are refused, since the catalogue could not say which law the figures follow.
    """
    resolved: list[tuple[int, ExpectedValue]] = []
    for value in values:
        year = value.year.resolve(envelope)
        governing = {
            other.governed_by
            for other in values
            if other.governed_by is not None
            and _value_key(other) == _value_key(value)
            and envelope.governs(other.governed_by, year)
        }
        if len(governing) > 1:
            raise PersonaCatalogueError(
                f"{value.modelo} {value.period} {value.year}: values follow {sorted(governing)} in the same year"
            )
        if value.governed_by is None if not governing else value.governed_by in governing:
            resolved.append((year, value))
    return tuple(resolved)


def governed_provisions() -> frozenset[str]:
    """Every provision a stated value of the catalogue is limited to, read before any persona is validated.

    The caller reads these provisions' governed periods from the registry into the
    :class:`YearEnvelope` that validation and :func:`values_in_force` take.
    """
    provisions: set[str] = set()
    for persona_id in persona_ids():
        path = PERSONAS_ROOT / persona_id / "expectations.toml"
        if not path.is_file():
            continue
        for index, table in enumerate(_tables(_read_toml(path).get("values"), str(path))):
            governed_by = _optional_string(table, "governed_by", f"{path} values[{index}]")
            if governed_by is not None:
                provisions.add(governed_by)
    return frozenset(provisions)


# -- assembly ------------------------------------------------------------------------------------------------------


def persona_ids() -> tuple[str, ...]:
    """Return every persona of the catalogue, sorted."""
    return tuple(sorted(entry.name for entry in PERSONAS_ROOT.iterdir() if (entry / "persona.toml").is_file()))


def parse_persona(
    persona_id: str,
    *,
    persona_document: _Table,
    ledger_text: str,
    documents_document: _Table,
    expectations_document: _Table,
    catalogue: IdentityCatalogue,
    envelope: YearEnvelope,
    omit_below_floor: bool = False,
) -> Persona:
    """Validate one persona's parsed files against the catalogue contract and the year envelope.

    A year outside the envelope is refused. With ``omit_below_floor``, for a
    read under a horizon lowered below the registry's own, a return-history
    record or an expectation whose year falls below the floor is left out and
    listed in :attr:`Persona.below_floor` instead; every other token stays
    refused there.
    """
    where = f"{persona_id}/persona.toml"
    if persona_document.get("format") != CATALOGUE_FORMAT:
        raise _fail(where, f"format must be {CATALOGUE_FORMAT}, found {persona_document.get('format')!r}")
    _keys(
        persona_document, where, required=frozenset({"format", "persona", "clock", "profile"}), optional=_PERSONA_TABLES
    )
    roles = _Roles(catalogue, persona_id)
    head = _table(persona_document["persona"], f"{where} [persona]")
    _keys(
        head, f"{where} [persona]", required=frozenset({"id", "title", "summary", "taxpayer", "fiscal_year", "modelos"})
    )
    if head["id"] != persona_id:
        raise _fail(where, "persona id differs from its directory")
    clock = _table(persona_document["clock"], f"{where} [clock]")
    _keys(clock, f"{where} [clock]", required=frozenset({"as_of"}))
    profile = _table(persona_document["profile"], f"{where} [profile]")
    fields = _table(persona_document.get("fields", {}), f"{where} [fields]")
    if not all(isinstance(value, str) for value in fields.values()):
        raise _fail(where, "[fields] values must be strings")
    household = _table(persona_document.get("household", {}), f"{where} [household]")
    _keys(household, f"{where} [household]", required=frozenset(), optional=frozenset({"descendants", "ascendants"}))
    activities: list[ActivityRow] = []
    for index, table in enumerate(_tables(persona_document.get("activities"), f"{where} activities")):
        if not all(isinstance(value, str) for value in table.values()):
            raise _fail(f"{where} activities[{index}]", "activity values must be strings")
        activities.append(ActivityRow(values=tuple((key, cast(str, value)) for key, value in table.items())))
    elections: list[Election] = []
    for index, table in enumerate(_tables(persona_document.get("elections"), f"{where} elections")):
        here = f"{where} elections[{index}]"
        _keys(table, here, required=frozenset({"question", "value", "year"}))
        elections.append(
            Election(
                question=_string(table, "question", here),
                value=_string(table, "value", here),
                year=YearToken.parse(table["year"], where=f"{here}.year"),
            )
        )
    modelos = _strings(head, "modelos", where)
    own_accounts = tuple(
        _own_account(table, f"{where} own_accounts[{index}]", modelos)
        for index, table in enumerate(_tables(persona_document.get("own_accounts"), where))
    )
    _check_designations(own_accounts, f"{where} own_accounts")
    ledger = _parse_ledger(ledger_text, where=f"{persona_id}/ledger.csv", roles=roles)
    persona = Persona(
        id=persona_id,
        title=_string(head, "title", where),
        summary=_string(head, "summary", where),
        taxpayer=roles(head["taxpayer"], where),
        fiscal_year=YearToken.parse(head["fiscal_year"], where=f"{where}.fiscal_year"),
        modelos=modelos,
        as_of=_date(clock["as_of"], f"{where} [clock].as_of", biographical=False),
        profile=tuple(
            ProfileAnswer(question_id=key, value=_profile_value(key, value, f"{where} [profile].{key}", roles))
            for key, value in profile.items()
        ),
        fields=tuple(FieldValue(path=key, value=cast(str, value)) for key, value in fields.items()),
        activities=tuple(activities),
        elections=tuple(elections),
        descendants=_household(household.get("descendants"), f"{where} descendants", _DESCENDANT_LEAVES, roles),
        ascendants=_household(household.get("ascendants"), f"{where} ascendants", _ASCENDANT_LEAVES, roles),
        household_families=tuple(family for family in ("descendants", "ascendants") if family in household),
        own_accounts=own_accounts,
        withholding_certificates=tuple(
            _withholding(table, f"{where} withholding_certificates[{index}]", roles)
            for index, table in enumerate(_tables(persona_document.get("withholding_certificates"), where))
        ),
        rental_properties=tuple(
            _rental(table, f"{where} rental_properties[{index}]", roles)
            for index, table in enumerate(_tables(persona_document.get("rental_properties"), where))
        ),
        officers=tuple(
            _officer(table, f"{where} officers[{index}]", roles)
            for index, table in enumerate(_tables(persona_document.get("officers"), where))
        ),
        filed_returns=tuple(
            _filed_returns(table, f"{where} filed_returns[{index}]")
            for index, table in enumerate(_tables(persona_document.get("filed_returns"), where))
        ),
        calculated_returns=tuple(
            _calculated_returns(table, f"{where} calculated_returns[{index}]")
            for index, table in enumerate(_tables(persona_document.get("calculated_returns"), where))
        ),
        local_observations=tuple(
            _local_observation(table, f"{where} local_observations[{index}]")
            for index, table in enumerate(_tables(persona_document.get("local_observations"), where))
        ),
        aeat_filings=tuple(
            _aeat_filing(table, f"{where} aeat_filings[{index}]")
            for index, table in enumerate(_tables(persona_document.get("aeat_filings"), where))
        ),
        leased_premises=tuple(
            _leased_premises(table, f"{where} leased_premises[{index}]", roles)
            for index, table in enumerate(_tables(persona_document.get("leased_premises"), where))
        ),
        inventory=tuple(
            _inventory_book(table, f"{where} inventory[{index}]")
            for index, table in enumerate(_tables(persona_document.get("inventory"), where))
        ),
        ledger=ledger,
        documents=_documents(
            documents_document, f"{persona_id}/documents.toml", persona_id, frozenset(row.ref for row in ledger)
        ),
        expectations=_expectations(expectations_document, f"{persona_id}/expectations.toml", persona_id, roles),
        identities=catalogue,
    )
    known_documents = {document.id for document in persona.documents}
    if any(row.document is not None and row.document not in known_documents for row in ledger):
        raise _fail(f"{persona_id}/ledger.csv", "a row names a document documents.toml does not hold")
    named = {row.ref: row.document for row in ledger}
    for document in persona.documents:
        if document.generator is not None and any(named[ref] != document.id for ref in document.attach_to):
            raise _fail(f"{persona_id}/documents.toml", f"{document.id}: its row does not name it in ledger.csv")
    _check_returns(persona)
    _check_inventory(persona)
    if omit_below_floor:
        persona = _without_records_below_floor(persona, envelope)
    _check_years(persona, envelope)
    _check_aeat_filings(persona, envelope)
    return persona


type _DatedRecord = (
    FiledReturns
    | CalculatedReturns
    | LocalObservation
    | AeatFiling
    | ExpectedObligation
    | ExpectedDeadline
    | ExpectedValue
)


def _record_periods(record: _DatedRecord) -> tuple[str, ...]:
    if isinstance(record, FiledReturns | CalculatedReturns | ExpectedObligation):
        return record.periods
    return (record.period,)


def _without_records_below_floor(persona: Persona, envelope: YearEnvelope) -> Persona:
    """``persona`` without its return-history records and expectations below the envelope floor, listing them."""
    dropped: list[BelowFloorRecord] = []

    def kept[Record: _DatedRecord](block: BelowFloorBlock, records: tuple[Record, ...]) -> tuple[Record, ...]:
        inside: list[Record] = []
        for record in records:
            if record.year.precedes_floor(envelope):
                dropped.append(
                    BelowFloorRecord(
                        block=block, modelo=record.modelo, year=record.year, periods=_record_periods(record)
                    )
                )
            else:
                inside.append(record)
        return tuple(inside)

    expectations = persona.expectations
    return dataclasses.replace(
        persona,
        filed_returns=kept("filed_returns", persona.filed_returns),
        calculated_returns=kept("calculated_returns", persona.calculated_returns),
        local_observations=kept("local_observations", persona.local_observations),
        aeat_filings=kept("aeat_filings", persona.aeat_filings),
        expectations=Expectations(
            obligations=kept("expectations.obligations", expectations.obligations),
            deadlines=kept("expectations.deadlines", expectations.deadlines),
            values=kept("expectations.values", expectations.values),
        ),
        below_floor=tuple(dropped),
    )


def _check_returns(persona: Persona) -> None:
    """Refuse a modelo period listed twice across the filed, calculated, observed and AEAT-filed blocks."""
    seen: set[tuple[str, str, str]] = set()
    keys = [
        *((block.modelo, str(block.year), period) for block in persona.filed_returns for period in block.periods),
        *((block.modelo, str(block.year), period) for block in persona.calculated_returns for period in block.periods),
        *((item.modelo, str(item.year), item.period) for item in persona.local_observations),
        *((item.modelo, str(item.year), item.period) for item in persona.aeat_filings),
    ]
    for key in keys:
        if key in seen:
            modelo, year, period = key
            raise _fail(persona.id, f"Modelo {modelo} {year} {period} is listed twice")
        seen.add(key)


def _period_closes(year: int, period: str) -> date:
    """The last day of a filed period of ``year``."""
    if period == "0A":
        return date(year, 12, 31)
    month = 3 * filed_period_order(period) + 3
    return date(year, month, calendar.monthrange(year, month)[1])


def _check_aeat_filings(persona: Persona, envelope: YearEnvelope) -> None:
    """Refuse a return presented before its period closed."""
    for filing in persona.aeat_filings:
        closes = _period_closes(filing.year.resolve(envelope), filing.period)
        if filing.presented.resolve(envelope) <= closes:
            raise _fail(
                persona.id,
                f"Modelo {filing.modelo} {filing.year} {filing.period} is presented before its period closes",
            )


def _check_inventory(persona: Persona) -> None:
    """Refuse two books for one activity and year."""
    books = [(book.activity, str(book.year)) for book in persona.inventory]
    if len(set(books)) != len(books):
        raise _fail(persona.id, "an inventory activity and year is listed twice")


def _dates(persona: Persona) -> list[PersonaDate]:
    found = [persona.as_of]
    found.extend(answer.value for answer in persona.profile if isinstance(answer.value, PersonaDate))
    for member in (*persona.descendants, *persona.ascendants):
        found.extend(value for _key, value in member.leaves if isinstance(value, PersonaDate))
    found.extend(rental.contract_start for rental in persona.rental_properties)
    found.extend(filing.presented for filing in persona.aeat_filings)
    found.extend(deadline.statutory_end for deadline in persona.expectations.deadlines)
    return found


def _check_years(persona: Persona, envelope: YearEnvelope) -> None:
    """Refuse every year that resolves outside the envelope; a biographical date may precede the floor."""
    tokens = [
        persona.fiscal_year,
        *(election.year for election in persona.elections),
        *(certificate.ejercicio for certificate in persona.withholding_certificates),
        *(filed.year for filed in persona.filed_returns),
        *(calculated.year for calculated in persona.calculated_returns),
        *(observation.year for observation in persona.local_observations),
        *(filing.year for filing in persona.aeat_filings),
        *(book.year for book in persona.inventory),
        *(row.year for row in persona.ledger),
        *(item.year for item in persona.expectations.obligations),
        *(item.year for item in persona.expectations.deadlines),
        *(item.year for item in persona.expectations.values),
    ]
    try:
        for token in tokens:
            token.resolve(envelope)
        for persona_date in _dates(persona):
            persona_date.resolve(envelope)
        for row in persona.ledger:
            row.operation_date(envelope)
    except ValueError as error:
        raise _fail(persona.id, str(error)) from None


def read_persona(persona_id: str, *, envelope: YearEnvelope, omit_below_floor: bool = False) -> Persona:
    """Read and validate one persona of the catalogue under the registry's year ``envelope``.

    ``omit_below_floor`` is as :func:`parse_persona` takes it.
    """
    directory = PERSONAS_ROOT / persona_id
    if not (directory / "persona.toml").is_file():
        raise PersonaCatalogueError(f"unknown persona {persona_id!r}")
    return parse_persona(
        persona_id,
        persona_document=_read_toml(directory / "persona.toml"),
        ledger_text=(directory / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_read_toml(directory / "documents.toml"),
        expectations_document=_read_toml(directory / "expectations.toml"),
        catalogue=identity_catalogue(),
        envelope=envelope,
        omit_below_floor=omit_below_floor,
    )


def persona_inputs_digest(persona: Persona) -> str:
    """Digest every file a persona's values come from: its directory, the identity catalogue and its documents."""
    paths = {path for path in (PERSONAS_ROOT / persona.id).rglob("*") if path.is_file()}
    paths.add(PERSONAS_ROOT / "identities.toml")
    paths.update(document.path for document in persona.documents if document.path is not None)
    return file_inputs_digest("persona-inputs", REPO_ROOT, sorted(paths))


__all__ = [
    "BIOGRAPHICAL_DATE_KEYS",
    "CATALOGUE_FORMAT",
    "DECLARATIVE_BLOCKS",
    "LEDGER_ACCRUAL_COLUMNS",
    "LEDGER_COLUMNS",
    "PERSONAS_ROOT",
    "ActivityRow",
    "AeatFiling",
    "BelowFloorBlock",
    "BelowFloorRecord",
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
    "ProfileAnswer",
    "ProfileValue",
    "ProvisionPeriods",
    "RentalProperty",
    "WithholdingCertificate",
    "YearEnvelope",
    "YearToken",
    "cadastral_control_characters",
    "filed_period_order",
    "governed_provisions",
    "identity_catalogue",
    "parse_identity_catalogue",
    "parse_persona",
    "persona_ids",
    "persona_inputs_digest",
    "read_persona",
    "values_in_force",
]
