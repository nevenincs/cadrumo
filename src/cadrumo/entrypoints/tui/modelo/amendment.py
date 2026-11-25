"""Prepare a correction of a declaration recorded as filed, on what the application offers for it.

A declaration recorded as filed is never changed in place. Its correction is a
new local declaration: a complementaria, a sustitutiva or a rectificativa,
whichever the period permits. The dialog shows only what the correction read
serves -- the filed declaration's facts, the kinds the period permits with
what each does, the motive where the chosen kind states one, the reason
prompt, and every box the filing declared with its filed figure -- and reads
each corrected figure through the application's grammar for that box. Nothing
is recorded here and nothing is sent to the AEAT: the dialog returns the
filer's answer and the workbench submits it through the supervised operation,
which records the correction locally for the filer to export and file.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Protocol, cast, override, runtime_checkable

from pydantic import ValidationError
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from ....application.modelo.edit_models import (
    MAX_EDIT_LEXEME_LENGTH,
    ModeloEditBaselineV1,
    ModeloEditParsedValueV1,
    ModeloEditParseRequestV1,
)
from ....application.modelo.edit_parsing import parse_modelo_edit_lexeme
from ....application.modelo.edit_review_wording import edit_refusal_words, entry_read_back
from ....application.modelo.work_amend_contracts import ModeloWorkAmendOverride
from ....application.modelo.work_amend_correction import (
    ModeloAmendmentCorrectionContextV1,
    ModeloAmendmentCorrectionRowV1,
)
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.identity.documents import SpanishTaxIdFormat
from ....domain.modelos.calculation_revision_amendment import M303RectificativaMotive
from ....domain.modelos.filing_record import FilingDeclarationKind
from ..components.language import localized, refresh_localized_widgets
from ..components.theme import tokenised
from .workbench.dialog_width import fit_dialog_width
from .workbench.ports import WorkbenchParsed, WorkbenchParseOutcome, WorkbenchRefused

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..operations.controller_port import OperationControllerPort

#: How long a stated reason may be, as the amendment request admits it.
REASON_MAX_LENGTH = 512
_FACT_SEPARATOR = " · "


@dataclass(frozen=True, slots=True)
class ModeloAmendmentAnswerV1:
    """The filer's correction: the kind, the motive where it applies, the reason and each corrected box."""

    kind: FilingDeclarationKind
    motive: M303RectificativaMotive | None
    reason: str
    overrides: tuple[ModeloWorkAmendOverride, ...]


@runtime_checkable
class ModeloWorkbenchAmendmentV1(Protocol):
    """Reads what correcting a declaration recorded as filed offers, reads its figures and records it."""

    async def amendment_context(self, language: OutputLanguage) -> ModeloAmendmentCorrectionContextV1:
        """Read the correction the declaration's current filing offers, worded in ``language``."""
        ...

    def parse_correction(
        self, row: ModeloAmendmentCorrectionRowV1, lexeme: str, language: OutputLanguage
    ) -> WorkbenchParseOutcome:
        """Read one corrected figure as the filer typed it, through the box's correction grammar."""
        ...

    async def amend(self, filing_record_id: str, answer: ModeloAmendmentAnswerV1) -> OperationControllerPort:
        """Submit the correction of ``filing_record_id`` through the supervised operation."""
        ...


def parse_correction_entry(
    row: ModeloAmendmentCorrectionRowV1,
    lexeme: str,
    language: OutputLanguage,
    *,
    baseline: ModeloEditBaselineV1 | None,
    tax_id_format: SpanishTaxIdFormat | None,
) -> WorkbenchParseOutcome:
    """Read a corrected figure through the grammar the correction read served for its box.

    The parser judges an entry against the declaration's admitted edit
    baseline, so without one nothing is read, as an edit is not.
    """
    if baseline is None:
        return WorkbenchRefused(message=tr("workspace.modelo.editability.no_admission"))
    result = parse_modelo_edit_lexeme(
        ModeloEditParseRequestV1(address=row.edit_address, entry_locale=language, lexeme=lexeme),
        baseline=baseline,
        tax_id_format=tax_id_format,
        correction_grammars={row.casilla_id: row.grammar},
    )
    if isinstance(result, ModeloEditParsedValueV1):
        value = result.value
        return WorkbenchParsed(value=value, display=entry_read_back(value, data_type=row.data_type, language=language))
    return WorkbenchRefused(message=edit_refusal_words(result.refusal, language))


def _row_heading(row: ModeloAmendmentCorrectionRowV1) -> str:
    box = f"[{row.box}] " if row.box is not None else ""
    return f"{box}{row.label}{_FACT_SEPARATOR}{row.filed_value_text}"


class ModeloAmendmentScreen(ModalScreen[ModeloAmendmentAnswerV1 | None]):
    """Collect one correction of a declaration recorded as filed."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        ModeloAmendmentScreen #amend-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        ModeloAmendmentScreen #amend-panel {
            width: $cadrumo-modal-width;
            height: auto;
            max-height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        ModeloAmendmentScreen.-narrow #amend-panel {
            width: 100%;
        }
        ModeloAmendmentScreen #amend-title {
            text-style: bold;
            color: $primary;
        }
        ModeloAmendmentScreen #amend-lead,
        ModeloAmendmentScreen #amend-filed {
            margin-bottom: $cadrumo-stack;
        }
        ModeloAmendmentScreen .amend-label {
            margin-top: $cadrumo-stack;
            text-style: bold;
        }
        ModeloAmendmentScreen .amend-help {
            color: $secondary;
        }
        ModeloAmendmentScreen .amend-row-error,
        ModeloAmendmentScreen #amend-notice {
            color: $warning;
            height: auto;
        }
        ModeloAmendmentScreen #amend-actions {
            height: auto;
            align-horizontal: right;
            margin-top: $cadrumo-stack;
        }
        ModeloAmendmentScreen #amend-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        context: ModeloAmendmentCorrectionContextV1,
        *,
        parse: Callable[[ModeloAmendmentCorrectionRowV1, str, OutputLanguage], WorkbenchParseOutcome],
    ) -> None:
        """Hold the served correction and how a corrected figure is read."""
        super().__init__()
        self._correction = context
        self._parse = parse

    @property
    def context(self) -> ModeloAmendmentCorrectionContextV1:
        """The correction this dialog prepares, as the application served it."""
        return self._correction

    @override
    def compose(self) -> ComposeResult:
        context = self._correction
        filed = context.filed
        with Container(id="amend-backdrop"), VerticalScroll(id="amend-panel"):
            yield localized(
                Static(tr("workspace.modelo.correction.title"), id="amend-title", markup=False),
                "workspace.modelo.correction.title",
            )
            yield localized(
                Static(tr("workspace.modelo.correction.lead"), id="amend-lead", markup=False),
                "workspace.modelo.correction.lead",
            )
            yield Static(
                _FACT_SEPARATOR.join(
                    (filed.modelo_title, filed.period_words, filed.declaration_kind_words, filed.filed_on)
                ),
                id="amend-filed",
                markup=False,
            )
            yield localized(
                Static(tr("tui.modelo.amendment.kind_label"), classes="amend-label", markup=False),
                "tui.modelo.amendment.kind_label",
            )
            yield Select[str](
                tuple((option.words, option.kind.value) for option in context.kinds),
                value=context.kinds[0].kind.value,
                allow_blank=False,
                id="amend-kind",
            )
            yield Static(context.kinds[0].help, id="amend-kind-help", classes="amend-help", markup=False)
            if context.motive_applies:
                yield from self._compose_motive()
            yield Static(context.reason_prompt, classes="amend-label", markup=False)
            yield Input(id="amend-reason", max_length=REASON_MAX_LENGTH)
            yield localized(
                Static(tr("tui.modelo.amendment.values_label"), classes="amend-label", markup=False),
                "tui.modelo.amendment.values_label",
            )
            for index, row in enumerate(context.rows):
                yield Static(_row_heading(row), markup=False)
                if row.help is not None:
                    yield Static(row.help, classes="amend-help", markup=False)
                yield Input(id=f"amend-value-{index}", max_length=MAX_EDIT_LEXEME_LENGTH)
                yield Static("", id=f"amend-error-{index}", classes="amend-row-error", markup=False)
            yield Static("", id="amend-notice", markup=False)
            with Horizontal(id="amend-actions"):
                yield localized(
                    Button(tr("workspace.modelo.editor.cancel"), id="amend-cancel"),
                    "workspace.modelo.editor.cancel",
                )
                yield localized(
                    Button(tr("workspace.modelo.correction.confirm"), id="amend-submit", variant="primary"),
                    "workspace.modelo.correction.confirm",
                )

    def _compose_motive(self) -> ComposeResult:
        context = self._correction
        with Container(id="amend-motive-block"):
            yield localized(
                Static(tr("tui.modelo.amendment.motive_label"), classes="amend-label", markup=False),
                "tui.modelo.amendment.motive_label",
            )
            yield Select[str](
                tuple((option.words, option.motive.value) for option in context.motives),
                id="amend-motive",
            )
            if context.motive_help is not None:
                yield Static(context.motive_help, classes="amend-help", markup=False)

    def on_mount(self) -> None:
        """Start on the kind, showing the motive only for the kind that states one."""
        fit_dialog_width(self, self.app.size.width)
        self._show_motive()
        self.query_one("#amend-kind", Select).focus()

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def _kind(self) -> FilingDeclarationKind:
        value = cast("Select[str]", self.query_one("#amend-kind", Select)).value
        if not isinstance(value, str):
            raise ValueError("a correction kind is always selected")
        return FilingDeclarationKind(value)

    def _asks_motive(self) -> bool:
        context = self._correction
        return context.motive_applies and self._kind() is context.motive_kind

    def _show_motive(self) -> None:
        for block in self.query("#amend-motive-block"):
            block.display = self._asks_motive()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Say what the chosen kind does, and ask the motive only where that kind states one."""
        if event.select.id != "amend-kind":
            return
        kind = self._kind()
        help_text = next(option.help for option in self._correction.kinds if option.kind is kind)
        self.query_one("#amend-kind-help", Static).update(help_text)
        self._show_motive()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Take a figure's refusal away as soon as the filer types it again."""
        control = event.input.id or ""
        if control.startswith("amend-value-"):
            self.query_one(f"#amend-error-{control.removeprefix('amend-value-')}", Static).update("")
        self.query_one("#amend-notice", Static).update("")

    def _motive(self) -> M303RectificativaMotive | None:
        if not self._asks_motive():
            return None
        value = cast("Select[str]", self.query_one("#amend-motive", Select)).value
        return M303RectificativaMotive(value) if isinstance(value, str) else None

    def _overrides(self, language: OutputLanguage) -> tuple[ModeloWorkAmendOverride, ...] | None:
        """Read every corrected figure, marking each refused one; ``None`` when any was refused."""
        overrides: list[ModeloWorkAmendOverride] = []
        refused = False
        for index, row in enumerate(self._correction.rows):
            lexeme = self.query_one(f"#amend-value-{index}", Input).value.strip()
            if not lexeme:
                continue
            error = self.query_one(f"#amend-error-{index}", Static)
            outcome = self._parse(row, lexeme, language)
            override = _override(row, outcome)
            if override is None:
                refused = True
                error.update(
                    outcome.message
                    if isinstance(outcome, WorkbenchRefused)
                    else tr("workspace.modelo.editor.unreadable")
                )
                continue
            error.update("")
            overrides.append(override)
        return None if refused else tuple(overrides)

    def _answer(self) -> ModeloAmendmentAnswerV1 | None:
        notice = self.query_one("#amend-notice", Static)
        overrides = self._overrides(self._correction.language)
        if overrides is None:
            return None
        reason = self.query_one("#amend-reason", Input).value.strip()
        motive = self._motive()
        if not overrides or not reason or (self._asks_motive() and motive is None):
            notice.update(tr("tui.modelo.amendment.incomplete"))
            return None
        return ModeloAmendmentAnswerV1(kind=self._kind(), motive=motive, reason=reason, overrides=overrides)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Prepare the correction, or leave without preparing it."""
        event.stop()
        if event.button.id == "amend-cancel":
            self.dismiss(None)
            return
        answer = self._answer()
        if answer is not None:
            self.dismiss(answer)

    def action_cancel(self) -> None:
        """Leave without preparing a correction."""
        self.dismiss(None)

    async def refresh_language(self) -> None:
        """Reword the dialog's own labels; the served words stay in the language they were read in."""
        refresh_localized_widgets(self)


def _override(row: ModeloAmendmentCorrectionRowV1, outcome: WorkbenchParseOutcome) -> ModeloWorkAmendOverride | None:
    if not isinstance(outcome, WorkbenchParsed) or not isinstance(outcome.value, Decimal):
        return None
    try:
        return ModeloWorkAmendOverride(casilla_id=row.casilla_id, value=format(outcome.value, "f"))
    except ValidationError:
        return None


__all__ = [
    "ModeloAmendmentAnswerV1",
    "ModeloAmendmentScreen",
    "ModeloWorkbenchAmendmentV1",
    "parse_correction_entry",
]
