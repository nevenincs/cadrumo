"""The editor form of one modelo work target, as a person reads and edits it.

The form is the canonical work review arranged by the revision's declared form
layout and classified for an editor: every casilla sits on a page and section
the official form names, or among the working figures the form does not print,
or in the unplaced list with its reason. Every field carries its official box
number, its localized label and help, its value, one origin state and one
editability classification, so a frontend renders the form and never decides
what a value means or whether it may change.

The two classifications are closed application vocabulary:

* :class:`ModeloFormOrigin` says where the value stands: entered by the filer,
  imported from a source, calculated, still needed, not applicable by design,
  and the other states a filer must be able to tell apart. "Nothing was
  entered" and "zero was entered" are different origins, never one figure.
* :class:`ModeloFormEditability` says what may be done about it: type a value,
  override a source with a reason, fix it at its source, correct it in the
  profile, or nothing because it is calculated or fixed by the official design.

Every text a person reads carries its :class:`ModeloFormTextDisclosure`, so a
Spanish fallback, a verbatim official heading or a technical name is never
passed off as a translation.

Beside the fields, the form states the facts a filer asks about the whole
declaration: where each bound value comes from (:class:`ModeloFormValueSource`),
whether the calculation replayed AEAT tax data (:class:`ModeloFormAeatData`),
the last day to file (:class:`ModeloFormDeadline`), the settled result and its
direction (:class:`ModeloFormResult`), and whether the declaration is recorded
as filed (:class:`ModeloFormFiling`). Each is classified here from declared
facts, so a frontend only renders it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.ids import BindingId, FormulaId, LegalRefId, RevisionId
from ...domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormLayoutSeedSource,
    FormPageCondition,
    FormUnplacedReason,
)
from ...domain.calculations.registry.schema_surfaces import CasillaConstraints
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from .calculation_report import CalculationReportRowRole
from .edit_apply_scalar_contracts import ModeloEditWireScalar, wire_scalar_value
from .source_policy import SourceFamily, SourceOverridePolicy, SourcePolicyV1, SourceSurface
from .work_review import ModeloWorkProgress

type ModeloFormScalar = Decimal | int | str | bool | date | None
"""A field's value as the calculation holds it; ``None`` only when there is none."""


class _FormModel(BaseModel):
    model_config = STRICT_FROZEN_CONFIG


class ModeloFormLayoutProvenance(StrEnum):
    """Where the form's arrangement comes from."""

    #: A declared layout a named person reviewed.
    REVIEWED = "reviewed"
    #: A declared layout generated from official sources and not yet reviewed.
    GENERATED = "generated"
    #: No usable declared layout: a read-only list in box order, with its reason.
    INSPECTION_ONLY = "inspection_only"


class ModeloFormInspectionReason(StrEnum):
    """Why a form could only be inspected."""

    LAYOUT_ABSENT = "layout_absent"
    LAYOUT_FOR_ANOTHER_REVISION = "layout_for_another_revision"


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


class ModeloFormText(_FormModel):
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


def _default_standing(data: dict[str, Any]) -> ModeloFormStanding:
    origin = data.get("origin")
    if not isinstance(origin, ModeloFormOrigin):
        raise ValueError("a field's standing is derived from its origin")
    return field_standing(origin, data.get("blockers", ()))


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


class ModeloFormCasillaAddressV1(_FormModel):
    """A field addressed by its casilla."""

    kind: Literal["casilla"] = "casilla"
    casilla_id: CasillaId


class ModeloFormBindingAddressV1(_FormModel):
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


class ModeloFormBinding(_FormModel):
    """One binding that feeds a field, with its source's policy and whether it resolved."""

    binding_id: BindingId
    policy: SourcePolicyV1
    resolved: bool


class ModeloFormBlocker(_FormModel):
    """One verification finding that blocks the field."""

    code: str = Field(min_length=1)


class ModeloFormEarlierFiling(_FormModel):
    """One earlier declaration a carried value is read from."""

    modelo: str = Field(min_length=1)
    #: The earlier declaration's filing year and period.
    period: Period


class ModeloFormValueSource(_FormModel):
    """Where a field's value comes from, named from its primary binding.

    ``family`` is the kind of place a filer thinks of: their records, a register
    they keep, their profile, an earlier filing, the AEAT tax data, a value they
    type, or a value the official form fixes. A value the calculation took from
    an imported AEAT draft reads as AEAT data, whatever its binding would
    otherwise fetch. ``earlier_filings`` names the declarations a carried value
    is read from when the binding identifies them, and is empty otherwise; it
    never guesses one. ``binding_id`` and ``source_kind`` are ``None`` only for a
    value the declared layout fixes without any binding.
    """

    family: SourceFamily
    binding_id: BindingId | None = None
    source_kind: BindingSourceKind | None = None
    earlier_filings: tuple[ModeloFormEarlierFiling, ...] = ()


class ModeloFormRateUnit(StrEnum):
    """The unit a rate is stated in."""

    #: Stated as a fraction of one, so ``0.04`` is four per cent.
    FRACTION = "fraction"


class ModeloFormRate(_FormModel):
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


class ModeloFormPrintedRate(_FormModel):
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


_OVERRIDE_EDITABILITIES = frozenset({ModeloFormEditability.OVERRIDABLE_SOURCE, ModeloFormEditability.EDITABLE_OVERRIDE})
_CONFIRMING_EDITABILITIES = frozenset({ModeloFormEditability.EDITABLE_VALUE, ModeloFormEditability.EDITABLE_OVERRIDE})


def _edit_address_of(
    address: ModeloFormAddressV1,
    editability: ModeloFormEditability,
    bindings: tuple[ModeloFormBinding, ...] | list[ModeloFormBinding],
) -> ModeloFormAddressV1:
    if isinstance(address, ModeloFormCasillaAddressV1) and editability in _OVERRIDE_EDITABILITIES and bindings:
        return ModeloFormBindingAddressV1(binding_id=bindings[0].binding_id)
    return address


def _typed_by_the_filer_of(bindings: tuple[ModeloFormBinding, ...] | list[ModeloFormBinding]) -> bool:
    return all(binding.policy.override_policy is SourceOverridePolicy.ENTER for binding in bindings)


def _confirmable_of(data: dict[str, Any]) -> bool:
    address = data["address"]
    editability = data["editability"]
    bindings = data.get("bindings", ())
    return (
        data["origin"] is ModeloFormOrigin.DEFAULT_TO_CONFIRM
        and data["value"] is not None
        and _typed_by_the_filer_of(bindings)
        and editability in _CONFIRMING_EDITABILITIES
        and _edit_address_of(address, editability, bindings) == address
    )


def holds_zero(value: ModeloFormScalar) -> bool:
    """Whether a value is an amount of exactly zero: a figure the form holds, which is not the same as nothing."""
    return isinstance(value, Decimal | int) and not isinstance(value, bool) and value == 0


def _default_edit_address(data: dict[str, Any]) -> ModeloFormAddressV1:
    return _edit_address_of(data["address"], data["editability"], data.get("bindings", ()))


def _default_held_zero(data: dict[str, Any]) -> bool:
    return holds_zero(data.get("value"))


_FILERS_OWN_ORIGINS = frozenset({ModeloFormOrigin.OVERRIDES_SOURCE, ModeloFormOrigin.ENTERED})

TYPED_EDITABILITIES: Final[frozenset[ModeloFormEditability]] = frozenset(
    {
        ModeloFormEditability.EDITABLE_VALUE,
        ModeloFormEditability.EDITABLE_OVERRIDE,
        ModeloFormEditability.OVERRIDABLE_SOURCE,
    }
)
"""Editabilities under which the filer may type a value on the field itself."""


def comparable_entry(value: ModeloFormScalar) -> ModeloEditWireScalar:
    """A value as two entries of it compare: an amount by its figure, whatever trailing zeros it was written with.

    ``1234.5`` and ``1234.50`` are the same figure, so they compare equal here,
    as they do as numbers; every other kind of value compares as it is.
    """
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return None if value is None else wire_scalar_value(value)


def _takes_typed_value_of(data: dict[str, Any]) -> bool:
    return data["editability"] in TYPED_EDITABILITIES


def _clearable_of(data: dict[str, Any]) -> bool:
    return data["editability"] is ModeloFormEditability.EDITABLE_VALUE and data["origin"] is ModeloFormOrigin.ENTERED


def _own_value_of(data: dict[str, Any]) -> ModeloEditWireScalar:
    return comparable_entry(data["value"]) if data["origin"] in _FILERS_OWN_ORIGINS else None


def _confirm_comparable_of(data: dict[str, Any]) -> ModeloEditWireScalar:
    value = data["value"]
    return comparable_entry(value) if value is not None and _confirmable_of(data) else None


def _state_digest_of(data: dict[str, Any]) -> str:
    value = comparable_entry(data["value"])
    seen = json.dumps([data["origin"].value, type(value).__name__, None if value is None else str(value)])
    return hashlib.sha256(seen.encode("utf-8")).hexdigest()


def _filers_own_of(data: dict[str, Any]) -> bool:
    return data["origin"] in _FILERS_OWN_ORIGINS


def _restorable_of(data: dict[str, Any]) -> bool:
    return data["editability"] in _OVERRIDE_EDITABILITIES and _filers_own_of(data)


def _confirm_value_of(data: dict[str, Any]) -> ModeloEditWireScalar:
    value = data["value"]
    return wire_scalar_value(value) if value is not None and _confirmable_of(data) else None


class ModeloFormField(_FormModel):
    """One box or binding input, classified for an editor."""

    address: ModeloFormAddressV1
    box: str | None
    label: ModeloFormText
    help: str | None
    data_type: str = Field(min_length=1)
    value: ModeloFormScalar
    origin: ModeloFormOrigin
    editability: ModeloFormEditability
    not_writable_reason: str | None = None
    #: Whether the declaration needs this value from the filer, by the rule verification checks.
    required: bool
    #: Whether the field holds a value the filer types that nobody is recorded as having entered.
    #: This is wider than the assumed origin: an optional box holding zero is not assumed, yet a
    #: recalculation still returns it to what the calculation gives, so it stays unattributed.
    unattributed: bool = False
    #: On a rate box, the one rate its row's base binding declares; ``None`` on every other field
    #: and on a rate box whose base declares no rate, several rates, or has no binding.
    grounded_rate: ModeloFormRate | None = None
    #: On a rate box the official design fixes, the rate its literal prints where the literal's scale
    #: is declared; ``None`` on every other field, on a placeholder literal and on an undeclared scale.
    printed_rate: ModeloFormPrintedRate | None = None
    role: CalculationReportRowRole | None = None
    #: The bindings that feed the field; on a bound casilla the first is the one an override replaces.
    bindings: tuple[ModeloFormBinding, ...] = ()
    #: Where the value comes from; ``None`` for a field no binding or declared constant feeds.
    source: ModeloFormValueSource | None = None
    formula_id: FormulaId | None = None
    formula_operands: tuple[str, ...] = ()
    blockers: tuple[ModeloFormBlocker, ...] = ()
    constraints: CasillaConstraints | None = None
    legal_refs: tuple[LegalRefId, ...] = ()
    also_appears_on: tuple[str, ...] = ()
    #: Where the box stands for the filer, on the declaration and page it is shown on; derived from
    #: its own origin and blockers when the builder has no declaration or page to say otherwise.
    standing: ModeloFormStanding = Field(default_factory=_default_standing)
    #: The address a change to the box is submitted to: the binding that feeds it when the filer
    #: replaces a source's value, otherwise the box itself.
    edit_address: ModeloFormAddressV1 = Field(default_factory=_default_edit_address)
    #: Whether the box holds an assumed value the filer can confirm here as their own.
    confirmable: bool = Field(default_factory=_confirmable_of)
    #: Whether the box holds an amount of exactly zero: a figure the form holds, never the same as nothing.
    held_zero: bool = Field(default_factory=_default_held_zero)
    #: Whether the filer may type a value on the box itself.
    takes_typed_value: bool = Field(default_factory=_takes_typed_value_of)
    #: Whether the box holds a value the filer entered that they can remove.
    clearable: bool = Field(default_factory=_clearable_of)
    #: The filer's own value as an entry of it compares (see :func:`comparable_entry`); typing it again
    #: changes nothing. ``None`` when the value is not the filer's own.
    own_value: ModeloEditWireScalar = Field(default_factory=_own_value_of)
    #: The value confirming the box stages, as an entry of it compares, the form ``own_value`` takes;
    #: ``None`` when the box is not confirmable.
    confirm_comparable: ModeloEditWireScalar = Field(default_factory=_confirm_comparable_of)
    #: A digest of the box's value and origin, so a frontend can tell whether the box moved under a change it
    #: holds. It is derived from the value and a single amount's digest can be found by trying amounts, so it
    #: travels only in the form's result and in a preflight's transient submission, never in a plain request.
    state_digest: str = Field(default_factory=_state_digest_of, min_length=64, max_length=64)
    #: Whether the box holds the filer's value over a source, which they can give back to that source.
    restorable: bool = Field(default_factory=_restorable_of)
    #: Whether the box holds the filer's own value: typed here, or replacing its source's.
    filers_own: bool = Field(default_factory=_filers_own_of)
    #: The value confirming the box stages, as an edit intent carries it; ``None`` when the box is not confirmable.
    confirm_value: ModeloEditWireScalar = Field(default_factory=_confirm_value_of)
    #: Where the box's value stands, in the few words every frontend shows beside it, in the
    #: form's language; ``None`` until the builder words the form.
    origin_words: str | None = None
    #: A sentence explaining an origin its few words cannot; ``None`` when the words suffice.
    origin_explanation: str | None = None
    #: What may be done about the box, or why it cannot be edited here, in the form's language.
    editability_words: str | None = None
    #: The figure the box shows in the form's language; ``None`` when it shows none, which every
    #: frontend says from the box's origin.
    value_text: str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _reason_only_when_not_writable(self) -> ModeloFormField:
        if (self.editability is ModeloFormEditability.NOT_WRITABLE) != (self.not_writable_reason is not None):
            raise ValueError("a not-writable reason belongs to, and only to, a not-writable field")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _derived_from_the_field_itself(self) -> ModeloFormField:
        if self.edit_address != _edit_address_of(self.address, self.editability, self.bindings):
            raise ValueError("a field's edit address is the one its own address, editability and bindings give")
        if self.confirmable is not _confirmable_of(dict(self)):
            raise ValueError("a field is confirmable exactly when its own state makes it so")
        if self.held_zero is not holds_zero(self.value):
            raise ValueError("a field holds zero exactly when its value is an amount of zero")
        if self.filers_own is not _filers_own_of(dict(self)):
            raise ValueError("a field holds the filer's own value exactly when its origin says so")
        if self.restorable is not _restorable_of(dict(self)):
            raise ValueError("a field can go back to its source exactly when its own state makes it so")
        if self.confirm_value != _confirm_value_of(dict(self)):
            raise ValueError("a field's confirm value is the value its own state lets a confirmation stage")
        derived = dict(self)
        if (self.takes_typed_value, self.clearable) != (_takes_typed_value_of(derived), _clearable_of(derived)):
            raise ValueError("whether a field takes typing or clearing is what its own state makes it")
        if self.confirm_comparable != _confirm_comparable_of(derived):
            raise ValueError("a field's comparable confirm value is the one its own state lets a confirmation stage")
        if self.own_value != _own_value_of(derived) or self.state_digest != _state_digest_of(derived):
            raise ValueError("a field's own value and state digest are the ones its value and origin give")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _standing_fits_the_field(self) -> ModeloFormField:
        # The builder knows the declaration and the page; the field alone bounds what either can make of it.
        if self.standing not in fitting_standings(self.origin, self.blockers):
            raise ValueError("a field's standing is one its origin and blockers allow on some declaration and page")
        return self


_SELF_DERIVED: Final[frozenset[str]] = frozenset(
    {
        "edit_address",
        "confirmable",
        "held_zero",
        "restorable",
        "filers_own",
        "confirm_value",
        "takes_typed_value",
        "clearable",
        "own_value",
        "confirm_comparable",
        "state_digest",
    }
)


def revised_field(field: ModeloFormField, **update: Any) -> ModeloFormField:
    """A copy of ``field`` with ``update`` applied and every value it derives from itself derived again.

    A plain model copy skips validation, so a copy that changes a value, an
    origin or an editability would keep derivations that no longer hold. The
    standing is kept unless ``update`` gives one, because it also depends on
    the declaration and page the builder knows. A copy that changes the origin
    or the blockers without giving a standing has it derived again, as for a
    field with no declaration or page to say more.
    """
    data = {name: getattr(field, name) for name in type(field).model_fields if name not in _SELF_DERIVED}
    data.update(update)
    if "standing" not in update and ("origin" in update or "blockers" in update):
        data["standing"] = field_standing(data["origin"], data["blockers"])
    return type(field).model_validate(data)


def edit_address(field: ModeloFormField) -> ModeloFormAddressV1:
    """Return the address a change to ``field`` is submitted to.

    A bound casilla is shown by its box, but what the filer may replace is the
    value of the binding that feeds it, so an override is addressed to that
    binding; every other field is edited at its own address.
    """
    return _edit_address_of(field.address, field.editability, field.bindings)


def typed_by_the_filer(field: ModeloFormField) -> bool:
    """Whether ``field``'s value is the filer's own entry rather than one a source supplies.

    A manual box is, and so is a binding no casilla owns whose source is the
    filer's entry. A box any other source fills is not: keeping a value over
    it replaces the source.
    """
    return _typed_by_the_filer_of(field.bindings)


def confirmable(field: ModeloFormField) -> bool:
    """Whether ``field`` holds an assumed value the filer can confirm here as their own.

    The value must be one nobody is recorded as having entered, in a box the
    filer types into, and the box must take a typed value here: a box whose
    kind of value cannot be entered here yet cannot be confirmed either.
    """
    return _confirmable_of(dict(field))


class ModeloFormCounts(_FormModel):
    """How many fields stand in each origin, for a section, a page or the form.

    ``needs_input`` and ``default_to_confirm`` count what is still to do, so a
    declaration recorded as filed counts none of either: nothing on it can be
    entered or confirmed any more, and changing it starts a correction.
    """

    total: int = Field(ge=0)
    needs_input: int = Field(ge=0)
    entered: int = Field(ge=0)
    imported: int = Field(ge=0)
    calculated: int = Field(ge=0)
    overridden: int = Field(ge=0)
    default_to_confirm: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    blocked: int = Field(ge=0)


class ModeloFormFieldBlock(_FormModel):
    """One field on its own line."""

    kind: Literal["field"] = "field"
    id: str
    field: ModeloFormField


class ModeloFormContextFieldBlock(_FormModel):
    """Read-only declared filing context; deliberately carries no editable address."""

    kind: Literal["context_field"] = "context_field"
    id: str
    label: ModeloFormText
    value: ModeloFormScalar
    #: The value in the form's language, dates and the period in words; ``None`` until the builder words the form.
    value_text: str | None = None


class ModeloFormGridColumn(_FormModel):
    """One official column heading."""

    key: str
    heading: ModeloFormText


class ModeloFormGridCell(_FormModel):
    """One grid cell: a field, the design's literal, or a blank where the paper form has no box."""

    kind: FormCellKind
    field: ModeloFormField | None = None
    literal: str | None = None


class ModeloFormGridRow(_FormModel):
    """One official printed row; ``cells`` align with the grid's columns."""

    key: str
    heading: ModeloFormText
    cells: tuple[ModeloFormGridCell, ...]


class ModeloFormGridBlock(_FormModel):
    """Official rows and columns, like the printed form's base, rate and amount lines."""

    kind: Literal["grid"] = "grid"
    id: str
    columns: tuple[ModeloFormGridColumn, ...]
    rows: tuple[ModeloFormGridRow, ...]


class ModeloFormRepeatingRow(_FormModel):
    """One detail row's values, aligned with the group's columns."""

    index: int = Field(ge=1)
    values: tuple[ModeloFormScalar, ...]
    #: Each value as the table shows it in the form's language, aligned with ``values``; ``None`` for an empty
    #: value, and empty until the builder words the form.
    value_texts: tuple[str | None, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _texts_align_with_values(self) -> ModeloFormRepeatingRow:
        if self.value_texts and len(self.value_texts) != len(self.values):
            raise ValueError("a record's value texts align with its values")
        return self


class ModeloFormRepeatingBlock(_FormModel):
    """An open set of detail rows, never flattened into single boxes.

    ``rows_known`` is false when this form cannot read the rows from their
    source, so an empty ``rows`` is never mistaken for a group with no rows.
    """

    kind: Literal["repeating"] = "repeating"
    id: str
    columns: tuple[ModeloFormGridColumn, ...]
    #: The casilla each column shows, aligned with ``columns``; ``None`` for a column no casilla owns.
    column_casilla_ids: tuple[str | None, ...]
    column_data_types: tuple[str, ...]
    min_rows: int = Field(ge=0)
    max_rows: int | None
    rows_known: bool
    rows: tuple[ModeloFormRepeatingRow, ...]


class ModeloFormBindingInputsBlock(_FormModel):
    """Values the filer supplies that no casilla owns."""

    kind: Literal["binding_inputs"] = "binding_inputs"
    id: str
    fields: tuple[ModeloFormField, ...]


type ModeloFormBlock = Annotated[
    ModeloFormFieldBlock
    | ModeloFormGridBlock
    | ModeloFormRepeatingBlock
    | ModeloFormBindingInputsBlock
    | ModeloFormContextFieldBlock,
    Field(discriminator="kind"),
]


class ModeloFormSection(_FormModel):
    """One apartado with its heading, ordered blocks and counts."""

    id: str
    heading: ModeloFormText
    official_heading: str | None
    blocks: tuple[ModeloFormBlock, ...]
    counts: ModeloFormCounts


class ModeloFormPage(_FormModel):
    """One official page, whether it applies to this filing, and its sections."""

    id: str
    heading: ModeloFormText
    official_ref: str | None
    condition: FormPageCondition
    #: ``True`` applies, ``False`` does not, ``None`` may not apply and cannot be decided from the data.
    applies: bool | None
    sections: tuple[ModeloFormSection, ...]
    counts: ModeloFormCounts
    #: That the page does not apply this period, said as the filer counts the period; ``None`` on a page that
    #: applies or may.
    applicability_words: str | None = None


class ModeloFormUnplacedField(_FormModel):
    """A casilla the layout could not position, and why."""

    field: ModeloFormField
    reason: FormUnplacedReason | None


class ModeloFormAttention(StrEnum):
    """How much a finding asks of the filer."""

    #: It must be resolved before the declaration can be recorded as filed.
    BLOCKS = "blocks"
    #: A value the declaration requires is missing; giving it resolves the finding.
    MISSING = "missing"
    #: A value Cadrumo assumed or kept, waiting for the filer to confirm it.
    CONFIRM = "confirm"
    #: A warning worth checking; it does not stop the filing.
    CHECK = "check"
    #: An explanation of what the calculation did; nothing to act on.
    INFO = "info"


EXPLANATORY_FINDING_MESSAGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        # A dependency on an earlier period scoped out because the filer
        # declared a later activity start: it says why a filing is not needed.
        "application.modelo.findings.cross_period_operator_declared_suppression",
        # A first-year Modelo 202 instalment scoped out by the activity start.
        "application.modelo.findings.cross_period_first_year_fractional_suppression",
        # An earlier filing admitted because it carries zero into this one.
        "application.modelo.findings.cross_period_zero_value_previous_filing",
        # An earlier Modelo 111 admitted because it declares no withholdings.
        "application.modelo.findings.cross_period_m111_no_retenciones",
        # Source modelos this taxpayer does not file.
        "application.modelo.findings.cross_period_modelo_not_applicable.message",
        # An empty annual withholdings summary the filer attested that no
        # withholding was paid in any period: it says why nothing is declared.
        "application.modelo.findings.withholding_detail_absent_attested",
    }
)
"""The advisory findings that explain a decision the verification already made.

Each is produced when the verification admits or scopes out a dependency on
explicit evidence, such as the filer's own declaration of when their activity
started or that they paid no income subject to withholding: the finding tells
the filer why, and asks nothing of them. Advisories outside this set, such as
a possibly missed reduction or a total resting on a non-official local chain,
remain worth checking. The set is closed and keyed on the producers' catalogue
keys; a key it names that no catalogue carries fails its guard test.
"""


def finding_attention(finding: ModeloVerificationFinding) -> ModeloFormAttention:
    """Classify one verification finding on the filer's attention scale.

    A required value that is missing sits with the other missing values, since
    giving it is all it asks. Any other blocking finding blocks. A warning is
    worth checking, unless it is an advisory the verification emits to explain
    an admitted or scoped-out dependency, which is for information only.
    """
    if finding.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA:
        return ModeloFormAttention.MISSING
    if finding.severity is ModeloVerificationFindingSeverity.BLOCKING:
        return ModeloFormAttention.BLOCKS
    if (
        finding.kind is ModeloVerificationFindingKind.ADVISORY
        and finding.message_locale_key in EXPLANATORY_FINDING_MESSAGE_KEYS
    ):
        return ModeloFormAttention.INFO
    return ModeloFormAttention.CHECK


def _issue_attention(data: dict[str, Any]) -> ModeloFormAttention:
    finding = data.get("finding")
    if not isinstance(finding, ModeloVerificationFinding):
        raise ValueError("an issue's attention is derived from its finding")
    return finding_attention(finding)


FINDING_KIND_ACTION_LOCALE_KEYS: Final[Mapping[ModeloVerificationFindingKind, str]] = MappingProxyType(
    {
        ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA: (
            "application.modelo.work_form.finding_action.enter_box_value"
        ),
        ModeloVerificationFindingKind.RECONCILIATION_MISMATCH: (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN: (
            "application.modelo.work_form.finding_action.settle_earlier_declaration"
        ),
        ModeloVerificationFindingKind.BLOCKING_RULE: (
            "application.modelo.work_form.finding_action.correct_and_recalculate"
        ),
        ModeloVerificationFindingKind.ADVISORY: "application.modelo.work_form.finding_action.read_and_decide",
        ModeloVerificationFindingKind.STALE_CALCULATION: "application.modelo.work_form.finding_action.calculate_again",
    }
)
"""What to do about a finding whose message has no action of its own, by the finding's kind."""

FINDING_MESSAGE_ACTION_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        # Explanations: the verification already decided, on the filer's own evidence.
        "application.modelo.findings.cross_period_operator_declared_suppression": (
            "application.modelo.work_form.finding_action.nothing_to_do"
        ),
        "application.modelo.findings.cross_period_first_year_fractional_suppression": (
            "application.modelo.work_form.finding_action.nothing_to_do"
        ),
        "application.modelo.findings.cross_period_m111_no_retenciones": (
            "application.modelo.work_form.finding_action.nothing_to_do"
        ),
        "application.modelo.findings.cross_period_modelo_not_applicable.message": (
            "application.modelo.work_form.finding_action.nothing_to_do"
        ),
        "application.modelo.findings.cross_period_zero_value_previous_filing": (
            "application.modelo.work_form.finding_action.check_carried_zero"
        ),
        "application.modelo.findings.withholding_detail_absent_attested": (
            "application.modelo.work_form.finding_action.review_attested_year"
        ),
        # A document the records lack.
        "application.modelo.findings.transaction_evidence_missing_output": (
            "application.modelo.work_form.finding_action.attach_document"
        ),
        "application.modelo.findings.transaction_evidence_missing_deductible": (
            "application.modelo.work_form.finding_action.attach_document"
        ),
        "application.modelo.findings.iva_intra_eu_self_assessment_unrecordable": (
            "application.modelo.work_form.finding_action.file_another_way"
        ),
        "application.modelo.findings.iva_import_document_unrecordable": (
            "application.modelo.work_form.finding_action.file_another_way"
        ),
        "application.modelo.findings.iva_reagp_document_unrecordable": (
            "application.modelo.work_form.finding_action.file_another_way"
        ),
        "application.modelo.findings.iva_rectification_document_unrecordable": (
            "application.modelo.work_form.finding_action.file_another_way"
        ),
        "application.modelo.findings.oss_evidence_missing": (
            "application.modelo.work_form.finding_action.attach_document"
        ),
        "application.modelo.findings.cuota_less_ledger_row_base_missing": (
            "application.modelo.work_form.finding_action.add_base_to_entry"
        ),
        # Figures that disagree.
        "application.modelo.findings.m303_m349_intracom_reconciliation_mismatch": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        "application.modelo.findings.pulled_filing_casilla_mismatch": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        "application.modelo.findings.cross_casilla_invariant_violated": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        "application.modelo.findings.attribution_received_unfolded": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        # Earlier declarations and records.
        "application.modelo.findings.cross_period_non_official_local_chain.message": (
            "application.modelo.work_form.finding_action.check_earlier_figures"
        ),
        "application.modelo.findings.iva_compensation_annual_source_evidence_failure": (
            "application.modelo.work_form.finding_action.resolve_303_returns"
        ),
        # Facts the filer supplies.
        "application.modelo.findings.cross_period_activity_start_missing": (
            "application.modelo.work_form.finding_action.add_activity_start"
        ),
        "application.modelo.findings.attribution_received_uncaptured": (
            "application.modelo.work_form.finding_action.add_attribution_to_profile"
        ),
        "application.modelo.findings.objective_estimation_exclusion_threshold_exceeded": (
            "application.modelo.work_form.finding_action.check_profile_value"
        ),
        "application.modelo.findings.suffered_retencion_trabajo_uncredited": (
            "application.modelo.work_form.finding_action.enter_withholding_certificate"
        ),
        "application.modelo.findings.suffered_retencion_capital_mobiliario_uncredited": (
            "application.modelo.work_form.finding_action.enter_withholding_certificate"
        ),
        "application.modelo.findings.withholding_detail_absent_against_ledger_evidence": (
            "application.modelo.work_form.finding_action.enter_payee_payments"
        ),
        "application.modelo.findings.withholding_detail_absent_unproven": (
            "application.modelo.work_form.finding_action.enter_or_confirm_payments"
        ),
        "application.modelo.findings.foreign_asset_redeclaration": (
            "application.modelo.work_form.finding_action.declare_asset_again"
        ),
        "application.modelo.findings.m210_agrupacion_renta_invalid": (
            "application.modelo.work_form.finding_action.regroup_income_lines"
        ),
        # Reductions and deductions the figures suggest.
        "application.modelo.findings.art20_reduccion_possible": (
            "application.modelo.work_form.finding_action.check_possible_reduction"
        ),
        "application.modelo.findings.dt12a_reduccion_possible": (
            "application.modelo.work_form.finding_action.check_possible_reduction"
        ),
        "application.modelo.findings.madrid_nacimiento_adopcion_eligibility_advisory": (
            "application.modelo.work_form.finding_action.check_possible_reduction"
        ),
        "application.modelo.findings.art52_reduccion_individual_sublimit_possible": (
            "application.modelo.work_form.finding_action.check_condition"
        ),
        "application.modelo.findings.dt12a_reduccion_antiquity_possible": (
            "application.modelo.work_form.finding_action.check_condition"
        ),
        # What this application cannot settle yet.
        "application.modelo.findings.m193_settled_row_amount_authority_unresolved": (
            "application.modelo.work_form.finding_action.await_update"
        ),
        "application.modelo.findings.registry_authority_grade_insufficient": (
            "application.modelo.work_form.finding_action.await_update"
        ),
        "application.modelo.findings.registry_snapshot_unresolved": (
            "application.modelo.work_form.finding_action.retry_or_update"
        ),
    }
)
"""What to do about a finding, by its message, where the message says more than its kind.

Each action restates the step the finding's own message names or implies, and
nothing more. A message not listed takes its kind's action from
:data:`FINDING_KIND_ACTION_LOCALE_KEYS`; the mapping is closed, and a key on
either side that no catalogue carries fails its guard test.
"""


def finding_action_locale_key(finding: ModeloVerificationFinding) -> str:
    """Return the catalogue key of the one sentence that says what to do about ``finding``.

    The finding's message decides first, then its kind. An explanation's
    "nothing to do" holds only while the finding is an explanation: the same
    message raised as a blocker or a warning of another kind takes its kind's
    action, so a finding that must be resolved never tells the filer to leave it.
    """
    action = FINDING_MESSAGE_ACTION_LOCALE_KEYS.get(finding.message_locale_key)
    explains = finding.message_locale_key in EXPLANATORY_FINDING_MESSAGE_KEYS
    if action is None or (explains and finding_attention(finding) is not ModeloFormAttention.INFO):
        return FINDING_KIND_ACTION_LOCALE_KEYS[finding.kind]
    return action


def _issue_action(data: dict[str, Any]) -> str:
    finding = data.get("finding")
    if not isinstance(finding, ModeloVerificationFinding):
        raise ValueError("an issue's action is derived from its finding")
    return finding_action_locale_key(finding)


class ModeloFormIssue(_FormModel):
    """One finding of the current calculation's latest verification, with the box it concerns.

    The finding keeps its catalogue key and typed facts, so the frontend renders
    it in the filer's language; ``box`` is the official box number when the
    finding names a casilla the form shows. ``attention`` places the finding on
    the filer's scale, and ``action_locale_key`` is the catalogue key of the one
    sentence that says what to do about it; both are derived from the finding
    when not given, and must match what it derives to when given.
    """

    finding: ModeloVerificationFinding
    box: str | None = None
    attention: ModeloFormAttention = Field(default_factory=_issue_attention)
    action_locale_key: str = Field(default_factory=_issue_action)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _attention_matches_the_finding(self) -> ModeloFormIssue:
        if self.attention is not finding_attention(self.finding):
            raise ValueError("an issue's attention must be the one its finding classifies to")
        if self.action_locale_key != finding_action_locale_key(self.finding):
            raise ValueError("an issue's action must be the one its finding maps to")
        return self


class ModeloFormSourceGroupKind(StrEnum):
    """Where a box's value comes from, as the filer thinks of it; one per box."""

    RECORDS = "records"
    REGISTERS = "registers"
    PROFILE = "profile"
    EARLIER_DECLARATIONS = "earlier_declarations"
    AEAT_DATA = "aeat_data"
    YOURS = "yours"
    REPLACED = "replaced"
    ASSUMED = "assumed"
    NEEDS_YOU = "needs_you"
    CALCULATED = "calculated"
    SET_BY_FORM = "set_by_form"
    INFORMATION = "information"
    BLANK = "blank"
    UNNAMED = "unnamed"


class ModeloFormSourceState(StrEnum):
    """What a source gave this declaration."""

    PRODUCED = "produced"
    NONE_FOUND = "none_found"
    NOT_YET = "not_yet"


class ModeloFormSourceReading(_FormModel):
    """One source feeding a group, what it gave, and the boxes listed under it, in the form's language."""

    source_kind: BindingSourceKind
    #: The product area that owns the source's data, which a frontend may open.
    surface: SourceSurface
    state: ModeloFormSourceState
    words: str
    addresses: tuple[ModeloFormAddressV1, ...]


class ModeloFormSourceGroup(_FormModel):
    """One group of where the form's values come from: its boxes, its sources, and its words.

    ``boxes`` are the box numbers a closed group lists, for a group that asks
    something of the filer; ``summary`` names its sources, or the earlier
    declarations its boxes are carried from.
    """

    kind: ModeloFormSourceGroupKind
    name: str
    summary: str = ""
    boxes: tuple[str, ...] = ()
    #: The declaration is recorded as filed, so a group that would ask for a value asks nothing.
    recorded: bool = False
    addresses: tuple[ModeloFormAddressV1, ...]
    readings: tuple[ModeloFormSourceReading, ...] = ()


class ModeloFormCalculationNote(_FormModel):
    """One thing the latest calculation noticed, on the filer's scale, with the box it names.

    ``reason`` is the calculation's own reason code, which the frontend words
    from the catalogue; ``box`` is the printed box number when the note names a
    box the form prints. ``withholds_filing`` is the application's
    calculation-note gate's own answer: the gate refuses the file and the
    recording while such a note stands, whatever its attention says, so the
    editor withholds them too (:attr:`ModeloWorkForm.blocking_calculation_notes`),
    as it does for a note at the blocking level.
    """

    reason: str = Field(min_length=1, max_length=64)
    attention: ModeloFormAttention
    casilla_id: CasillaId | None = None
    box: str | None = None
    withholds_filing: bool = False


class ModeloFormAeatData(_FormModel):
    """The AEAT tax data (borrador) the current calculation took values from.

    Recalculating replays the imported snapshot, so its values keep feeding the
    declaration until it is replaced. ``imported_at`` is when the data was
    imported, or ``None`` when this read could not open the snapshot's record;
    ``binding_ids`` are the bindings whose values the snapshot supplied.
    """

    snapshot_id: str = Field(min_length=1)
    imported_at: datetime | None = None
    binding_ids: tuple[BindingId, ...] = ()


class ModeloFormDeadline(_FormModel):
    """The last day of the voluntary filing window for this declaration.

    ``nominal_closes_on`` is the date the registry declares; ``closes_on`` is
    the date after the business-day shift, and ``holiday_coverage`` says which
    holidays that shift accounted for, so a date computed without the filer's
    regional holidays is never passed off as final. Exactly one of
    ``days_remaining`` and ``days_overdue`` is set, counted from
    ``reference_on``.
    """

    closes_on: date
    nominal_closes_on: date
    holiday_coverage: DeadlineHolidayCoverage
    reference_on: date
    days_remaining: int | None = Field(default=None, ge=0)
    days_overdue: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_posture(self) -> ModeloFormDeadline:
        if (self.days_remaining is None) == (self.days_overdue is None):
            raise ValueError("a deadline is either still open or passed, never both or neither")
        return self


class ModeloFormResultDirection(StrEnum):
    """Which way the declaration's result settles, as its official design declares it."""

    TO_PAY = "to_pay"
    TO_REFUND = "to_refund"
    TO_CARRY_FORWARD = "to_carry_forward"
    #: A negative instalment result the filer deducts from the positive results of later quarters of the same year.
    TO_DEDUCT_LATER = "to_deduct_later"
    #: A negative result that nothing carries: it is declared as negative and settles nothing.
    NEGATIVE = "negative"
    NIL = "nil"
    #: Nothing declares how this result settles, or it has no value yet.
    UNKNOWN = "unknown"


class ModeloFormResult(_FormModel):
    """The box that settles the declaration, its value and its direction.

    ``disposition`` is the official "tipo de declaración" code the result
    implies before any election the filer makes when filing; the direction is
    read from it and from nothing else, never from the sign alone. When the
    registry names the settlement box but declares no such rule, the direction
    is unknown. ``election_may_change`` says the filer's refund election can
    still turn a carried credit into a refund.
    """

    casilla_id: CasillaId
    box: str | None
    value: Decimal | None
    direction: ModeloFormResultDirection
    disposition: ResultDisposition | None = None
    election_may_change: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _direction_needs_a_value(self) -> ModeloFormResult:
        if self.value is None and self.direction is not ModeloFormResultDirection.UNKNOWN:
            raise ValueError("a result without a value has no direction")
        return self


class ModeloFormFiling(_FormModel):
    """The declaration is recorded in Cadrumo as filed; nothing was sent to AEAT from here."""

    #: When the filing was recorded, or ``None`` when the revision does not say.
    recorded_at: datetime | None = None


class ModeloFormExport(_FormModel):
    """The latest file exported for this declaration, and whether it was made from the current calculation.

    A file made from an earlier calculation no longer matches the declaration:
    changes applied or a recalculation since then created a newer one, so that
    file must not be uploaded.
    """

    exported_at: datetime
    calculation_revision_id: str = Field(min_length=1)
    current: bool


class ModeloFormEditClosure(StrEnum):
    """Why nothing on the form may be edited, whatever the edit admission says."""

    #: The declaration is recorded as filed; changing it starts a correction
    #: (a complementaria or a rectificativa), never an edit in place.
    RECORDED_AS_FILED = "recorded_as_filed"


class ModeloWorkForm(_FormModel):
    """The editor form of one work target in one language."""

    modelo: ModeloCode
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    work_unit_id: str
    calculation_revision_id: str | None
    language: OutputLanguage
    layout_provenance: ModeloFormLayoutProvenance
    inspection_reason: ModeloFormInspectionReason | None = None
    seed_source: FormLayoutSeedSource | None = None
    pages: tuple[ModeloFormPage, ...]
    working_figures: tuple[ModeloFormField, ...] = ()
    unplaced: tuple[ModeloFormUnplacedField, ...] = ()
    result_addresses: tuple[CasillaId, ...] = ()
    counts: ModeloFormCounts
    progress: ModeloWorkProgress
    operator_entries_known: bool
    edit_admitted: bool
    #: The current calculation's latest verification verdict; ``None`` when it has not been verified.
    verification: VerificationCompletenessStatus | None = None
    #: That verification's findings, blocking first, whether or not they name a casilla.
    issues: tuple[ModeloFormIssue, ...] = ()
    #: What the latest calculation noticed that no finding of the check already says, most urgent first.
    calculation_notes: tuple[ModeloFormCalculationNote, ...] = ()
    #: ``False`` when this session did not run the latest calculation, so only its durable notes are known.
    calculation_notes_held: bool = True
    #: Where every value comes from, grouped as the filer thinks of it, each box in exactly one group.
    source_groups: tuple[ModeloFormSourceGroup, ...] = ()
    #: The settlement box and its direction; ``None`` when the registry names no settlement box.
    result: ModeloFormResult | None = None
    #: The last day to file; ``None`` when the registry declares no window for this declaration.
    deadline: ModeloFormDeadline | None = None
    #: The AEAT tax data the current calculation replayed; ``None`` when it replayed none.
    aeat_data: ModeloFormAeatData | None = None
    #: Set when the declaration is recorded as filed.
    filing: ModeloFormFiling | None = None
    #: The latest file exported for this declaration, or ``None`` when none was ever exported.
    last_export: ModeloFormExport | None = None
    #: Why nothing may be edited, when something other than the admission closes the form.
    edit_closure: ModeloFormEditClosure | None = None
    #: The modelo's number and title, its number alone, and the period, in the form's language.
    modelo_title: str | None = None
    #: The modelo's own title without its number, beside the number a frontend shows apart; ``None`` without one.
    modelo_name: str | None = None
    modelo_number: str | None = None
    period_words: str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _inspection_reason_matches_provenance(self) -> ModeloWorkForm:
        inspecting = self.layout_provenance is ModeloFormLayoutProvenance.INSPECTION_ONLY
        if inspecting != (self.inspection_reason is not None):
            raise ValueError("an inspection reason belongs to, and only to, an inspection-only form")
        if self.edit_closure is not None and self.edit_admitted:
            raise ValueError("a form closed to editing admits no edit")
        return self

    @property
    def calculation_out_of_date(self) -> bool:
        """Whether the last check found the records changed after the calculation, so it must be calculated again."""
        return any(issue.finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION for issue in self.issues)

    @property
    def blocking_calculation_notes(self) -> tuple[ModeloFormCalculationNote, ...]:
        """The latest calculation's notes that withhold filing, as blocking findings do: at that level or gated."""
        return tuple(
            note
            for note in self.calculation_notes
            if note.attention is ModeloFormAttention.BLOCKS or note.withholds_filing
        )

    def fields(self) -> tuple[ModeloFormField, ...]:
        """Return every field once, in reading order: pages, then working figures, then unplaced."""
        collected: list[ModeloFormField] = []
        for page in self.pages:
            for section in page.sections:
                collected.extend(section_fields(section))
        collected.extend(self.working_figures)
        collected.extend(item.field for item in self.unplaced)
        return tuple(collected)


def map_section_fields(
    section: ModeloFormSection, change: Callable[[ModeloFormField], ModeloFormField]
) -> ModeloFormSection:
    """Return ``section`` with ``change`` applied to every field it shows, in every kind of block."""
    blocks: list[ModeloFormBlock] = []
    for block in section.blocks:
        if isinstance(block, ModeloFormFieldBlock):
            blocks.append(block.model_copy(update={"field": change(block.field)}))
        elif isinstance(block, ModeloFormGridBlock):
            rows = tuple(
                row.model_copy(
                    update={
                        "cells": tuple(
                            cell if cell.field is None else cell.model_copy(update={"field": change(cell.field)})
                            for cell in row.cells
                        )
                    }
                )
                for row in block.rows
            )
            blocks.append(block.model_copy(update={"rows": rows}))
        elif isinstance(block, ModeloFormBindingInputsBlock):
            blocks.append(block.model_copy(update={"fields": tuple(change(field) for field in block.fields)}))
        else:
            blocks.append(block)
    return section.model_copy(update={"blocks": tuple(blocks)})


def map_form_fields(form: ModeloWorkForm, change: Callable[[ModeloFormField], ModeloFormField]) -> ModeloWorkForm:
    """Return ``form`` with ``change`` applied to every field: on its pages, its working figures and unplaced."""
    return form.model_copy(
        update={
            "pages": tuple(
                page.model_copy(update={"sections": tuple(map_section_fields(s, change) for s in page.sections)})
                for page in form.pages
            ),
            "working_figures": tuple(change(field) for field in form.working_figures),
            "unplaced": tuple(item.model_copy(update={"field": change(item.field)}) for item in form.unplaced),
        }
    )


def section_fields(section: ModeloFormSection) -> tuple[ModeloFormField, ...]:
    """Return a section's fields in reading order, grid rows left to right."""
    collected: list[ModeloFormField] = []
    for block in section.blocks:
        if isinstance(block, ModeloFormFieldBlock):
            collected.append(block.field)
        elif isinstance(block, ModeloFormGridBlock):
            collected.extend(cell.field for row in block.rows for cell in row.cells if cell.field is not None)
        elif isinstance(block, ModeloFormBindingInputsBlock):
            collected.extend(block.fields)
    return tuple(collected)


__all__ = [
    "ABSENT_FROM_ADMISSION",
    "ASKS_FOR_A_VALUE",
    "EXPLANATORY_FINDING_MESSAGE_KEYS",
    "FINDING_KIND_ACTION_LOCALE_KEYS",
    "FINDING_MESSAGE_ACTION_LOCALE_KEYS",
    "NEEDS_ATTENTION",
    "ORIGIN_STANDINGS",
    "ModeloFormAddressV1",
    "ModeloFormAeatData",
    "ModeloFormAttention",
    "ModeloFormBinding",
    "ModeloFormBindingAddressV1",
    "ModeloFormBindingInputsBlock",
    "ModeloFormBlock",
    "ModeloFormBlocker",
    "ModeloFormCalculationNote",
    "ModeloFormCasillaAddressV1",
    "ModeloFormContextFieldBlock",
    "ModeloFormCounts",
    "ModeloFormDeadline",
    "ModeloFormEarlierFiling",
    "ModeloFormEditClosure",
    "ModeloFormEditability",
    "ModeloFormExport",
    "ModeloFormField",
    "ModeloFormFieldBlock",
    "ModeloFormFiling",
    "ModeloFormGridBlock",
    "ModeloFormGridCell",
    "ModeloFormGridColumn",
    "ModeloFormGridRow",
    "ModeloFormInspectionReason",
    "ModeloFormIssue",
    "ModeloFormLayoutProvenance",
    "ModeloFormOrigin",
    "ModeloFormPage",
    "ModeloFormPrintedRate",
    "ModeloFormRate",
    "ModeloFormRateUnit",
    "ModeloFormRepeatingBlock",
    "ModeloFormRepeatingRow",
    "ModeloFormResult",
    "ModeloFormResultDirection",
    "ModeloFormScalar",
    "ModeloFormSection",
    "ModeloFormSourceGroup",
    "ModeloFormSourceGroupKind",
    "ModeloFormSourceReading",
    "ModeloFormSourceState",
    "ModeloFormStanding",
    "ModeloFormText",
    "ModeloFormTextDisclosure",
    "ModeloFormUnplacedField",
    "ModeloFormValueSource",
    "ModeloWorkForm",
    "address_key",
    "confirmable",
    "edit_address",
    "field_standing",
    "finding_action_locale_key",
    "finding_attention",
    "fitting_standings",
    "holds_zero",
    "map_form_fields",
    "map_section_fields",
    "revised_field",
    "section_fields",
    "typed_by_the_filer",
]
