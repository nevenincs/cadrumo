"""The classified facts of a Modelo work form, apart from the words and controls that present them.

A form's filing facts -- what is still to do, what blocks filing, the result,
the next step and the journey -- rest on how each box is classified and where
it sits, never on its label, help or edit controls. The summary
(:class:`ModeloWorkFormSummary`) holds exactly those facts, classified once;
the full form is built from it and adds every field's presentation on top.

The functions that decide the filing facts read either through
:class:`ModeloFormFacts`, which the summary and the full
:class:`~.work_form_models.ModeloWorkForm` both provide, so the two reads of one
stored state answer with the same functions over the same classification.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from ...domain.calculations.registry.ids import BindingId
from .work_form_field_vocabulary import (
    ASKS_FOR_A_VALUE,
    ModeloFormAddressV1,
    ModeloFormBlocker,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormStanding,
)
from .work_form_models import (
    ModeloFormCounts,
    ModeloFormField,
    form_blocking_calculation_notes,
    form_calculation_out_of_date,
    form_filed_before_grade_cap,
)

if TYPE_CHECKING:
    from ...core.external_constants import OutputLanguage
    from ...core.period import Period
    from ...domain.modelos.codes import ModeloCode
    from ...domain.modelos.verification_report import VerificationCompletenessStatus
    from .work_form_declaration_facts import (
        ModeloFormCalculationNote,
        ModeloFormDeadline,
        ModeloFormEditClosure,
        ModeloFormExport,
        ModeloFormFiling,
        ModeloFormResult,
    )
    from .work_form_findings import ModeloFormIssue
    from .work_form_models import ModeloFormRepeatingRow


class ModeloFormFieldFactsLike(Protocol):
    """What the filing facts read of one box or binding input: where it is, what it holds and where it stands."""

    @property
    def address(self) -> ModeloFormAddressV1:
        """Where the box sits: its casilla or its binding."""
        ...

    @property
    def box(self) -> str | None:
        """The number the form prints for the box, if any."""
        ...

    @property
    def value(self) -> ModeloFormScalar:
        """What the box holds; ``None`` when nothing."""
        ...

    @property
    def origin(self) -> ModeloFormOrigin:
        """Where the box's value stands."""
        ...

    @property
    def standing(self) -> ModeloFormStanding:
        """Where the box stands for the filer on its declaration and page."""
        ...

    @property
    def blockers(self) -> tuple[ModeloFormBlocker, ...]:
        """The verification findings that block the box."""
        ...


class ModeloFormPageFactsLike(Protocol):
    """What the filing facts read of one official page: whether it applies and what its boxes count."""

    @property
    def id(self) -> str:
        """The page's id."""
        ...

    @property
    def applies(self) -> bool | None:
        """Whether the page applies to this filing; ``None`` when the data cannot say."""
        ...

    @property
    def counts(self) -> ModeloFormCounts:
        """What the boxes count, by origin and by what they ask of the filer."""
        ...


class ModeloFormFieldSource[F: ModeloFormFieldFactsLike](Protocol):
    """The boxes of a form in reading order: each page's, then those no page shows."""

    @property
    def pages(self) -> Sequence[ModeloFormPageFactsLike]:
        """The official pages, in reading order."""
        ...

    def page_fields(self) -> tuple[tuple[str, tuple[F, ...]], ...]:
        """Every page's id with its boxes, in reading order."""
        ...

    def detail_fields(self) -> tuple[F, ...]:
        """The boxes no page shows, in reading order: working figures, unplaced, then answers."""
        ...


class ModeloFormFacts(ModeloFormFieldSource[ModeloFormFieldFactsLike], Protocol):
    """Everything the filing facts of one declaration's form are decided from."""

    @property
    def period(self) -> Period:
        """The declaration's period."""
        ...

    @property
    def language(self) -> OutputLanguage:
        """The language the form is read in."""
        ...

    @property
    def calculation_revision_id(self) -> str | None:
        """The calculation the form shows; ``None`` before any."""
        ...

    @property
    def registry_revision_id(self) -> str:
        """The registry revision the form's boxes are read against."""
        ...

    @property
    def counts(self) -> ModeloFormCounts:
        """What the boxes count, by origin and by what they ask of the filer."""
        ...

    @property
    def result_addresses(self) -> tuple[str, ...]:
        """The casillas declared as settlement results, in review order."""
        ...

    @property
    def result(self) -> ModeloFormResult | None:
        """The settlement box and its direction; ``None`` when the registry names none."""
        ...

    @property
    def issues(self) -> tuple[ModeloFormIssue, ...]:
        """The last check's findings, blocking first."""
        ...

    @property
    def calculation_notes(self) -> tuple[ModeloFormCalculationNote, ...]:
        """What the latest calculation noticed that no finding already says, most urgent first."""
        ...

    @property
    def verification(self) -> VerificationCompletenessStatus | None:
        """The current calculation's latest verification verdict; ``None`` when unchecked."""
        ...

    @property
    def verification_out_of_date(self) -> bool:
        """Whether the movements the last check read changed after it read them."""
        ...

    @property
    def filing(self) -> ModeloFormFiling | None:
        """The recorded filing; ``None`` when the declaration is not recorded as filed."""
        ...

    @property
    def last_export(self) -> ModeloFormExport | None:
        """The latest file exported for the declaration; ``None`` when none was."""
        ...

    @property
    def deadline(self) -> ModeloFormDeadline | None:
        """The last day to file; ``None`` when no window is declared."""
        ...

    @property
    def calculation_out_of_date(self) -> bool:
        """Whether the calculation must be worked out again first."""
        ...

    @property
    def filed_before_grade_cap(self) -> bool:
        """Whether the declaration was recorded before screens existed with a figure in a capped box."""
        ...

    @property
    def blocking_calculation_notes(self) -> tuple[ModeloFormCalculationNote, ...]:
        """The latest calculation's notes that withhold filing."""
        ...

    def fields(self) -> tuple[ModeloFormFieldFactsLike, ...]:
        """Every box once, in reading order."""
        ...

    def record_casilla_ids(self) -> frozenset[str]:
        """The casillas a table of records carries a value of."""
        ...

    def presented_casilla(self, casilla_id: str) -> ModeloFormField | None:
        """The full field of a box that states the result; ``None`` when there is none."""
        ...


@dataclass(frozen=True, slots=True)
class ModeloFormFieldFacts:
    """One box or binding input as the form classifies it, before any word presents it.

    ``box`` is the number the form prints for a casilla; a binding input reads
    none here, since no filing fact names a binding by box. ``first_binding_id``
    is the binding an override of the field replaces, the one that takes it as
    an answer. ``design_constant`` marks a box whose value the official design
    fixes.
    """

    address: ModeloFormAddressV1
    box: str | None
    value: ModeloFormScalar
    origin: ModeloFormOrigin
    standing: ModeloFormStanding
    blockers: tuple[ModeloFormBlocker, ...]
    first_binding_id: BindingId | None
    design_constant: bool = False


def asking_no_value(facts: ModeloFormFieldFacts) -> ModeloFormFieldFacts:
    """The box as a page that does not apply shows it: a value it asked for is no longer asked."""
    if facts.standing is not ModeloFormStanding.NEEDS_YOU or facts.blockers or facts.origin not in ASKS_FOR_A_VALUE:
        return facts
    return replace(facts, standing=ModeloFormStanding.DONE)


@dataclass(frozen=True, slots=True)
class ModeloFormRecordBlock:
    """One table of records a section holds, as its saved rows read it.

    ``position`` is the page, the section and the block, the place the form
    shows the table.
    """

    position: tuple[str, str, str]
    rows_known: bool
    rows: tuple[ModeloFormRepeatingRow, ...]
    column_casilla_ids: tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class ModeloFormPageFacts:
    """One official page, whether it applies, its boxes' facts in reading order and their counts."""

    id: str
    applies: bool | None
    counts: ModeloFormCounts
    fields: tuple[ModeloFormFieldFacts, ...]


@dataclass(frozen=True, slots=True)
class ModeloFormDetailFacts:
    """The boxes no page shows: working figures, unplaced casillas and answers, in reading order."""

    working_figures: tuple[ModeloFormFieldFacts, ...] = ()
    unplaced: tuple[ModeloFormFieldFacts, ...] = ()
    answers: tuple[ModeloFormFieldFacts, ...] = ()


@dataclass(frozen=True, slots=True)
class ModeloWorkFormSummary:
    """One declaration's form classified, without the fields' words and controls.

    It is the single owner of the facts a form's filing state rests on; the
    full form is built from it. ``presented`` holds the full field of each box
    that states the result, the only boxes whose words a filing fact says.
    ``alias_blocks`` are the positions of the blocks that repeat a box shown
    elsewhere, and ``records`` the tables of records the pages hold.
    """

    modelo: ModeloCode
    filing_year: int
    period: Period
    registry_revision_id: str
    work_unit_id: str
    calculation_revision_id: str | None
    language: OutputLanguage
    pages: tuple[ModeloFormPageFacts, ...]
    details: ModeloFormDetailFacts
    counts: ModeloFormCounts
    result_addresses: tuple[str, ...]
    result: ModeloFormResult | None
    issues: tuple[ModeloFormIssue, ...]
    calculation_notes: tuple[ModeloFormCalculationNote, ...]
    calculation_notes_held: bool
    verification: VerificationCompletenessStatus | None
    verification_out_of_date: bool
    filing: ModeloFormFiling | None
    edit_closure: ModeloFormEditClosure | None
    last_export: ModeloFormExport | None
    deadline: ModeloFormDeadline | None
    presented: Mapping[str, ModeloFormField]
    alias_blocks: frozenset[tuple[str, str, str]] = frozenset()
    records: tuple[ModeloFormRecordBlock, ...] = ()
    #: Whether an earlier return a relation of the calculation found nothing of is held now.
    calculation_sources_arrived: bool = False

    @property
    def calculation_out_of_date(self) -> bool:
        """Whether the calculation must be worked out again before it can be checked, exported or recorded."""
        return form_calculation_out_of_date(
            self.issues,
            self.calculation_notes,
            verification_out_of_date=self.verification_out_of_date,
            sources_arrived=self.calculation_sources_arrived,
        )

    @property
    def filed_before_grade_cap(self) -> bool:
        """Whether the declaration was recorded before screens existed with a figure in a capped box."""
        return form_filed_before_grade_cap(self.calculation_notes)

    @property
    def blocking_calculation_notes(self) -> tuple[ModeloFormCalculationNote, ...]:
        """The latest calculation's notes that withhold filing."""
        return form_blocking_calculation_notes(self.calculation_notes)

    def page_fields(self) -> tuple[tuple[str, tuple[ModeloFormFieldFacts, ...]], ...]:
        """Every page's id with its boxes' facts, in reading order."""
        return tuple((page.id, page.fields) for page in self.pages)

    def detail_fields(self) -> tuple[ModeloFormFieldFacts, ...]:
        """The boxes no page shows, in reading order: working figures, unplaced, then answers."""
        details = self.details
        return (*details.working_figures, *details.unplaced, *details.answers)

    def fields(self) -> tuple[ModeloFormFieldFacts, ...]:
        """Every box once, in reading order: pages, then working figures, unplaced, then answers."""
        return (*(field for page in self.pages for field in page.fields), *self.detail_fields())

    def record_casilla_ids(self) -> frozenset[str]:
        """The casillas a table of records carries a value of, in every record."""
        return frozenset(
            casilla_id for record in self.records for casilla_id in record.column_casilla_ids if casilla_id is not None
        )

    def presented_casilla(self, casilla_id: str) -> ModeloFormField | None:
        """The full field of one box that states the result; ``None`` for any other box."""
        return self.presented.get(casilla_id)


__all__ = [
    "ModeloFormDetailFacts",
    "ModeloFormFacts",
    "ModeloFormFieldFacts",
    "ModeloFormFieldFactsLike",
    "ModeloFormFieldSource",
    "ModeloFormPageFacts",
    "ModeloFormPageFactsLike",
    "ModeloFormRecordBlock",
    "ModeloWorkFormSummary",
    "asking_no_value",
]
