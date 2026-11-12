"""The statements the form serves, offered from the workbench and staged with the filer's other changes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.work_form_models import ModeloFormCarryAttestation, ModeloWorkForm
from .....application.modelo.work_form_prior_value_models import ModeloFormPriorValueAttestation
from .....core.i18n.render import tr
from .ports import WorkbenchParseOutcome, WorkbenchRefused
from .session import binding_fields
from .statements import FigureParser, StagedFigures, StatedFamily, StatementsChoice, StatementsScreen

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen

_NONE_LOCALE_KEY = "tui.modelo.statements.none"
_NOT_PLACED_LOCALE_KEY = "tui.modelo.statements.not_placed"


class WorkbenchStatementsMixin:
    """Own the statements offer of the modelo workbench."""

    def _served_statements(self: ModeloWorkbenchScreen) -> tuple[ModeloFormCarryAttestation, ...]:
        """Every statement the form serves now, in its order; none where the declaration takes no edit."""
        form = self.form
        if form is None or not self._may_confirm():
            return ()
        return form.carry_attestations

    def _served_prior_values(self: ModeloWorkbenchScreen) -> tuple[ModeloFormPriorValueAttestation, ...]:
        """Every figure the form serves for earlier returns, in its order; none where the declaration takes no edit."""
        form = self.form
        if form is None or not self._may_confirm():
            return ()
        return form.prior_value_attestations

    def offers_statements(self: ModeloWorkbenchScreen) -> bool:
        """Whether the form serves anything the statements dialog lists."""
        return bool(self._served_statements() or self._served_prior_values())

    def action_statements(self: ModeloWorkbenchScreen) -> None:
        """List every statement the form serves, so the filer can stage several of them for one review."""
        if not self._may_confirm():
            self._edit_unavailable()
            return
        served = self._served_statements()
        prior = self._served_prior_values()
        if not served and not prior:
            self._notice(tr(_NONE_LOCALE_KEY))
            return
        staged = frozenset(
            position for position, statement in enumerate(served) if self._session.stages_statement(statement)
        )
        prior_staged = frozenset(
            attestation.family_id for attestation in prior if self._session.stages_prior_withdrawal(attestation)
        )
        self.app.push_screen(
            StatementsScreen(
                served,
                staged=staged,
                status_line=self._status_line(),
                prior_values=prior,
                prior_staged=prior_staged,
                language=self._language,
                figure_labels=self._figure_labels(prior),
                figure_parser=self._figure_parser(),
                figures_staged=self._figures_staged(prior),
            ),
            self._statements_chosen,
        )

    def _figure_labels(
        self: ModeloWorkbenchScreen, prior: tuple[ModeloFormPriorValueAttestation, ...]
    ) -> dict[str, str]:
        """Each carry's own words: its box and label as the form shows it."""
        form = self.form
        labels: dict[str, str] = {}
        for attestation in prior:
            placed = None if form is None else binding_fields(form, (attestation.binding_id,))
            if placed is None:
                continue
            field = placed[0]
            box = f"[{field.box}] " if (field.box is not None and field.box) else ""
            labels[attestation.binding_id] = f"{box}{field.label.text}"
        return labels

    def _figure_parser(self: ModeloWorkbenchScreen) -> FigureParser | None:
        """Read a figure typed for a carry through the application's own grammar; ``None`` when nothing can read it."""
        actions = self._actions
        form = self.form
        if actions is None or form is None:
            return None
        language = self._language

        def parse(binding_id: str, lexeme: str) -> WorkbenchParseOutcome:
            placed = binding_fields(form, (binding_id,))
            if placed is None:
                return WorkbenchRefused(message=tr(_NOT_PLACED_LOCALE_KEY))
            return actions.parse(placed[0], lexeme, language)

        return parse

    def _figures_staged(
        self: ModeloWorkbenchScreen, prior: tuple[ModeloFormPriorValueAttestation, ...]
    ) -> StagedFigures:
        """The figures already staged, by family."""
        families = dict.fromkeys(attestation.family_id for attestation in prior)
        return {family: self._session.prior_figures(family) for family in families}

    def _statements_chosen(self: ModeloWorkbenchScreen, chosen: StatementsChoice | None) -> None:
        """Stage every statement ticked and withdraw every one left unticked, then show the workbench with them."""
        form = self.form
        if chosen is None or form is None:
            return
        refused = False
        for statement in form.carry_attestations:
            if statement in chosen.statements:
                refused = not self._session.stage_statement(form, statement) or refused
            else:
                self._session.withdraw_statement(statement)
        refused = self._stage_prior_withdrawals(form, chosen.withdrawn_families) or refused
        refused = self._stage_prior_figures(form, chosen.stated_families) or refused
        self._refresh_after_staging()
        self._notice(tr(_NOT_PLACED_LOCALE_KEY) if refused else "")

    def _stage_prior_withdrawals(self: ModeloWorkbenchScreen, form: ModeloWorkForm, families: frozenset[str]) -> bool:
        """Stage the withdrawal of each ticked family whole and drop it for each left unticked; ``True`` if refused."""
        refused = False
        seen: set[str] = set()
        for attestation in form.prior_value_attestations:
            if attestation.family_id in seen or attestation.withdrawal is None:
                continue
            seen.add(attestation.family_id)
            if attestation.family_id in families:
                if not self._session.stages_prior_withdrawal(attestation):
                    refused = self._session.stage_prior_withdrawal(form, attestation) is not None or refused
            else:
                self._session.unstage_prior_withdrawal(attestation)
        return refused

    def _stage_prior_figures(
        self: ModeloWorkbenchScreen, form: ModeloWorkForm, stated: tuple[StatedFamily, ...]
    ) -> bool:
        """Stage each family stated whole and drop the figures of each family left unstated; ``True`` if refused."""
        refused = False
        given = {family.family_id: family for family in stated}
        for family_id in dict.fromkeys(attestation.family_id for attestation in form.prior_value_attestations):
            family = given.get(family_id)
            if family is None:
                self._session.unstage_prior_figures(family_id)
                continue
            figures = {item.binding_id: (item.value, item.display) for item in family.figures}
            refused = self._session.stage_prior_figures(form, family_id, figures) is not None or refused
        return refused


__all__ = ["WorkbenchStatementsMixin"]
