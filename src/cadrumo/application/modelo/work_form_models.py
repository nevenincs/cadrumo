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

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.hashing import sha256_hex
from ...core.period import Period
from ...core.type_guards import is_object_list_or_tuple
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...domain.calculations.registry.ids import BindingId, FormulaId, LegalRefId, RevisionId
from ...domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormLayoutSeedSource,
    FormPageCondition,
    FormUnplacedReason,
)
from ...domain.calculations.registry.schema_surfaces import CasillaConstraints
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
)
from .calculation_notes import CALCULATION_SCREEN_OUTDATED_REASON, FILED_BEFORE_GRADE_CAP_REASON
from .calculation_report import CalculationReportRowRole
from .edit_apply_scalar_contracts import ModeloEditWireScalar, wire_scalar_value
from .edit_models import ModeloEditBindingIntentKind
from .source_policy import SourceOverridePolicy, SourceSurface
from .work_form_declaration_facts import (
    ModeloFormAeatData,
    ModeloFormBase,
    ModeloFormCalculationNote,
    ModeloFormDeadline,
    ModeloFormEditClosure,
    ModeloFormExport,
    ModeloFormFiling,
    ModeloFormResult,
    ModeloFormYearProjection,
)
from .work_form_field_vocabulary import (
    TYPED_EDITABILITIES,
    ModeloFormAddressV1,
    ModeloFormBinding,
    ModeloFormBindingAddressV1,
    ModeloFormBlocker,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormPrintedRate,
    ModeloFormRate,
    ModeloFormScalar,
    ModeloFormStanding,
    ModeloFormText,
    ModeloFormValueSource,
    address_key,
    field_standing,
    fitting_standings,
)
from .work_form_findings import ModeloFormAttention, ModeloFormIssue
from .work_form_prior_value_models import ModeloFormPriorValueAttestation
from .work_form_scalar_values import comparable_entry, holds_zero
from .work_review import ModeloWorkProgress


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


def _default_standing(data: dict[str, object]) -> ModeloFormStanding:
    origin = data.get("origin")
    if not isinstance(origin, ModeloFormOrigin):
        raise ValueError("a field's standing is derived from its origin")
    return field_standing(origin, _factory_blockers(data))


_OVERRIDE_EDITABILITIES = frozenset({ModeloFormEditability.OVERRIDABLE_SOURCE, ModeloFormEditability.EDITABLE_OVERRIDE})
_CONFIRMING_EDITABILITIES = frozenset({ModeloFormEditability.EDITABLE_VALUE, ModeloFormEditability.EDITABLE_OVERRIDE})


def _is_absent(value: object) -> bool:
    return value is None


def _is_empty(value: tuple[object, ...]) -> bool:
    return not value


_CARRY_STATEMENT_INTENTS: Final = frozenset(
    {ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT, ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE}
)


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


def _factory_blockers(data: dict[str, object]) -> tuple[ModeloFormBlocker, ...] | list[ModeloFormBlocker]:
    blockers = data.get("blockers", ())
    if not is_object_list_or_tuple(blockers) or not all(isinstance(item, ModeloFormBlocker) for item in blockers):
        raise ValueError("a field's blockers must be validated")
    return tuple(item for item in blockers if isinstance(item, ModeloFormBlocker))


def _factory_bindings(data: dict[str, object]) -> tuple[ModeloFormBinding, ...] | list[ModeloFormBinding]:
    bindings = data.get("bindings", ())
    if not is_object_list_or_tuple(bindings) or not all(isinstance(item, ModeloFormBinding) for item in bindings):
        raise ValueError("a field's bindings must be validated")
    return tuple(item for item in bindings if isinstance(item, ModeloFormBinding))


def _factory_address(data: dict[str, object]) -> ModeloFormAddressV1:
    address = data["address"]
    if not isinstance(address, ModeloFormCasillaAddressV1 | ModeloFormBindingAddressV1):
        raise ValueError("a field's address must be validated")
    return address


def _factory_editability(data: dict[str, object]) -> ModeloFormEditability:
    editability = data["editability"]
    if not isinstance(editability, ModeloFormEditability):
        raise ValueError("a field's editability must be validated")
    return editability


def _factory_origin(data: dict[str, object]) -> ModeloFormOrigin:
    origin = data["origin"]
    if not isinstance(origin, ModeloFormOrigin):
        raise ValueError("a field's origin must be validated")
    return origin


def _factory_value(data: dict[str, object]) -> ModeloFormScalar:
    value = data.get("value")
    if value is not None and not isinstance(value, Decimal | int | str | bool | date):
        raise ValueError("a field's value must be validated")
    return value


def _confirmable_of(data: dict[str, object]) -> bool:
    address = _factory_address(data)
    editability = _factory_editability(data)
    bindings = _factory_bindings(data)
    return (
        data["origin"] is ModeloFormOrigin.DEFAULT_TO_CONFIRM
        and data["value"] is not None
        and _typed_by_the_filer_of(bindings)
        and editability in _CONFIRMING_EDITABILITIES
        and _edit_address_of(address, editability, bindings) == address
    )


def _default_edit_address(data: dict[str, object]) -> ModeloFormAddressV1:
    return _edit_address_of(_factory_address(data), _factory_editability(data), _factory_bindings(data))


def _default_held_zero(data: dict[str, object]) -> bool:
    return holds_zero(_factory_value(data))


_FILERS_OWN_ORIGINS = frozenset({ModeloFormOrigin.OVERRIDES_SOURCE, ModeloFormOrigin.ENTERED})


def _takes_typed_value_of(data: dict[str, object]) -> bool:
    return data["editability"] in TYPED_EDITABILITIES


def _clearable_of(data: dict[str, object]) -> bool:
    return data["editability"] is ModeloFormEditability.EDITABLE_VALUE and data["origin"] is ModeloFormOrigin.ENTERED


_REMOVABLE_ORIGINS = frozenset({ModeloFormOrigin.ENTERED, ModeloFormOrigin.CLEARED})


def _removable_of(data: dict[str, object]) -> bool:
    return data["editability"] is ModeloFormEditability.EDITABLE_VALUE and data["origin"] in _REMOVABLE_ORIGINS


def _own_value_of(data: dict[str, object]) -> ModeloEditWireScalar:
    return comparable_entry(_factory_value(data)) if data["origin"] in _FILERS_OWN_ORIGINS else None


def _confirm_comparable_of(data: dict[str, object]) -> ModeloEditWireScalar:
    value = _factory_value(data)
    return comparable_entry(value) if value is not None and _confirmable_of(data) else None


def _state_digest_of(data: dict[str, object]) -> str:
    value = comparable_entry(_factory_value(data))
    seen = json.dumps([_factory_origin(data).value, type(value).__name__, None if value is None else str(value)])
    return sha256_hex(seen.encode("utf-8"))


def _filers_own_of(data: dict[str, object]) -> bool:
    return data["origin"] in _FILERS_OWN_ORIGINS


def _restorable_of(data: dict[str, object]) -> bool:
    return data["editability"] in _OVERRIDE_EDITABILITIES and _filers_own_of(data)


def _confirm_value_of(data: dict[str, object]) -> ModeloEditWireScalar:
    value = _factory_value(data)
    return wire_scalar_value(value) if value is not None and _confirmable_of(data) else None


class ModeloFormField(ModeloFormBase):
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
    #: Whether the filer's own entry or clear on a box they type can be taken out, so the box holds
    #: what the declaration gives without it, as it did before the filer touched it.
    removable: bool = Field(default_factory=_removable_of)
    #: The filer's own value as an entry of it compares (see
    #: :func:`~cadrumo.application.modelo.work_form_scalar_values.comparable_entry`); typing it again
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
    #: The statement the filer made that this carry holds nothing, by the family its binding declares;
    #: ``None`` for a value typed or taken from a source, so a zero stated never reads as a zero typed.
    stated_absent: AbsenceAttestationFamily | None = None
    #: The figure on the carry is one the filer stated for an earlier return the application does not hold;
    #: ``None`` for a value typed, taken from a source or stated absent. Left out when ``None``.
    stated_prior_value: ModeloFormStatedPriorValue | None = Field(default=None, exclude_if=_is_absent)
    #: The statements the edit admits on the box's carry that the filer has not made, in served words;
    #: left out when there are none.
    statements: tuple[ModeloFormBindingStatement, ...] = Field(default=(), exclude_if=_is_empty)
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
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _derived_edit_values_match(self) -> ModeloFormField:
        derived = dict(self)
        if (self.takes_typed_value, self.clearable, self.removable) != (
            _takes_typed_value_of(derived),
            _clearable_of(derived),
            _removable_of(derived),
        ):
            raise ValueError("whether a field takes typing, clearing or removal is what its own state makes it")
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
        "removable",
        "own_value",
        "confirm_comparable",
        "state_digest",
    }
)


def revised_field(field: ModeloFormField, **update: object) -> ModeloFormField:
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
        data["standing"] = field_standing(_factory_origin(data), _factory_blockers(data))
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


class ModeloFormCounts(ModeloFormBase):
    """How many fields stand in each origin, for a section, a page or the form.

    ``total`` counts the boxes counted: a section's, a page's, or for the form
    every box on its pages plus its working figures and unplaced casillas. Every
    tally of the form is the sum of its outline groups' tallies, so a navigator
    drawn from the outline reaches each box any tally counts, and none it
    does not.

    ``needs_input`` and ``default_to_confirm`` count what is still to do, so a
    declaration recorded as filed counts none of either: nothing on it can be
    entered or confirmed any more, and changing it starts a correction.

    ``needs_you`` and ``could_not_calculate`` are the attention a navigator
    shows. ``needs_you`` counts every box whose standing asks the filer to act
    (a value to give or confirm, a box the calculation could not work out, a
    blocker), so it is what a section still asks of the filer.
    ``could_not_calculate`` counts the boxes among them the last calculation
    could not produce. A box can count in both.
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
    needs_you: int = Field(ge=0)
    could_not_calculate: int = Field(ge=0)


class ModeloFormFieldBlock(ModeloFormBase):
    """One field on its own line."""

    kind: Literal["field"] = "field"
    id: str
    field: ModeloFormField


class ModeloFormContextFieldBlock(ModeloFormBase):
    """Read-only declared filing context; deliberately carries no editable address."""

    kind: Literal["context_field"] = "context_field"
    id: str
    label: ModeloFormText
    #: The printed box the design gives this context, kept apart from the label so each frontend decides how to show it.
    box_number: str | None = None
    value: ModeloFormScalar
    #: The value in the form's language, dates and the period in words; ``None`` until the builder words the form.
    value_text: str | None = None


class ModeloFormGridColumn(ModeloFormBase):
    """One official column heading."""

    key: str
    heading: ModeloFormText


class ModeloFormGridCell(ModeloFormBase):
    """One grid cell: a field, the design's literal, or a blank where the paper form has no box."""

    kind: FormCellKind
    field: ModeloFormField | None = None
    literal: str | None = None


class ModeloFormGridRow(ModeloFormBase):
    """One official printed row; ``cells`` align with the grid's columns."""

    key: str
    heading: ModeloFormText
    cells: tuple[ModeloFormGridCell, ...]


class ModeloFormGridBlock(ModeloFormBase):
    """Official rows and columns, like the printed form's base, rate and amount lines."""

    kind: Literal["grid"] = "grid"
    id: str
    columns: tuple[ModeloFormGridColumn, ...]
    rows: tuple[ModeloFormGridRow, ...]


class ModeloFormRepeatingRow(ModeloFormBase):
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


class ModeloFormRepeatingBlock(ModeloFormBase):
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


class ModeloFormBindingInputsBlock(ModeloFormBase):
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


class ModeloFormSection(ModeloFormBase):
    """One apartado with its heading, ordered blocks, counts and whether it applies."""

    id: str
    heading: ModeloFormText
    official_heading: str | None
    blocks: tuple[ModeloFormBlock, ...]
    counts: ModeloFormCounts
    #: ``False`` when its page does not apply or every box on it is proven not to apply; otherwise its page's answer.
    applies: bool | None


class ModeloFormPage(ModeloFormBase):
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


class ModeloFormOutlineKind(StrEnum):
    """What an outline group gathers: sections of the form's pages, or one of the lists kept apart from them."""

    SECTIONS = "sections"
    #: The working figures: boxes the calculation produces that the form does not print.
    WORKING_FIGURES = "working_figures"
    #: The casillas the layout could not position.
    UNPLACED = "unplaced"
    #: The answers the calculation reads that no field of the pages takes.
    ANSWERS = "answers"


class ModeloFormOutlineGroup(ModeloFormBase):
    """One group of the form's navigation outline: a heading and what it gathers, in order.

    A ``sections`` group names :attr:`ModeloFormSection.id` values in
    ``section_ids``, every section of the form's pages in exactly one such
    group. A ``working_figures``, ``unplaced`` or ``answers`` group gathers the
    form's list of that name, has no section ids, and is present only when the
    list is not empty. ``counts`` roll up the boxes the group gathers; ``applies`` is
    ``True`` when any of its sections applies, ``False`` when none does, and
    ``None`` otherwise. A list kept apart from the pages always applies.
    """

    id: str
    heading: ModeloFormText
    kind: ModeloFormOutlineKind = ModeloFormOutlineKind.SECTIONS
    section_ids: tuple[str, ...]
    counts: ModeloFormCounts
    applies: bool | None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _only_a_sections_group_names_sections(self) -> ModeloFormOutlineGroup:
        if self.kind is not ModeloFormOutlineKind.SECTIONS and self.section_ids:
            raise ValueError("a group of a list kept apart from the pages names no section")
        return self


class ModeloFormUnplacedField(ModeloFormBase):
    """A casilla the layout could not position, and why."""

    field: ModeloFormField
    reason: FormUnplacedReason | None


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


class ModeloFormSourceReading(ModeloFormBase):
    """One source feeding a group, what it gave, and the boxes listed under it, in the form's language."""

    source_kind: BindingSourceKind
    #: The product area that owns the source's data, which a frontend may open.
    surface: SourceSurface
    state: ModeloFormSourceState
    words: str
    addresses: tuple[ModeloFormAddressV1, ...]


class ModeloFormSourceGroup(ModeloFormBase):
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


class ModeloFormCredit(ModeloFormBase):
    """A box the withholding register supplies, and the numbered boxes the calculation works out from it.

    ``dependents`` are the numbered boxes this form shows whose formula reads the
    credit, directly or through other figures, printed or not, in the form's
    reading order; a box that is itself a credit is listed as a credit, not here.
    An empty tuple says no formula of the revision reads the credit. ``None``
    says the revision declares a formula the graph cannot read, so which boxes
    depend on the credit is not known; it never stands for none.
    """

    address: ModeloFormAddressV1
    dependents: tuple[ModeloFormCasillaAddressV1, ...] | None


class ModeloFormStatedPriorValue(ModeloFormBase):
    """The mark of a carry holding a figure the filer stated for an earlier return the application does not hold."""

    #: The earlier return or returns the figure stands in for, in the form's language.
    source_words: str = Field(min_length=1)
    #: Where the box's value comes from, in the few words a frontend shows beside it.
    origin_words: str = Field(min_length=1)
    #: The family of the statement, the carries standing in for the same earlier returns, as
    #: :attr:`ModeloWorkForm.prior_value_attestations` names it; left out when ``None``.
    family_id: str | None = Field(default=None, min_length=1, exclude_if=_is_absent)


class ModeloFormBindingStatement(ModeloFormBase):
    """One statement the edit admits on a single carry, worded for the form.

    ``attest_no_amount`` states the carry holds nothing; ``attest_prior_value``
    states its figure for the earlier return ``source_words`` names, which the
    application does not hold. Applying it stages that one intent on
    ``binding_id``; withdrawing it stages ``remove_override`` on the same binding.
    """

    intent: ModeloEditBindingIntentKind
    binding_id: BindingId
    #: The action, in the form's language.
    action_words: str = Field(min_length=1)
    #: What the statement records and what follows when an earlier return later shows otherwise.
    statement_words: str = Field(min_length=1)
    #: What the statement does to the carry, as a review lists each staged change.
    effect_words: str = Field(min_length=1)
    #: The earlier return a stated figure stands in for; ``None`` for a statement of no amount.
    source_words: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _a_figure_names_its_earlier_return(self) -> ModeloFormBindingStatement:
        if self.intent not in _CARRY_STATEMENT_INTENTS:
            raise ValueError("a carry statement states no amount or an earlier return's figure")
        if (self.intent is ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE) != (self.source_words is not None):
            raise ValueError("a stated figure, and only a stated figure, names the earlier return it stands in for")
        return self


class ModeloFormCarryAttestation(ModeloFormBase):
    """The statement a filer can make that no amount from an earlier ejercicio is still pending.

    It is offered while a carry the declaration reads from an earlier filing
    holds no value: no stored earlier return supplied it, and the filer has
    neither entered it nor stated it. Applying it stages one ``attest_no_amount``
    intent per binding, which records each as a zero the filer stated.
    """

    #: The family of carries the statement answers, as their bindings declare it.
    family: AbsenceAttestationFamily
    #: The carries the statement answers, each a binding override the edit admits the statement on.
    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    #: The action, in the form's language.
    action_words: str = Field(min_length=1)
    #: What the statement records and what happens when an earlier return later shows an amount.
    statement_words: str = Field(min_length=1)
    #: What the statement does to one carry, as a review lists each staged change.
    effect_words: str = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _bindings_are_unique_and_sorted(self) -> ModeloFormCarryAttestation:
        if list(self.binding_ids) != sorted(set(self.binding_ids)):
            raise ValueError("a carry attestation names each binding once, in order")
        return self


class ModeloWorkForm(ModeloFormBase):
    """The editor form of one work target in one language."""

    modelo: ModeloCode
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    #: Whether the filing year is carried across from another edition, and the authority it reaches.
    year_projection: ModeloFormYearProjection
    work_unit_id: str
    calculation_revision_id: str | None
    language: OutputLanguage
    layout_provenance: ModeloFormLayoutProvenance
    inspection_reason: ModeloFormInspectionReason | None = None
    seed_source: FormLayoutSeedSource | None = None
    pages: tuple[ModeloFormPage, ...]
    #: The navigation outline over :attr:`pages`: the layout's declared groups, or one group per page.
    outline: tuple[ModeloFormOutlineGroup, ...]
    working_figures: tuple[ModeloFormField, ...] = ()
    unplaced: tuple[ModeloFormUnplacedField, ...] = ()
    #: The binding overrides the edit surface admits that no field of the pages, the working figures or the
    #: unplaced list takes, each as a field of its own, so every answer the declaration can be given has a place.
    answers: tuple[ModeloFormField, ...] = ()
    result_addresses: tuple[CasillaId, ...] = ()
    #: The boxes the withholding register supplies, in reading order, each with the boxes worked out from it.
    withholding_credits: tuple[ModeloFormCredit, ...] = ()
    #: Who withheld :attr:`withholding_credits`, in the form's language; ``None`` when the form has none.
    withholding_credits_heading: str | None = None
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
    #: Whether the annual estimate from the quarterly declarations (``modelo.project``) can be asked
    #: for this declaration: the registry's projection declaration targets this modelo, period and
    #: revision. ``False`` says it cannot, never that an estimate would be empty.
    projectable: bool = False
    #: Whether this revision's calculation reads the income imputation election (RIRPF art. 7): the
    #: registry declares a binding whose resolver places activity income or expense by the taxpayer's
    #: dated criterion. ``False`` says the declaration does not ask for it, never that none is stated.
    asks_imputation_election: bool = False
    #: Whether joint and individual filing can be compared (``modelo.work.compare_taxation``) for this
    #: declaration: its revision declares the declaration-type box, bound to the profile, and the cuota
    #: resultante and cuota diferencial it compares. ``False`` says the comparison cannot be asked, never
    #: that either mode comes out lower.
    compares_taxation: bool = False
    #: Whether the AEAT draft (Borrador) can be compared with the calculation (``live.borrador.100.compare``)
    #: for this declaration: its revision declares one Borrador PDF extraction profile. ``False`` says no
    #: draft can be read for it, never that a draft agrees.
    compares_borrador: bool = False
    #: Whether this declaration offers the profile's IVA compensation wallet: its revision declares the
    #: compensación-pendiente binding the wallet decision owns. It holds before any calculation and says
    #: nothing about the balance, the wallet's history or whether a wallet write would be admitted.
    offers_iva_wallet: bool = False
    #: Whether the source movements changed after the last check read them, such as evidence attached
    #: since, so its findings may no longer stand and the check is the next thing to run. ``False`` when
    #: they did not, or when the check recorded nothing to compare with.
    verification_out_of_date: bool = False
    #: Set when the declaration is recorded as filed.
    filing: ModeloFormFiling | None = None
    #: The latest file exported for this declaration, or ``None`` when none was ever exported.
    last_export: ModeloFormExport | None = None
    #: Why nothing may be edited, when something other than the admission closes the form.
    edit_closure: ModeloFormEditClosure | None = None
    #: The statements that no earlier-ejercicio amount is pending, one per family, while a carry each
    #: answers holds no value.
    carry_attestations: tuple[ModeloFormCarryAttestation, ...] = ()
    #: The carries whose figure the filer can state for earlier returns the application does not hold, one per
    #: carry the edit takes, with why a statement is refused and how a family's statements are withdrawn; left
    #: out when there are none.
    prior_value_attestations: tuple[ModeloFormPriorValueAttestation, ...] = Field(default=(), exclude_if=_is_empty)
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
        self._require_outline_to_match_the_form()
        self._require_answers_to_be_taken_nowhere_else()
        return self

    def _require_answers_to_be_taken_nowhere_else(self) -> None:
        if not self.answers:
            return
        answered = [field.address for field in self.answers]
        if not all(isinstance(address, ModeloFormBindingAddressV1) for address in answered):
            raise ValueError("an answer is a binding no other field of the form takes")
        taken = {
            address_key(address)
            for field in self.fields()[: -len(self.answers)]
            for address in (field.address, field.edit_address)
        }
        keys = [address_key(address) for address in answered]
        if len(set(keys)) != len(keys) or taken.intersection(keys):
            raise ValueError("an answer is a binding no other field of the form takes")

    def _require_outline_to_match_the_form(self) -> None:
        outlined = [section_id for group in self.outline for section_id in group.section_ids]
        if sorted(outlined) != sorted(section.id for page in self.pages for section in page.sections):
            raise ValueError("the outline must name every section of the form exactly once")
        kept_apart = {
            ModeloFormOutlineKind.WORKING_FIGURES: bool(self.working_figures),
            ModeloFormOutlineKind.UNPLACED: bool(self.unplaced),
            ModeloFormOutlineKind.ANSWERS: bool(self.answers),
        }
        for kind, present in kept_apart.items():
            if sum(1 for group in self.outline if group.kind is kind) != int(present):
                raise ValueError(f"the outline holds one {kind.value} group when the form has such boxes, else none")

    @property
    def calculation_out_of_date(self) -> bool:
        """Whether the calculation must be worked out again before it can be checked, exported or recorded.

        The last check found the records changed after the calculation, unless
        what it read has itself changed since, or the calculation was screened
        against other registry declarations than the pinned ones, which the gate
        refuses until it is calculated again.
        """
        stale_finding = not self.verification_out_of_date and any(
            issue.finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION for issue in self.issues
        )
        return stale_finding or any(
            note.reason == CALCULATION_SCREEN_OUTDATED_REASON for note in self.calculation_notes
        )

    @property
    def filed_before_grade_cap(self) -> bool:
        """Whether the declaration was recorded before screens existed with a figure in a capped box.

        Its export is refused until it is calculated again, checked and recorded
        anew, so the form offers that recalculation in place of the recorded state.
        """
        return any(note.reason == FILED_BEFORE_GRADE_CAP_REASON for note in self.calculation_notes)

    @property
    def blocking_calculation_notes(self) -> tuple[ModeloFormCalculationNote, ...]:
        """The latest calculation's notes that withhold filing, as blocking findings do: at that level or gated."""
        return tuple(
            note
            for note in self.calculation_notes
            if note.attention is ModeloFormAttention.BLOCKS or note.withholds_filing
        )

    def fields(self) -> tuple[ModeloFormField, ...]:
        """Return every field once, in reading order: pages, then working figures, unplaced, then answers."""
        collected: list[ModeloFormField] = []
        for page in self.pages:
            for section in page.sections:
                collected.extend(section_fields(section))
        collected.extend(self.working_figures)
        collected.extend(item.field for item in self.unplaced)
        collected.extend(self.answers)
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
    """Return ``form`` with ``change`` applied to every field: on its pages, working figures, unplaced and answers."""
    return form.model_copy(
        update={
            "pages": tuple(
                page.model_copy(update={"sections": tuple(map_section_fields(s, change) for s in page.sections)})
                for page in form.pages
            ),
            "working_figures": tuple(change(field) for field in form.working_figures),
            "unplaced": tuple(item.model_copy(update={"field": change(item.field)}) for item in form.unplaced),
            "answers": tuple(change(field) for field in form.answers),
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
    "ModeloFormBindingInputsBlock",
    "ModeloFormBlock",
    "ModeloFormContextFieldBlock",
    "ModeloFormCounts",
    "ModeloFormCredit",
    "ModeloFormField",
    "ModeloFormFieldBlock",
    "ModeloFormGridBlock",
    "ModeloFormGridCell",
    "ModeloFormGridColumn",
    "ModeloFormGridRow",
    "ModeloFormInspectionReason",
    "ModeloFormLayoutProvenance",
    "ModeloFormOutlineGroup",
    "ModeloFormPage",
    "ModeloFormRepeatingBlock",
    "ModeloFormRepeatingRow",
    "ModeloFormSection",
    "ModeloFormSourceGroup",
    "ModeloFormSourceGroupKind",
    "ModeloFormSourceReading",
    "ModeloFormSourceState",
    "ModeloFormUnplacedField",
    "ModeloWorkForm",
    "confirmable",
    "edit_address",
    "map_form_fields",
    "map_section_fields",
    "revised_field",
    "section_fields",
    "typed_by_the_filer",
]
