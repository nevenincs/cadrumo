"""The statements a declaration serves, offered together so the filer can make several in one review.

The form serves each statement the filer can make about a family of boxes:
the action, what it states, and what it does. The dialog lists every one the
form serves, in the order it serves them and in its words, each with a tick;
the workbench names no family and chooses none. Ticking several stages them
all, and leaving one staged earlier unticked withdraws it, so the dialog
always shows what the review will hold. Nothing is applied from here.

A figure the filer stated for earlier returns the application does not hold is
listed under the statements, one entry per family in the form's words: the
carries that stand in for the same earlier returns are one statement, withdrawn
whole by one tick the form serves the words for. A family the form does not
admit a figure for is shown with the refusal's words and its served ways out;
nothing here words either.

A family the form admits a figure for, with none stated, offers one entry per carry of it, labelled with
the carry's own words. It is stated whole or not at all: every entry is filled and read, or none is. An entry
the application cannot read is refused with its own words and nothing is staged.

The dialog covers the header, so it can repeat the header's result line as its
first line.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Static

from .....application.modelo.edit_models import MAX_EDIT_LEXEME_LENGTH
from .....application.modelo.work_form_field_vocabulary import ModeloFormScalar
from .....application.modelo.work_form_models import ModeloFormCarryAttestation
from .....application.modelo.work_form_prior_value_models import ModeloFormPriorValueAttestation
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.language import localized, refresh_localized_widgets
from ...components.theme import tokenised
from ...refusal.panel import RefusalPanel, RefusalSlot
from ...refusal.served import ServedRefusalV1, ServedWordsV1
from .bulk_confirm import TickBox
from .dialog_width import fit_dialog_width
from .ports import WorkbenchParsed, WorkbenchParseOutcome, WorkbenchRefused
from .status_bar import StatusBar

if TYPE_CHECKING:
    from .header import StatusLine


_PRIOR_HEADING_LOCALE_KEY: Final[str] = "tui.modelo.statements.prior.heading"
_PRIOR_PARTIAL_LOCALE_KEY: Final[str] = "tui.modelo.statements.prior.partial"
_PRIOR_UNREADABLE_LOCALE_KEY: Final[str] = "workspace.modelo.editor.unreadable"

type FigureParser = Callable[[str, str], WorkbenchParseOutcome]
"""Read what the filer typed for one carry, given the carry's binding and the text."""

type StagedFigures = Mapping[str, Mapping[str, tuple[ModeloFormScalar, str]]]
"""The figures already staged, by family and then by carry: each a value and how it reads back."""


@dataclass(frozen=True, slots=True)
class PriorValueFamily:
    """The carries standing in for the same earlier returns, as the form serves them: one statement.

    ``withdrawing`` is the served attestation whose withdrawal takes the whole family out, or ``None`` when
    the form offers none. ``refusals`` are the distinct refusals served for the carries it does not admit.
    """

    family_id: str
    attestations: tuple[ModeloFormPriorValueAttestation, ...]
    withdrawing: ModeloFormPriorValueAttestation | None
    refusals: tuple[ServedRefusalV1, ...]

    @property
    def source_words(self) -> str:
        """The earlier returns the family stands in for, in the form's words."""
        return self.attestations[0].source_words

    @property
    def stated(self) -> bool:
        """Whether any carry of the family holds a figure the filer stated."""
        return any(item.stated for item in self.attestations)

    @property
    def statement_words(self) -> str:
        """What the statement records, in the form's words."""
        return self.attestations[0].statement_words

    @property
    def statable(self) -> bool:
        """Whether the form admits a figure on every carry of the family and none holds one yet."""
        return not self.stated and all(item.admitted for item in self.attestations)


def prior_value_families(
    attestations: tuple[ModeloFormPriorValueAttestation, ...], language: OutputLanguage
) -> tuple[PriorValueFamily, ...]:
    """Group the served attestations by family, in the order the form serves them."""
    grouped: dict[str, list[ModeloFormPriorValueAttestation]] = {}
    for attestation in attestations:
        grouped.setdefault(attestation.family_id, []).append(attestation)
    families: list[PriorValueFamily] = []
    for family_id, members in grouped.items():
        refusals: list[ServedRefusalV1] = []
        for member in members:
            if member.admitted or member.refusal_words is None:
                continue
            served = ServedRefusalV1(
                refusal_words=ServedWordsV1(words=member.refusal_words, language=language), verdict=member.refusal
            )
            if served not in refusals:
                refusals.append(served)
        withdrawing = next((member for member in members if member.withdrawal is not None), None)
        families.append(PriorValueFamily(family_id, tuple(members), withdrawing, tuple(refusals)))
    return tuple(families)


@dataclass(frozen=True, slots=True)
class PriorFigure:
    """One carry's figure, read: its binding, the value and how that value reads back."""

    binding_id: str
    value: ModeloFormScalar
    display: str


@dataclass(frozen=True, slots=True)
class StatedFamily:
    """The figures the filer gave for one family, every carry of it, read."""

    family_id: str
    figures: tuple[PriorFigure, ...]


@dataclass(frozen=True, slots=True)
class StatementsChoice:
    """What the dialog closed with: the statements ticked, the families whose withdrawal is ticked, the figures."""

    statements: tuple[ModeloFormCarryAttestation, ...]
    withdrawn_families: frozenset[str]
    #: The families stated whole; a statable family absent here has none stated.
    stated_families: tuple[StatedFamily, ...] = ()


class StatementsScreen(ModalScreen[StatementsChoice | None]):
    """Offer every statement the form serves; close with the ones ticked, in the order served."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        StatementsScreen #statements-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        StatementsScreen #statements-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        StatementsScreen.-narrow #statements-panel {
            width: 100%;
        }
        StatementsScreen #statements-status {
            height: auto;
        }
        StatementsScreen #statements-title {
            text-style: bold;
            color: $foreground;
        }
        StatementsScreen #statements-intro {
            color: $secondary;
            height: auto;
            margin-bottom: $cadrumo-stack;
        }
        StatementsScreen #statements-body {
            height: 1fr;
        }
        StatementsScreen .statement-tick > .toggle--button {
            color: $foreground;
        }
        StatementsScreen .statement-tick.-on > .toggle--button {
            color: $text-success;
        }
        StatementsScreen .statement-words {
            height: auto;
            color: $secondary;
            padding: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-gutter;
            margin-bottom: $cadrumo-stack;
        }
        StatementsScreen .prior-heading {
            text-style: bold;
            color: $foreground;
            margin-top: $cadrumo-stack;
        }
        StatementsScreen .prior-source {
            height: auto;
            color: $foreground;
        }
        StatementsScreen .figure-label {
            height: auto;
            color: $foreground;
            padding: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-gutter;
        }
        StatementsScreen .figure-input {
            margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-stack $cadrumo-gutter;
        }
        StatementsScreen .figure-error {
            height: auto;
            color: $warning;
            padding: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-gutter;
        }
        StatementsScreen #statements-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        StatementsScreen #statements-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        statements: tuple[ModeloFormCarryAttestation, ...],
        *,
        staged: frozenset[int] = frozenset(),
        status_line: StatusLine | None = None,
        prior_values: tuple[ModeloFormPriorValueAttestation, ...] = (),
        prior_staged: frozenset[str] = frozenset(),
        language: OutputLanguage | None = None,
        figure_labels: Mapping[str, str] | None = None,
        figure_parser: FigureParser | None = None,
        figures_staged: StagedFigures | None = None,
    ) -> None:
        """Hold every statement the form serves, in its order.

        ``staged`` holds the positions among ``statements`` already staged,
        which open ticked. ``status_line`` is the header's result line, shown
        first because the dialog covers it. ``prior_values`` are the figures the form serves for earlier
        returns, in ``language``; ``prior_staged`` holds the families whose withdrawal is already staged.
        ``figure_parser`` reads a figure typed for a carry and ``figure_labels`` gives each carry its words;
        without a parser no figure is offered. ``figures_staged`` are the figures already staged.
        """
        super().__init__()
        self._statements = statements
        self._staged = staged
        self._status_line = status_line
        self._families = prior_value_families(prior_values, language) if language is not None else ()
        self._prior_staged = prior_staged
        self._figure_labels = figure_labels or {}
        self._figure_parser = figure_parser
        self._figures_staged = figures_staged or {}

    @property
    def statements(self) -> tuple[ModeloFormCarryAttestation, ...]:
        """The statements the dialog lists, in the order the form serves them."""
        return self._statements

    @property
    def families(self) -> tuple[PriorValueFamily, ...]:
        """The families of stated figures the dialog lists, in the order the form serves them."""
        return self._families

    @override
    def compose(self) -> ComposeResult:
        with Container(id="statements-backdrop"), Vertical(id="statements-panel"):
            if self._status_line is not None:
                yield StatusBar(self._status_line, id="statements-status")
            yield localized(
                Static(tr("tui.modelo.statements.title"), id="statements-title", markup=False),
                "tui.modelo.statements.title",
            )
            yield localized(
                Static(tr("tui.modelo.statements.intro"), id="statements-intro", markup=False),
                "tui.modelo.statements.intro",
            )
            with VerticalScroll(id="statements-body"):
                for position, statement in enumerate(self._statements):
                    # The served words are shown as written, never read as markup.
                    yield TickBox(
                        Content(statement.action_words),
                        value=position in self._staged,
                        id=f"statement-{position}",
                        classes="statement-tick",
                        compact=True,
                    )
                    yield Static(statement.statement_words, classes="statement-words", markup=False)
                if self._families:
                    yield localized(
                        Static(tr(_PRIOR_HEADING_LOCALE_KEY), classes="prior-heading", markup=False),
                        _PRIOR_HEADING_LOCALE_KEY,
                    )
                for index, family in enumerate(self._families):
                    yield from self._compose_family(index, family)
            with Horizontal(id="statements-actions"):
                yield localized(
                    Button(tr("workspace.modelo.editor.cancel"), id="statements-cancel"),
                    "workspace.modelo.editor.cancel",
                )
                yield localized(
                    Button(
                        tr("tui.modelo.statements.stage"),
                        id="statements-stage",
                        variant="primary",
                        disabled=True,
                    ),
                    "tui.modelo.statements.stage",
                )

    def _compose_family(self, index: int, family: PriorValueFamily) -> ComposeResult:
        """One family: the earlier returns it stands in for, its statement, and the way to withdraw or the refusal."""
        yield Static(family.source_words, id=f"prior-source-{index}", classes="prior-source", markup=False)
        withdrawing = family.withdrawing
        if family.stated and withdrawing is not None and withdrawing.withdrawal is not None:
            yield TickBox(
                Content(withdrawing.withdrawal.action_words),
                value=family.family_id in self._prior_staged,
                id=f"prior-{index}",
                classes="statement-tick",
                compact=True,
            )
            yield Static(withdrawing.withdrawal.effect_words, classes="statement-words", markup=False)
        else:
            yield Static(family.statement_words, id=f"prior-words-{index}", classes="statement-words", markup=False)
        if family.statable and self._figure_parser is not None:
            yield from self._compose_figures(index, family)
        for position, refusal in enumerate(family.refusals):
            yield RefusalSlot(refusal, id=f"prior-refusal-{index}-{position}")

    def _compose_figures(self, index: int, family: PriorValueFamily) -> ComposeResult:
        """One entry per carry of the family, each labelled with the carry's own words, and the family's refusal."""
        staged = self._figures_staged.get(family.family_id, {})
        for position, attestation in enumerate(family.attestations):
            label = self._figure_labels.get(attestation.binding_id, attestation.binding_id)
            yield Static(label, classes="figure-label", markup=False)
            held = staged.get(attestation.binding_id)
            yield Input(
                value="" if held is None else held[1],
                id=f"figure-{index}-{position}",
                classes="figure-input",
                max_length=MAX_EDIT_LEXEME_LENGTH,
                compact=True,
            )
        yield Static("", id=f"figure-error-{index}", classes="figure-error", markup=False)

    def _statable(self) -> tuple[tuple[int, PriorValueFamily], ...]:
        """The families the dialog offers figure entries for, with their positions."""
        if self._figure_parser is None:
            return ()
        return tuple((index, family) for index, family in enumerate(self._families) if family.statable)

    def _typed(self, index: int, family: PriorValueFamily) -> tuple[str, ...]:
        return tuple(
            self.query_one(f"#figure-{index}-{position}", Input).value.strip()
            for position in range(len(family.attestations))
        )

    def _figures_differ(self) -> bool:
        """Whether the entries differ from the figures already staged."""
        for index, family in self._statable():
            staged = self._figures_staged.get(family.family_id, {})
            held = tuple(
                staged[item.binding_id][1] if item.binding_id in staged else "" for item in family.attestations
            )
            if self._typed(index, family) != held:
                return True
        return False

    def _read_figures(self) -> tuple[StatedFamily, ...] | None:
        """Read every family's entries; ``None``, with each refusal shown, when any family is partial or unreadable.

        A family with every entry empty states nothing; a family with some empty is refused whole.
        """
        parser = self._figure_parser
        if parser is None:
            return ()
        stated: list[StatedFamily] = []
        refused = False
        for index, family in self._statable():
            error = self.query_one(f"#figure-error-{index}", Static)
            typed = self._typed(index, family)
            if not any(typed):
                error.update("")
                continue
            if not all(typed):
                error.update(tr(_PRIOR_PARTIAL_LOCALE_KEY))
                refused = True
                continue
            read = self._read_family(family, typed, parser)
            if isinstance(read, str):
                error.update(read)
                refused = True
                continue
            error.update("")
            stated.append(StatedFamily(family.family_id, read))
        return None if refused else tuple(stated)

    def _read_family(
        self, family: PriorValueFamily, typed: tuple[str, ...], parser: FigureParser
    ) -> tuple[PriorFigure, ...] | str:
        """The family's figures, or the words of every entry the application did not read."""
        staged = self._figures_staged.get(family.family_id, {})
        figures: list[PriorFigure] = []
        refusals: list[str] = []
        for attestation, lexeme in zip(family.attestations, typed, strict=True):
            held = staged.get(attestation.binding_id)
            if held is not None and held[1] == lexeme:
                figures.append(PriorFigure(attestation.binding_id, held[0], held[1]))
                continue
            outcome = parser(attestation.binding_id, lexeme)
            if isinstance(outcome, WorkbenchParsed) and outcome.value is not None:
                figures.append(PriorFigure(attestation.binding_id, outcome.value, outcome.display))
                continue
            label = self._figure_labels.get(attestation.binding_id, attestation.binding_id)
            words = outcome.message if isinstance(outcome, WorkbenchRefused) else tr(_PRIOR_UNREADABLE_LOCALE_KEY)
            refusals.append(f"{label}: {words}")
        return "\n".join(refusals) if refusals else tuple(figures)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Take a family's refusal away as soon as an entry changes, and offer staging once entries differ."""
        control = event.input.id or ""
        if control.startswith("figure-"):
            self.query_one(f"#figure-error-{control.split('-')[1]}", Static).update("")
        self._offer_staging()

    def on_refusal_panel_action_chosen(self, message: RefusalPanel.ActionChosen) -> None:
        """Leave the dialog for the destination a way out opens; the host opens it."""
        del message
        self.dismiss(None)

    def _withdrawable(self) -> tuple[tuple[int, PriorValueFamily], ...]:
        """The families the dialog ticks a withdrawal for, with their positions."""
        return tuple(
            (index, family)
            for index, family in enumerate(self._families)
            if family.stated and family.withdrawing is not None and family.withdrawing.withdrawal is not None
        )

    def _ticked_families(self) -> frozenset[str]:
        return frozenset(
            family.family_id
            for index, family in self._withdrawable()
            if self.query_one(f"#prior-{index}", Checkbox).value
        )

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Fit the terminal and put the cursor on the first statement."""
        fit_dialog_width(self, self.app.size.width)
        if self._statements:
            self.query_one("#statement-0", Checkbox).focus()
        elif self._withdrawable():
            self.query_one(f"#prior-{self._withdrawable()[0][0]}", Checkbox).focus()

    def chosen(self) -> tuple[ModeloFormCarryAttestation, ...]:
        """The statements ticked now, in the order the form serves them."""
        return tuple(
            statement
            for position, statement in enumerate(self._statements)
            if self.query_one(f"#statement-{position}", Checkbox).value
        )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Offer staging once the ticks differ from what is staged."""
        del event
        self._offer_staging()

    def _offer_staging(self) -> None:
        ticked = frozenset(
            position
            for position in range(len(self._statements))
            if self.query_one(f"#statement-{position}", Checkbox).value
        )
        self.query_one("#statements-stage", Button).disabled = (
            ticked == self._staged and self._ticked_families() == self._prior_staged and not self._figures_differ()
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the statements ticked, or with nothing."""
        if event.button.id == "statements-stage":
            stated = self._read_figures()
            if stated is not None:
                self.dismiss(StatementsChoice(self.chosen(), self._ticked_families(), stated))
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Close without staging or withdrawing anything."""
        self.dismiss(None)

    async def refresh_language(self) -> None:
        """Reword the dialog's own words; the statements keep the words the form served."""
        refresh_localized_widgets(self)


__all__ = [
    "FigureParser",
    "PriorFigure",
    "PriorValueFamily",
    "StagedFigures",
    "StatedFamily",
    "StatementsChoice",
    "StatementsScreen",
    "prior_value_families",
]
