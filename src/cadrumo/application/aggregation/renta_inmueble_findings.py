"""What stops or limits a property's ``Inmueble`` occurrence, and the command that settles it.

A finding has one of three weights. A refusal means the occurrence cannot be
built from what the records state: no row of the return is emitted, because a
property missing from a numbered block would renumber the others. A blocking
finding keeps the rows, which are right as far as they go, and withholds
checking, export and filing until it is settled. A limitation names a part of
the occurrence the calculation does not offer; it withholds nothing.

Every refusal and blocking finding names the command that settles it. A
limitation has none: there is nothing for the filer to do but enter the figure
by hand where it applies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class RentaInmuebleFindingKind(StrEnum):
    """How much a finding withholds."""

    REFUSAL = "refusal"
    BLOCKING = "blocking"
    LIMITATION = "limitation"


class RentaInmuebleDoor(StrEnum):
    """The command, below the program name, that settles a finding."""

    INMUEBLE_ADD = "config profile inmueble add"
    INMUEBLE_EDIT = "config profile inmueble edit"
    ARRENDAMIENTO_ADD = "config profile arrendamiento add"
    ARRENDAMIENTO_EDIT = "config profile arrendamiento edit"
    LEDGER_CLASSIFY = "app ledger classify"
    ATTEST_NO_AMOUNT = "app modelo work attest-no-amount"

    @property
    def path(self) -> tuple[str, ...]:
        """Return the command path as the live command tree addresses it."""
        return tuple(self.value.split(" "))

    @property
    def takes_row(self) -> bool:
        """Whether the command names the property row it settles with ``--row``."""
        return self is RentaInmuebleDoor.ATTEST_NO_AMOUNT


class RentaInmuebleCause(StrEnum):
    """Why an occurrence is refused, blocked or limited."""

    RECORD_UNREADABLE = "record_unreadable"
    TITULARIDAD_UNSTATED = "titularidad_unstated"
    ACQUISITION_DATE_UNSTATED = "acquisition_date_unstated"
    NATURALEZA_UNSTATED = "naturaleza_unstated"
    LEASE_NAMES_NO_PROPERTY = "lease_names_no_property"
    ROW_NAMES_NO_LEASE = "row_names_no_lease"
    ROW_NAMES_NO_PROPERTY = "row_names_no_property"
    INCOME_ROW_ON_PROPERTY = "income_row_on_property"
    EXPENSE_ROW_ON_LEASE = "expense_row_on_lease"
    EXPENSE_ROW_WITHOUT_CONCEPT = "expense_row_without_concept"
    CONCEPT_UNDECLARED = "concept_undeclared"
    INCOME_OUTSIDE_LEASE = "income_outside_lease"
    LEASE_WITHOUT_INCOME = "lease_without_income"
    RELATIVE_FACT_UNSTATED = "relative_fact_unstated"
    CURRENCY_UNCONVERTED = "currency_unconverted"
    REGIME_NOT_PLENO_DOMINIO = "regime_not_pleno_dominio"
    TITULAR_NOT_DECLARANT = "titular_not_declarant"
    PROPERTY_ABROAD_LET = "property_abroad_let"
    ACCESSORY_PROPERTY = "accessory_property"
    CONCURRENT_LEASES = "concurrent_leases"
    SEVERAL_LEASES = "several_leases"
    TENANTS_BEYOND_NUMBERED = "tenants_beyond_numbered"
    RELATIVE_TENANT = "relative_tenant"
    IMPROVEMENT_IN_EJERCICIO = "improvement_in_ejercicio"
    HELD_PART_OF_EJERCICIO = "held_part_of_ejercicio"
    DAYS_UNACCOUNTED = "days_unaccounted"
    IMPUTACION_VALOR_CATASTRAL_UNSTATED = "imputacion_valor_catastral_unstated"
    IMPUTACION_VIGOR_UNSTATED = "imputacion_vigor_unstated"
    IMPUTACION_USO_SIMULTANEO = "imputacion_uso_simultaneo"
    IMPUTACION_RUSTICA = "imputacion_rustica"
    ACQUISITION_COST_UNSTATED = "acquisition_cost_unstated"
    CADASTRAL_VALUES_UNSTATED = "cadastral_values_unstated"
    CUMULATIVE_AMORTISATION_UNSTATED = "cumulative_amortisation_unstated"
    LETTING_START_UNSTATED = "letting_start_unstated"
    PENDING_EXPENSES_UNSTATED = "pending_expenses_unstated"
    PENDING_EXPENSES_HELD_RETURN_UNSTATED = "pending_expenses_held_return_unstated"
    PENDING_EXPENSES_TOTAL_UNSPLIT = "pending_expenses_total_unsplit"
    REDUCTION_FACT_UNSTATED = "reduction_fact_unstated"
    REDUCTION_TENANTS_MIXED = "reduction_tenants_mixed"
    WITHHOLDING_PAYER_NO_TENANT = "withholding_payer_no_tenant"
    WITHHOLDING_PAYER_SEVERAL_PROPERTIES = "withholding_payer_several_properties"
    BOXES_NOT_OFFERED = "boxes_not_offered"


_REFUSAL: Final = RentaInmuebleFindingKind.REFUSAL
_BLOCKING: Final = RentaInmuebleFindingKind.BLOCKING
_LIMITATION: Final = RentaInmuebleFindingKind.LIMITATION

_CAUSE_TERMS: Final[dict[RentaInmuebleCause, tuple[RentaInmuebleFindingKind, RentaInmuebleDoor | None, str]]] = {
    RentaInmuebleCause.RECORD_UNREADABLE: (
        _REFUSAL,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "a property or lease record of the profile cannot be read",
    ),
    RentaInmuebleCause.TITULARIDAD_UNSTATED: (
        _REFUSAL,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property does not state who holds it and in what right",
    ),
    RentaInmuebleCause.ACQUISITION_DATE_UNSTATED: (
        _REFUSAL,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property does not state when it was acquired, so the days it was held are unknown",
    ),
    RentaInmuebleCause.NATURALEZA_UNSTATED: (
        _REFUSAL,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property does not state whether it is urban or rustic",
    ),
    RentaInmuebleCause.LEASE_NAMES_NO_PROPERTY: (
        _REFUSAL,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "a lease names a property the profile does not hold",
    ),
    RentaInmuebleCause.ROW_NAMES_NO_LEASE: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "a ledger row is linked to a lease the profile does not hold",
    ),
    RentaInmuebleCause.ROW_NAMES_NO_PROPERTY: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "a ledger row is linked to a property the profile does not hold",
    ),
    RentaInmuebleCause.INCOME_ROW_ON_PROPERTY: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "an incoming ledger row is linked to a property; rent is linked to its lease",
    ),
    RentaInmuebleCause.EXPENSE_ROW_ON_LEASE: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "an outgoing ledger row is linked to a lease; an expense is linked to its property",
    ),
    RentaInmuebleCause.EXPENSE_ROW_WITHOUT_CONCEPT: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "a ledger row linked to a property does not state its expense concept",
    ),
    RentaInmuebleCause.CONCEPT_UNDECLARED: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "a ledger row states an expense concept the ejercicio's vocabulary does not declare",
    ),
    RentaInmuebleCause.INCOME_OUTSIDE_LEASE: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "a rent row is dated outside the period of the lease it is linked to",
    ),
    RentaInmuebleCause.LEASE_WITHOUT_INCOME: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "a lease active in the ejercicio has no rent row linked to it",
    ),
    RentaInmuebleCause.RELATIVE_FACT_UNSTATED: (
        _REFUSAL,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "a lease active in the ejercicio does not state whether the tenant is a relative under art. 24 LIRPF",
    ),
    RentaInmuebleCause.CURRENCY_UNCONVERTED: (
        _REFUSAL,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "a linked ledger row is in a foreign currency with no euro value",
    ),
    RentaInmuebleCause.REGIME_NOT_PLENO_DOMINIO: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property is held in a right other than pleno dominio, which the calculation does not offer",
    ),
    RentaInmuebleCause.TITULAR_NOT_DECLARANT: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property belongs to a member of the family unit other than the declarant",
    ),
    RentaInmuebleCause.PROPERTY_ABROAD_LET: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "a property abroad is let, and its foreign-source treatment is not offered",
    ),
    RentaInmuebleCause.ACCESSORY_PROPERTY: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "an accessory property is let with its principal, which the calculation does not offer",
    ),
    RentaInmuebleCause.CONCURRENT_LEASES: (
        _BLOCKING,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "two leases of the property share a day",
    ),
    RentaInmuebleCause.SEVERAL_LEASES: (
        _BLOCKING,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "the property has more than one lease in the ejercicio, which the return cannot yet carry per contract",
    ),
    RentaInmuebleCause.TENANTS_BEYOND_NUMBERED: (
        _BLOCKING,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "a lease states more tenants than the numbered tenant boxes hold",
    ),
    RentaInmuebleCause.RELATIVE_TENANT: (
        _BLOCKING,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "the tenant is a relative under art. 24 LIRPF, whose minimum yield is not computed",
    ),
    RentaInmuebleCause.IMPROVEMENT_IN_EJERCICIO: (
        _BLOCKING,
        RentaInmuebleDoor.LEDGER_CLASSIFY,
        "an improvement is dated inside the ejercicio, and its amortisation days are not computed",
    ),
    RentaInmuebleCause.HELD_PART_OF_EJERCICIO: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property was acquired or transmitted inside the ejercicio, and its expense proration is not offered",
    ),
    RentaInmuebleCause.DAYS_UNACCOUNTED: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property was held on days it was neither let nor in a stated use, so whether those days impute "
        "income under art. 85 LIRPF is unknown",
    ),
    RentaInmuebleCause.IMPUTACION_VALOR_CATASTRAL_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property was at its owner's disposal and states no cadastral value for the ejercicio; a property "
        "without one, or whose value was not notified, imputes on half its acquisition or checked value, which "
        "the Inmueble boxes do not carry, so its imputed income is not computed",
    ),
    RentaInmuebleCause.IMPUTACION_VIGOR_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property was at its owner's disposal and does not state the year the collective valuation behind "
        "the ejercicio's cadastral value entered into force, so the art. 85 rate is unknown",
    ),
    RentaInmuebleCause.IMPUTACION_USO_SIMULTANEO: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the property was at its owner's disposal on days it was also let or in another use, and the imputed "
        "income of that simultaneous use (casillas 0086 to 0088) is not computed",
    ),
    RentaInmuebleCause.IMPUTACION_RUSTICA: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "a rustic property was at its owner's disposal; it imputes income only for constructions not "
        "indispensable to farming, which the record does not state, so its imputed income is not computed",
    ),
    RentaInmuebleCause.ACQUISITION_COST_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the let property does not state its acquisition amount and acquisition expenses, "
        "so its building amortisation is not computed",
    ),
    RentaInmuebleCause.CADASTRAL_VALUES_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the let property states neither its land value nor the ejercicio's cadastral values, "
        "so the land cannot be excluded from its amortisation base",
    ),
    RentaInmuebleCause.CUMULATIVE_AMORTISATION_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the amortisation of the let property may reach its acquisition value, and the cumulative "
        "amortisation at the first day of the ejercicio is not stated",
    ),
    RentaInmuebleCause.LETTING_START_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.INMUEBLE_EDIT,
        "the let property does not state when it was first let, so the earlier ejercicios whose interest "
        "and repair excess it may still carry (LIRPF art. 23.1.a.1.º) are unknown",
    ),
    RentaInmuebleCause.PENDING_EXPENSES_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.ATTEST_NO_AMOUNT,
        "the property was let before the ejercicio, and the interest and repair expenses one earlier "
        "ejercicio of the carry window left pending on it are not stated, and no earlier return the "
        "application holds states them",
    ),
    RentaInmuebleCause.PENDING_EXPENSES_HELD_RETURN_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.ATTEST_NO_AMOUNT,
        "the property was let before the ejercicio and the return of the previous ejercicio is held, but it "
        "is not read for the interest and repair expenses one earlier ejercicio left pending on the "
        "property, so they must be stated",
    ),
    RentaInmuebleCause.PENDING_EXPENSES_TOTAL_UNSPLIT: (
        _BLOCKING,
        RentaInmuebleDoor.ATTEST_NO_AMOUNT,
        "an amount still pending on the let property was stated as one total, and anexo C.1 needs it split "
        "by the ejercicio it arose in (LIRPF art. 23.1.a.1.º; RIRPF art. 13.a), so each origin year's "
        "amount must be stated",
    ),
    RentaInmuebleCause.REDUCTION_FACT_UNSTATED: (
        _BLOCKING,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "a lease does not state whether it is for a dwelling, whether the dwelling is in a tensioned "
        "zone or whether it keeps art. 17.6 LAU, so the art. 23.2 reduction is not computed",
    ),
    RentaInmuebleCause.REDUCTION_TENANTS_MIXED: (
        _BLOCKING,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "only some tenants of a lease qualify for the art. 23.2 reduction by age, which is not computed",
    ),
    RentaInmuebleCause.WITHHOLDING_PAYER_NO_TENANT: (
        _BLOCKING,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "a withholding on urban rent names a payer who is not a tenant of any lease of the ejercicio",
    ),
    RentaInmuebleCause.WITHHOLDING_PAYER_SEVERAL_PROPERTIES: (
        _BLOCKING,
        RentaInmuebleDoor.ARRENDAMIENTO_EDIT,
        "a withholding on urban rent names a payer who is a tenant of more than one property, "
        "so the property it belongs to is unknown",
    ),
    RentaInmuebleCause.BOXES_NOT_OFFERED: (
        _LIMITATION,
        None,
        "furniture amortisation, the art. 23.3 reduction and special-case amortisation are not offered; "
        "enter them by hand where they apply",
    ),
}


@dataclass(frozen=True, slots=True)
class RentaInmuebleFinding:
    """One reason an occurrence is refused, blocked or limited, and the subject it names."""

    cause: RentaInmuebleCause
    subject: str
    """The record the finding speaks of: ``inmueble:{n}``, ``arrendamiento:{n}`` or ``transaction:{id}``."""
    back: int | None = None
    """The origin year a pending-expense finding speaks of, counted back from the ejercicio filed."""

    @property
    def kind(self) -> RentaInmuebleFindingKind:
        """Return how much this finding withholds."""
        return _CAUSE_TERMS[self.cause][0]

    @property
    def door(self) -> RentaInmuebleDoor | None:
        """Return the command that settles the finding, or ``None`` for one the filer cannot settle."""
        return _CAUSE_TERMS[self.cause][1]

    @property
    def message(self) -> str:
        """Return the technical account of the finding, naming its subject."""
        origin = "" if self.back is None else f" (origin {self.back} ejercicios back)"
        return f"{self.subject}{origin}: {_CAUSE_TERMS[self.cause][2]}"


__all__ = [
    "RentaInmuebleCause",
    "RentaInmuebleDoor",
    "RentaInmuebleFinding",
    "RentaInmuebleFindingKind",
]
