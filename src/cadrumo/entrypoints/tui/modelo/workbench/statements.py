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

The dialog covers the header, so it can repeat the header's result line as its
first line.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

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
from .status_bar import StatusBar

if TYPE_CHECKING:
    from .header import StatusLine


_PRIOR_HEADING_LOCALE_KEY: Final[str] = "tui.modelo.statements.prior.heading"


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
class StatementsChoice:
    """What the dialog closed with: the statements ticked, and the families whose withdrawal is ticked."""

    statements: tuple[ModeloFormCarryAttestation, ...]
    withdrawn_families: frozenset[str]


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
    ) -> None:
        """Hold every statement the form serves, in its order.

        ``staged`` holds the positions among ``statements`` already staged,
        which open ticked. ``status_line`` is the header's result line, shown
        first because the dialog covers it. ``prior_values`` are the figures the form serves for earlier
        returns, in ``language``; ``prior_staged`` holds the families whose withdrawal is already staged.
        """
        super().__init__()
        self._statements = statements
        self._staged = staged
        self._status_line = status_line
        self._families = prior_value_families(prior_values, language) if language is not None else ()
        self._prior_staged = prior_staged

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
        for position, refusal in enumerate(family.refusals):
            yield RefusalSlot(refusal, id=f"prior-refusal-{index}-{position}")

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
        ticked = frozenset(
            position
            for position in range(len(self._statements))
            if self.query_one(f"#statement-{position}", Checkbox).value
        )
        self.query_one("#statements-stage", Button).disabled = (
            ticked == self._staged and self._ticked_families() == self._prior_staged
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the statements ticked, or with nothing."""
        if event.button.id == "statements-stage":
            self.dismiss(StatementsChoice(self.chosen(), self._ticked_families()))
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Close without staging or withdrawing anything."""
        self.dismiss(None)

    async def refresh_language(self) -> None:
        """Reword the dialog's own words; the statements keep the words the form served."""
        refresh_localized_widgets(self)


__all__ = ["PriorValueFamily", "StatementsChoice", "StatementsScreen", "prior_value_families"]
