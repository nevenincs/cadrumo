"""The comparison of joint and individual filing, asked for and shown beside a declaration.

The same declaration is worked out twice, filed jointly and filed individually,
on the values it holds, by the registered comparison operation. It is a read: it
changes nothing. Every figure, the recommendation, its reason and the scope
caveat of the individual figure are the operation's own, shown as served and in
the language they were served in; this module compares no amount and words no
tax statement. Which mode is recommended, or that neither is, is the served
recommendation; the screen only marks the mode it names.

A refusal is shown through the one refusal panel, in its served words and with
its served ways out. The boxes a refusal names as without a value are listed
with the form's own labels; choosing one returns to the workbench on that box.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import ClassVar, Final, Protocol, override, runtime_checkable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from ....application.modelo.taxation_comparison import TaxationRecommendation
from ....application.modelo.taxation_comparison_operation import ModeloTaxationComparisonProjection
from ....application.modelo.value_presentation import format_casilla_value
from ....application.modelo.work_form_field_vocabulary import ModeloFormCasillaAddressV1
from ....application.modelo.work_form_models import ModeloWorkForm
from ....application.operations.error_detail import build_operation_error_detail
from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ....core.logging import get_logger
from ..components.language import localized, refresh_localized_widgets
from ..components.theme import tokenised
from ..refusal.panel import RefusalPanel, RefusalSlot
from ..refusal.served import ServedRefusalV1, served_refusal

_TITLE_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.title"
_LEAD_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.lead"
_ASK_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.ask"
_AGAIN_LOCALE_KEY: Final = "desktop.modelo.compare.again"
_FAILED_LOCALE_KEY: Final = "desktop.modelo.compare.failed"
_REFUSED_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.refused"
_BOXES_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.boxes"
_JOINT_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.joint"
_INDIVIDUAL_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.individual"
_TAX_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.tax"
_RESULT_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.result"
_RECOMMENDED_LOCALE_KEY: Final = "desktop.modelo.compare.taxation.recommended"
_WORDS_LANGUAGE_LOCALE_KEY: Final = "desktop.modelo.compare.words_language"
_READING_LOCALE_KEY: Final = "tui.modelo.taxation.reading"
_CLOSE_LOCALE_KEY: Final = "workspace.modelo.key.close"
KEY_LOCALE_KEY: Final = "tui.modelo.taxation.key"
"""What the workbench's key that opens the comparison says in its footer."""

_CASILLA_IDS_CONTEXT: Final = "casilla_ids"
_LANGUAGE_NAME_KEY: Final = "wizard.setup.profile.output-language.choices.{language}.label"

type ComparisonDoor = Callable[[], Awaitable[ModeloTaxationComparisonProjection]]
"""Ask the registered comparison of the declaration shown and return its served projection."""


@runtime_checkable
class ModeloTaxationComparerV1(Protocol):
    """The workbench's actions, when they can ask for the comparison."""

    async def compare_taxation(self) -> ModeloTaxationComparisonProjection:
        """Work the declaration out filed jointly and individually; raise the served refusal when it is refused."""
        ...


@runtime_checkable
class ModeloTaxationComparisonSourceV1(Protocol):
    """A workbench source that can read the comparison through its runtime session.

    The read is synchronous because the workbench calls it off its event loop.
    """

    def compare_taxation(self) -> ModeloTaxationComparisonProjection:
        """Read the comparison of the declaration this source serves."""
        ...


def offers_taxation_comparison(form: ModeloWorkForm | None) -> bool:
    """Whether the served form says joint and individual filing can be compared."""
    return form is not None and form.compares_taxation


class ComparisonPhase(StrEnum):
    """Where the comparison stands, from not asked for to answered."""

    IDLE = "idle"
    READING = "reading"
    READY = "ready"
    REFUSED = "refused"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class NamedBox:
    """One box a refusal names as without a value, with the form's own words for it when it places the box."""

    casilla_id: str
    box: str
    label: str | None


def named_boxes(form: ModeloWorkForm, casilla_ids: tuple[str, ...]) -> tuple[NamedBox, ...]:
    """The boxes a refusal names, in the order served, each with the form's box number and label if it places it."""
    placed = {
        field.address.casilla_id: field
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    boxes: list[NamedBox] = []
    for casilla_id in casilla_ids:
        field = placed.get(casilla_id)
        boxes.append(
            NamedBox(
                casilla_id=casilla_id,
                box=casilla_id if field is None or field.box is None else field.box,
                label=None if field is None else field.label.text,
            )
        )
    return tuple(boxes)


def _refusal_boxes(refusal_context: dict[str, str]) -> tuple[str, ...]:
    """The box ids a refusal lists, comma separated as the application serves them."""
    served = refusal_context.get(_CASILLA_IDS_CONTEXT, "")
    return tuple(part.strip() for part in served.split(",") if part.strip())


def _amount(text: str, language: OutputLanguage) -> str:
    """A served amount written as a box writes money, keeping the sign it was served with."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        return text
    return format_casilla_value(value, data_type="money", language=language)


def _language_name(code: str) -> str:
    """A language's name, written in that language."""
    return tr(_LANGUAGE_NAME_KEY.format(language=code), locale=code, default=code)


class ModeloTaxationComparisonScreen(ModalScreen[str | None]):
    """Ask for the comparison of one declaration and show what was served.

    Closes with the id of the box the filer chose from a refusal's list, or
    ``None``.
    """

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        ModeloTaxationComparisonScreen #taxcmp-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        ModeloTaxationComparisonScreen #taxcmp-panel {
            width: $cadrumo-modal-width;
            max-width: 100%;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        ModeloTaxationComparisonScreen #taxcmp-title {
            text-style: bold;
            color: $foreground;
        }
        ModeloTaxationComparisonScreen #taxcmp-lead {
            color: $secondary;
            height: auto;
            margin-bottom: $cadrumo-stack;
        }
        ModeloTaxationComparisonScreen #taxcmp-reading {
            color: $secondary;
            height: auto;
        }
        ModeloTaxationComparisonScreen #taxcmp-body {
            height: 1fr;
        }
        ModeloTaxationComparisonScreen #taxcmp-modes {
            height: auto;
        }
        ModeloTaxationComparisonScreen .taxcmp-mode {
            width: 1fr;
            height: auto;
            border: $cadrumo-rule $panel;
            padding: $cadrumo-space-0 $cadrumo-space-1;
        }
        ModeloTaxationComparisonScreen .taxcmp-mode.-recommended {
            border: $cadrumo-rule $success;
        }
        ModeloTaxationComparisonScreen #taxcmp-reason,
        ModeloTaxationComparisonScreen #taxcmp-caveat,
        ModeloTaxationComparisonScreen #taxcmp-language,
        ModeloTaxationComparisonScreen #taxcmp-refused,
        ModeloTaxationComparisonScreen #taxcmp-failed {
            height: auto;
            margin-top: $cadrumo-stack;
        }
        ModeloTaxationComparisonScreen #taxcmp-caveat,
        ModeloTaxationComparisonScreen #taxcmp-language {
            color: $secondary;
        }
        ModeloTaxationComparisonScreen #taxcmp-refused,
        ModeloTaxationComparisonScreen #taxcmp-failed {
            color: $warning;
        }
        ModeloTaxationComparisonScreen #taxcmp-boxes {
            height: auto;
            max-height: $cadrumo-log-max-height;
        }
        ModeloTaxationComparisonScreen #taxcmp-boxes-title {
            height: auto;
            margin-top: $cadrumo-stack;
            text-style: bold;
        }
        ModeloTaxationComparisonScreen #taxcmp-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        ModeloTaxationComparisonScreen #taxcmp-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape,q", "close", "", show=False)]

    def __init__(self, compare: ComparisonDoor, *, form: ModeloWorkForm) -> None:
        """Hold the door that asks for the comparison and the form that names the boxes a refusal lists."""
        super().__init__()
        self._compare = compare
        self._form = form
        self._phase = ComparisonPhase.IDLE
        self._projection: ModeloTaxationComparisonProjection | None = None
        self._refusal: ServedRefusalV1 | None = None
        self._boxes: tuple[NamedBox, ...] = ()
        self._ticket = 0

    @property
    def phase(self) -> ComparisonPhase:
        """Where the comparison stands."""
        return self._phase

    @property
    def projection(self) -> ModeloTaxationComparisonProjection | None:
        """The comparison served, once answered."""
        return self._projection

    @property
    def boxes(self) -> tuple[NamedBox, ...]:
        """The boxes the last refusal named, in the order served."""
        return self._boxes

    @override
    def compose(self) -> ComposeResult:
        with Container(id="taxcmp-backdrop"), Vertical(id="taxcmp-panel"):
            yield localized(Static(tr(_TITLE_LOCALE_KEY), id="taxcmp-title", markup=False), _TITLE_LOCALE_KEY)
            yield localized(Static(tr(_LEAD_LOCALE_KEY), id="taxcmp-lead", markup=False), _LEAD_LOCALE_KEY)
            yield Button(tr(_ASK_LOCALE_KEY), id="taxcmp-ask")
            yield Static("", id="taxcmp-reading", markup=False)
            with VerticalScroll(id="taxcmp-body"):
                with Horizontal(id="taxcmp-modes"):
                    yield Static("", id="taxcmp-joint", classes="taxcmp-mode", markup=False)
                    yield Static("", id="taxcmp-individual", classes="taxcmp-mode", markup=False)
                yield Static("", id="taxcmp-reason", markup=False)
                yield Static("", id="taxcmp-caveat", markup=False)
                yield Static("", id="taxcmp-language", markup=False)
                yield Static("", id="taxcmp-refused", markup=False)
                yield RefusalSlot(id="taxcmp-refusal")
                yield Static("", id="taxcmp-boxes-title", markup=False)
                yield OptionList(id="taxcmp-boxes")
                yield Static("", id="taxcmp-failed", markup=False)
            with Horizontal(id="taxcmp-actions"):
                yield localized(Button(tr(_CLOSE_LOCALE_KEY), id="taxcmp-close"), _CLOSE_LOCALE_KEY)

    def on_mount(self) -> None:
        """Show the idle state, with the ask control in reach."""
        self._paint()
        self.query_one("#taxcmp-ask", Button).focus()

    async def refresh_language(self) -> None:
        """Reword the chrome; the served words stay in the language they were served in."""
        refresh_localized_widgets(self)
        self._paint()

    # -- asking ----------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Ask for the comparison, or close."""
        event.stop()
        if event.button.id == "taxcmp-ask":
            self.ask()
        elif event.button.id == "taxcmp-close":
            self.action_close()

    def ask(self) -> None:
        """Ask again for the comparison; an answer is the latest question's only."""
        if self._phase is ComparisonPhase.READING:
            return
        self._ticket += 1
        self._phase = ComparisonPhase.READING
        self._projection, self._refusal, self._boxes = None, None, ()
        self._paint()
        self.run_worker(self._read(self._ticket), group="taxation-comparison", exclusive=True)

    async def _read(self, ticket: int) -> None:
        projection: ModeloTaxationComparisonProjection | None = None
        refusal: ServedRefusalV1 | None = None
        boxes: tuple[str, ...] = ()
        phase = ComparisonPhase.FAILED
        try:
            projection = await self._compare()
            phase = ComparisonPhase.READY
        except CadrumoError as error:
            detail = build_operation_error_detail(error)
            refusal = served_refusal(detail)
            if detail is not None and refusal is not None:
                boxes = _refusal_boxes(detail.context_mapping())
                phase = ComparisonPhase.REFUSED
            get_logger(__name__).info("taxation comparison was not answered: %s", type(error).__qualname__)
        except Exception as failure:
            get_logger(__name__).error(
                "taxation comparison failed before it was answered: %s", type(failure).__qualname__, exc_info=True
            )
        if ticket != self._ticket:
            return
        self._phase, self._projection, self._refusal = phase, projection, refusal
        self._boxes = named_boxes(self._form, boxes)
        self._paint()
        if phase is ComparisonPhase.REFUSED and self._boxes:
            self.query_one("#taxcmp-boxes", OptionList).focus()
        else:
            self.query_one("#taxcmp-ask", Button).focus()

    # -- painting --------------------------------------------------------------

    def _paint(self) -> None:
        phase = self._phase
        ask = self.query_one("#taxcmp-ask", Button)
        ask.label = tr(
            _AGAIN_LOCALE_KEY if phase in {ComparisonPhase.READY, ComparisonPhase.REFUSED} else _ASK_LOCALE_KEY
        )
        ask.disabled = phase is ComparisonPhase.READING
        reading = self.query_one("#taxcmp-reading", Static)
        reading.update(tr(_READING_LOCALE_KEY) if phase is ComparisonPhase.READING else "")
        reading.display = phase is ComparisonPhase.READING
        projection = self._projection
        self._paint_result(projection if phase is ComparisonPhase.READY else None)
        self._paint_refusal(phase)
        failed = self.query_one("#taxcmp-failed", Static)
        failed.update(tr(_FAILED_LOCALE_KEY) if phase is ComparisonPhase.FAILED else "")
        failed.display = phase is ComparisonPhase.FAILED

    def _paint_result(self, projection: ModeloTaxationComparisonProjection | None) -> None:
        modes = self.query_one("#taxcmp-modes", Horizontal)
        modes.display = projection is not None
        for widget_id in ("#taxcmp-reason", "#taxcmp-caveat", "#taxcmp-language"):
            self.query_one(widget_id, Static).display = projection is not None
        if projection is None:
            return
        language = OutputLanguage(output_language())
        recommended = projection.recommendation
        for widget_id, title_key, tax, result, mode in (
            (
                "#taxcmp-joint",
                _JOINT_LOCALE_KEY,
                projection.conjunta_cuota_resultante,
                projection.conjunta_resultado,
                TaxationRecommendation.CONJUNTA,
            ),
            (
                "#taxcmp-individual",
                _INDIVIDUAL_LOCALE_KEY,
                projection.individual_cuota_resultante,
                projection.individual_resultado,
                TaxationRecommendation.INDIVIDUAL,
            ),
        ):
            widget = self.query_one(widget_id, Static)
            marked = recommended is mode
            widget.set_class(marked, "-recommended")
            heading = f"{tr(title_key)} · {tr(_RECOMMENDED_LOCALE_KEY)}" if marked else tr(title_key)
            widget.update(
                "\n".join(
                    (
                        heading,
                        f"{tr(_TAX_LOCALE_KEY)}: {_amount(tax, language)}",
                        f"{tr(_RESULT_LOCALE_KEY)}: {_amount(result, language)}",
                    )
                )
            )
        self.query_one("#taxcmp-reason", Static).update(projection.recommendation_reason_words)
        self.query_one("#taxcmp-caveat", Static).update(projection.individual_branch_caveat)
        words_language = self.query_one("#taxcmp-language", Static)
        if projection.words_language.value != language.value:
            words_language.update(
                tr(_WORDS_LANGUAGE_LOCALE_KEY, language=_language_name(projection.words_language.value))
            )
        else:
            words_language.update("")
            words_language.display = False

    def _paint_refusal(self, phase: ComparisonPhase) -> None:
        refused = phase is ComparisonPhase.REFUSED
        served = self._refusal if refused else None
        self.query_one("#taxcmp-refusal", RefusalSlot).show(served)
        # A refusal that served no sentence of its own still says that it refused.
        unworded = refused and (served is None or served.refusal_words is None)
        notice = self.query_one("#taxcmp-refused", Static)
        notice.update(tr(_REFUSED_LOCALE_KEY) if unworded else "")
        notice.display = unworded
        title = self.query_one("#taxcmp-boxes-title", Static)
        listing = self.query_one("#taxcmp-boxes", OptionList)
        has_boxes = refused and bool(self._boxes)
        title.update(tr(_BOXES_LOCALE_KEY) if has_boxes else "")
        title.display = has_boxes
        listing.display = has_boxes
        listing.clear_options()
        if has_boxes:
            listing.add_options(
                Option(f"[{box.box}] {box.label}" if box.label is not None else f"[{box.box}]", id=box.casilla_id)
                for box in self._boxes
            )
            listing.highlighted = 0

    # -- leaving ---------------------------------------------------------------

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Return to the workbench on the box the filer chose."""
        event.stop()
        if event.option.id is not None:
            self.dismiss(event.option.id)

    def on_refusal_panel_action_chosen(self, message: RefusalPanel.ActionChosen) -> None:
        """Leave the comparison for the destination a way out opens; the host opens it."""
        del message
        self.dismiss(None)

    def action_close(self) -> None:
        """Close the comparison; it changed nothing."""
        self.dismiss(None)


__all__ = [
    "KEY_LOCALE_KEY",
    "ComparisonDoor",
    "ComparisonPhase",
    "ModeloTaxationComparerV1",
    "ModeloTaxationComparisonScreen",
    "ModeloTaxationComparisonSourceV1",
    "NamedBox",
    "named_boxes",
    "offers_taxation_comparison",
]
