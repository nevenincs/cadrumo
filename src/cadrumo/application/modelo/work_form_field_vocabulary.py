"""The closed vocabulary one editor-form field is classified by.

Where a field's value stands (:class:`ModeloFormOrigin`) and where the box
stands for the filer (:class:`ModeloFormStanding`), what may be done about it
(:class:`ModeloFormEditability`), how a displayed text discloses its source
(:class:`ModeloFormTextDisclosure`), and the semantic address, bindings,
blockers, value source and rates a field carries.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal

from pydantic import Field

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.period import Period
from ...domain.calculations.registry.ids import BindingId
from .source_policy import SourceFamily, SourcePolicyV1
from .work_form_declaration_facts import ModeloFormBase

type ModeloFormScalar = Decimal | int | str | bool | date | None
"""A field's value as the calculation holds it; ``None`` only when there is none."""


class ModeloFormTextDisclosure(StrEnum):
    """Which catalogue coordinate a displayed text came from."""

    #: Translated into the requested language.
    LOCALIZED = "localized"
    #: The Spanish source text, shown because no translation exists yet.
    SPANISH_FALLBACK = "spanish_fallback"
    #: The official design's Spanish words, quoted verbatim.
    OFFICIAL_SPANISH = "official_spanish"
    #: A technical name, shown because no human text exists.
    TECHNICAL = "technical"
    #: The form gives the field no name: the text says so in the requested language, and the
    #: field's identifier stays in its address, never on its label.
    UNNAMED = "unnamed"


class ModeloFormText(ModeloFormBase):
    """One displayed text and the honest account of where it came from."""

    text: str = Field(min_length=1)
    disclosure: ModeloFormTextDisclosure


class ModeloFormOrigin(StrEnum):
    """Where one field's value stands; exactly one per field."""

    #: The registry proves the value does not apply to this filer or period.
    NOT_APPLICABLE = "not_applicable"
    #: The filer's value replaces what a source or the calculation produced.
    OVERRIDES_SOURCE = "overrides_source"
    CALCULATED = "calculated"
    #: A calculated box on a work unit that has not been calculated yet.
    NOT_CALCULATED_YET = "not_calculated_yet"
    #: A calculated box the last calculation could not produce.
    CALCULATION_FAILED = "calculation_failed"
    #: Identification or projection figures that are shown, not declared.
    INFORMATIONAL = "informational"
    #: A box the declaration needs and nobody has filled.
    NEEDS_INPUT = "needs_input"
    IMPORTED = "imported"
    #: A box a source should fill and has not.
    NOT_IMPORTED_YET = "not_imported_yet"
    OPTIONAL_EMPTY = "optional_empty"
    #: The filer explicitly removed a value they had declared.
    CLEARED = "cleared"
    #: A value the calculation holds that nobody is proven to have entered.
    DEFAULT_TO_CONFIRM = "default_to_confirm"
    ENTERED = "entered"


ABSENT_FROM_ADMISSION: Final[str] = "absent_from_admission"
"""The not-writable reason of a field the edit admission does not name at all."""


class ModeloFormStanding(StrEnum):
    """Where one box stands on the filing journey, as every frontend that counts boxes classes it."""

    #: The filer has something to do about it: give a value, confirm one, or resolve why it failed.
    NEEDS_YOU = "needs_you"
    #: It waits on a step the filer runs, an import or a calculation, not on anything typed into it.
    WAITING = "waiting"
    #: Nothing is left to do about it.
    DONE = "done"


ORIGIN_STANDINGS: Final[Mapping[ModeloFormOrigin, ModeloFormStanding]] = MappingProxyType(
    {
        ModeloFormOrigin.NEEDS_INPUT: ModeloFormStanding.NEEDS_YOU,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: ModeloFormStanding.NEEDS_YOU,
        ModeloFormOrigin.CALCULATION_FAILED: ModeloFormStanding.NEEDS_YOU,
        ModeloFormOrigin.NOT_IMPORTED_YET: ModeloFormStanding.WAITING,
        ModeloFormOrigin.NOT_CALCULATED_YET: ModeloFormStanding.WAITING,
        ModeloFormOrigin.NOT_APPLICABLE: ModeloFormStanding.DONE,
        ModeloFormOrigin.OVERRIDES_SOURCE: ModeloFormStanding.DONE,
        ModeloFormOrigin.CALCULATED: ModeloFormStanding.DONE,
        ModeloFormOrigin.INFORMATIONAL: ModeloFormStanding.DONE,
        ModeloFormOrigin.IMPORTED: ModeloFormStanding.DONE,
        ModeloFormOrigin.OPTIONAL_EMPTY: ModeloFormStanding.DONE,
        ModeloFormOrigin.CLEARED: ModeloFormStanding.DONE,
        ModeloFormOrigin.ENTERED: ModeloFormStanding.DONE,
    }
)
"""The one classing of every origin that every count, heading, row and next-box move shares."""

#: Origins that ask the filer to act before the declaration is ready.
NEEDS_ATTENTION: Final[frozenset[ModeloFormOrigin]] = frozenset(
    origin for origin, standing in ORIGIN_STANDINGS.items() if standing is ModeloFormStanding.NEEDS_YOU
)
#: Origins that ask the filer for a value, which neither a filed declaration nor a page that does not apply does.
ASKS_FOR_A_VALUE: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.NEEDS_INPUT, ModeloFormOrigin.DEFAULT_TO_CONFIRM}
)
#: Origins whose words say there is no value, whatever the field still holds.
ORIGINS_WITHOUT_A_VALUE: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {
        ModeloFormOrigin.NOT_APPLICABLE,
        ModeloFormOrigin.NOT_CALCULATED_YET,
        ModeloFormOrigin.CALCULATION_FAILED,
        ModeloFormOrigin.NOT_IMPORTED_YET,
        ModeloFormOrigin.CLEARED,
    }
)
#: Origins of a box a source feeds, whether the source has filled it yet or not.
FED_BY_A_SOURCE: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.NOT_IMPORTED_YET}
)


def field_standing(
    origin: ModeloFormOrigin,
    blockers: tuple[ModeloFormBlocker, ...] | list[ModeloFormBlocker] = (),
    *,
    recorded: bool = False,
    applies: bool = True,
) -> ModeloFormStanding:
    """Where a box stands for the filer, on its declaration and page.

    On a declaration recorded as filed nothing is left to do, a blocker always
    needs the filer, and a page that does not apply asks for no value. A box
    waiting on an import or a calculation waits: running that step fills it,
    not anything the filer types into it.
    """
    if recorded:
        return ModeloFormStanding.DONE
    if blockers:
        return ModeloFormStanding.NEEDS_YOU
    if not applies and origin in ASKS_FOR_A_VALUE:
        return ModeloFormStanding.DONE
    return ORIGIN_STANDINGS[origin]


def fitting_standings(
    origin: ModeloFormOrigin, blockers: tuple[ModeloFormBlocker, ...] | list[ModeloFormBlocker] = ()
) -> frozenset[ModeloFormStanding]:
    """Every standing a box of this origin and blockers can have, on some declaration and page."""
    return frozenset(
        field_standing(origin, blockers, recorded=recorded, applies=applies)
        for recorded in (False, True)
        for applies in (True, False)
    )


class ModeloFormEditability(StrEnum):
    """What may be done about one field's value; exactly one per field."""

    #: The filer types the value.
    EDITABLE_VALUE = "editable_value"
    #: The filer types the value of a binding no casilla owns.
    EDITABLE_OVERRIDE = "editable_override"
    #: A carried source value the filer may replace, with a reason.
    OVERRIDABLE_SOURCE = "overridable_source"
    #: A value that follows the filer's records and is corrected there.
    LOCKED_SOURCE = "locked_source"
    #: A source nobody has yet decided a filer may replace.
    SOURCE_POLICY_UNDECIDED = "source_policy_undecided"
    #: A profile fact, corrected once in the profile.
    EDIT_AT_PROFILE = "edit_at_profile"
    CALCULATED = "calculated"
    #: A value the official design fixes.
    DESIGN_CONSTANT = "design_constant"
    INFORMATIONAL = "informational"
    #: The edit admission declares the address read-only, with its reason.
    NOT_WRITABLE = "not_writable"
    #: No edit admission is available for this form.
    NO_ADMISSION = "no_admission"


class ModeloFormCasillaAddressV1(ModeloFormBase):
    """A field addressed by its casilla."""

    kind: Literal["casilla"] = "casilla"
    casilla_id: CasillaId


class ModeloFormBindingAddressV1(ModeloFormBase):
    """A field addressed by a binding no casilla owns."""

    kind: Literal["binding"] = "binding"
    binding_id: BindingId


type ModeloFormAddressV1 = Annotated[
    ModeloFormCasillaAddressV1 | ModeloFormBindingAddressV1, Field(discriminator="kind")
]
"""A field's semantic address; focus, staging and review key on it, never on position."""


def address_key(address: ModeloFormAddressV1) -> tuple[str, str]:
    """Return the hashable identity of one address."""
    if isinstance(address, ModeloFormCasillaAddressV1):
        return ("casilla", address.casilla_id)
    return ("binding", address.binding_id)


class ModeloFormBinding(ModeloFormBase):
    """One binding that feeds a field, with its source's policy and whether it resolved."""

    binding_id: BindingId
    policy: SourcePolicyV1
    resolved: bool


class ModeloFormBlocker(ModeloFormBase):
    """One verification finding that blocks the field."""

    code: str = Field(min_length=1)


class ModeloFormEarlierFiling(ModeloFormBase):
    """One earlier declaration a carried value is read from."""

    modelo: str = Field(min_length=1)
    #: The earlier declaration's filing year and period.
    period: Period


class ModeloFormValueSource(ModeloFormBase):
    """Where a field's value comes from, named from its primary binding.

    ``family`` is the kind of place a filer thinks of: their records, a register
    they keep, their profile, an earlier filing, the AEAT tax data, a value they
    type, or a value the official form fixes. A value the calculation took from
    an imported AEAT draft reads as AEAT data, whatever its binding would
    otherwise fetch. ``earlier_filings`` names the declarations a carried value
    is read from when the binding identifies them, and is empty otherwise; it
    never guesses one. ``binding_id`` is ``None`` for a value no binding feeds: one the
    declared layout fixes, or one a resolver supplied to the box directly, which
    names that resolver's ``source_kind``. Both are ``None`` for the fixed value.
    """

    family: SourceFamily
    binding_id: BindingId | None = None
    source_kind: BindingSourceKind | None = None
    earlier_filings: tuple[ModeloFormEarlierFiling, ...] = ()


class ModeloFormRateUnit(StrEnum):
    """The unit a rate is stated in."""

    #: Stated as a fraction of one, so ``0.04`` is four per cent.
    FRACTION = "fraction"


class ModeloFormRate(ModeloFormBase):
    """The one rate a printed rate box stands for, grounded on the binding that fills its row's base.

    A rate-specific base binding accepts only records taxed at the rates it
    declares; when it declares exactly one, that is the rate the row applies
    and the rate box prints. ``binding_id`` is that base binding.
    """

    ratio: Decimal = Field(ge=Decimal(0), le=Decimal(1))
    unit: ModeloFormRateUnit = ModeloFormRateUnit.FRACTION
    binding_id: BindingId

    def percent(self) -> Decimal:
        """The rate in per cent, as the printed form states it."""
        return self.ratio * 100


class ModeloFormPrintedRate(ModeloFormBase):
    """The rate the official design prints in a rate box it fixes, read from the design's own literal.

    A literal is read only where its scale is declared: it states a percentage
    outright ("21 %"), or the export field that writes it declares its implied
    decimals and the casilla's bounds say whether the figure is a percentage or
    a fraction. Nothing is inferred from other rows. A literal of zeros is the
    design's placeholder, never a rate. It says what the form prints, not that
    the calculation applies it.
    """

    ratio: Decimal = Field(gt=Decimal(0), le=Decimal(1))
    unit: ModeloFormRateUnit = ModeloFormRateUnit.FRACTION
    literal: str = Field(min_length=1)

    def percent(self) -> Decimal:
        """The rate in per cent, as the printed form states it."""
        return self.ratio * 100


TYPED_EDITABILITIES: Final[frozenset[ModeloFormEditability]] = frozenset(
    {
        ModeloFormEditability.EDITABLE_VALUE,
        ModeloFormEditability.EDITABLE_OVERRIDE,
        ModeloFormEditability.OVERRIDABLE_SOURCE,
    }
)
"""Editabilities under which the filer may type a value on the field itself."""


__all__ = [
    "ABSENT_FROM_ADMISSION",
    "ASKS_FOR_A_VALUE",
    "FED_BY_A_SOURCE",
    "NEEDS_ATTENTION",
    "ORIGINS_WITHOUT_A_VALUE",
    "ORIGIN_STANDINGS",
    "TYPED_EDITABILITIES",
    "ModeloFormAddressV1",
    "ModeloFormBinding",
    "ModeloFormBindingAddressV1",
    "ModeloFormBlocker",
    "ModeloFormCasillaAddressV1",
    "ModeloFormEarlierFiling",
    "ModeloFormEditability",
    "ModeloFormOrigin",
    "ModeloFormPrintedRate",
    "ModeloFormRate",
    "ModeloFormRateUnit",
    "ModeloFormScalar",
    "ModeloFormStanding",
    "ModeloFormText",
    "ModeloFormTextDisclosure",
    "ModeloFormValueSource",
    "address_key",
    "field_standing",
    "fitting_standings",
]
