"""Look up, confirm and withdraw what is known about one counterparty's establishment.

A lookup shows how the ladder settles the counterparty's territorial scope and
identification state, and any contradiction it withholds. A confirmation
records the operator's own assertion of one or both of those facts; a
withdrawal removes a recorded assertion and asks once more before it is sent.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from typing import override

from textual.widget import Widget
from textual.widgets import Input, Static

from ....application.ledger.counterparty_operation import (
    CounterpartyResolutionProjection,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ....core.i18n.render import tr
from .categorisation_common import (
    CategorisationScreen,
    StagedChangeV1,
    action,
    action_row,
    blank_to_none,
    field,
    heading,
    line,
)
from .categorisation_doors import LedgerCounterpartyDoorV1
from .controller import LedgerWorkspaceController


def _resolution_text(identifier: str, resolution: CounterpartyResolutionProjection) -> str:
    lines = [
        tr(
            "tui.ledger.categorisation.counterparty.scope",
            identifier=identifier,
            scope=resolution.territorial_scope or "-",
            source=resolution.territorial_source or "-",
        ),
        tr(
            "tui.ledger.categorisation.counterparty.state",
            state=resolution.identification_state or "-",
            source=resolution.identification_source or "-",
        ),
    ]
    if resolution.contradiction_detail is not None:
        lines.append(
            tr(
                "tui.ledger.categorisation.counterparty.contradiction",
                confirmed=resolution.confirmed_scope or "-",
                evidenced=resolution.evidenced_scope or "-",
                detail=resolution.contradiction_detail,
            )
        )
    return "\n".join(lines)


def _confirmation_text(result: LedgerCounterpartyResult) -> str:
    facts = result.facts
    return tr(
        "tui.ledger.categorisation.counterparty.confirmed"
        if result.changed
        else "tui.ledger.categorisation.counterparty.unchanged",
        identifier=result.tax_identifier,
        scope="-" if facts is None else facts.territorial_scope or "-",
        state="-" if facts is None else facts.identification_state or "-",
    )


def counterparty_outcome_text(result: LedgerCounterpartyResult) -> str:
    """Say what one counterparty request found or changed."""
    if result.action == "view":
        resolution = result.resolution
        if resolution is None:
            return tr("tui.ledger.categorisation.counterparty.nothing_known", identifier=result.tax_identifier)
        return _resolution_text(result.tax_identifier, resolution)
    if result.action == "withdraw":
        return tr(
            "tui.ledger.categorisation.counterparty.withdrawn"
            if result.withdrawn is True
            else "tui.ledger.categorisation.counterparty.nothing_to_withdraw",
            identifier=result.tax_identifier,
        )
    if result.conflict_context is not None:
        detail = ", ".join(f"{name}: {value}" for name, value in result.conflict_context)
        return tr("tui.ledger.categorisation.counterparty.conflict", identifier=result.tax_identifier, detail=detail)
    return _confirmation_text(result)


class LedgerCounterpartiesScreen(CategorisationScreen):
    """Look up, confirm or withdraw the establishment facts of one counterparty."""

    @override
    def banner(self) -> Static:
        return line("tui.ledger.categorisation.counterparty.title", classes="cadrumo-banner")

    @override
    def prompt(self) -> Static:
        return line("tui.ledger.categorisation.counterparty.prompt")

    def __init__(self, controller: LedgerWorkspaceController, *, door: LedgerCounterpartyDoorV1) -> None:
        """Keep the profile-bound counterparty door."""
        super().__init__(controller, id="ledger-categorisation-counterparties-screen")
        self.door = door

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield heading("tui.ledger.categorisation.counterparty.who_heading")
        yield field("tui.ledger.categorisation.counterparty.identifier", id="categorisation-counterparty-identifier")
        yield field(
            "tui.ledger.categorisation.counterparty.country", id="categorisation-counterparty-country", max_length=2
        )
        yield field("tui.ledger.categorisation.counterparty.evidenced", id="categorisation-counterparty-evidenced")
        yield action_row(
            action("tui.ledger.categorisation.counterparty.view", id="categorisation-counterparty-view"),
            action("tui.ledger.categorisation.counterparty.review_withdraw", id="categorisation-counterparty-withdraw"),
        )
        yield heading("tui.ledger.categorisation.counterparty.confirm_heading")
        yield field("tui.ledger.categorisation.counterparty.territorial", id="categorisation-counterparty-scope")
        yield field(
            "tui.ledger.categorisation.counterparty.identification",
            id="categorisation-counterparty-state",
            max_length=2,
        )
        yield field("tui.ledger.categorisation.counterparty.note", id="categorisation-counterparty-note")
        yield field("tui.ledger.categorisation.counterparty.asserted_by", id="categorisation-counterparty-asserted")
        yield action_row(
            action("tui.ledger.categorisation.counterparty.review_confirm", id="categorisation-counterparty-confirm")
        )

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return (
            "#categorisation-counterparty-identifier",
            "#categorisation-counterparty-country",
            "#categorisation-counterparty-evidenced",
            "#categorisation-counterparty-view",
            "#categorisation-counterparty-withdraw",
            "#categorisation-counterparty-scope",
            "#categorisation-counterparty-state",
            "#categorisation-counterparty-note",
            "#categorisation-counterparty-asserted",
            "#categorisation-counterparty-confirm",
        )

    def _value(self, selector: str) -> str | None:
        return blank_to_none(self.query_one(selector, Input).value)

    def _identity(self) -> dict[str, object]:
        identifier = self._value("#categorisation-counterparty-identifier")
        if identifier is None:
            raise ValueError(tr("tui.ledger.categorisation.counterparty.identifier_required"))
        country = self._value("#categorisation-counterparty-country")
        return {
            "profile_id": self.door.profile_id,
            "tax_identifier": identifier,
            "country_code": None if country is None else country.upper(),
        }

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id == "categorisation-counterparty-view":
            try:
                request = LedgerCounterpartyRequest.model_validate(
                    {
                        **self._identity(),
                        "action": "view",
                        "evidenced_scope": self._value("#categorisation-counterparty-evidenced"),
                    }
                )
            except ValueError as error:
                self.refuse_error(error)
                return
            self.run_read(lambda: self._view(request))
        elif button_id == "categorisation-counterparty-withdraw":
            self.stage_from(self._stage_withdraw)
        elif button_id == "categorisation-counterparty-confirm":
            self.stage_from(self._stage_confirm)

    async def _view(self, request: LedgerCounterpartyRequest) -> None:
        result = await self.door(request)
        self.show_outcome(lambda: counterparty_outcome_text(result))

    def _writer(self, request: LedgerCounterpartyRequest) -> Callable[[], Awaitable[bool]]:
        async def write() -> bool:
            result = await self.door(request)
            self.show_outcome(lambda: counterparty_outcome_text(result))
            return result.changed

        return write

    def _stage_withdraw(self) -> StagedChangeV1:
        request = LedgerCounterpartyRequest.model_validate({**self._identity(), "action": "withdraw"})
        return StagedChangeV1(
            summary=lambda: tr(
                "tui.ledger.categorisation.counterparty.stage_withdraw", identifier=request.tax_identifier
            ),
            write=self._writer(request),
            destructive=True,
        )

    def _stage_confirm(self) -> StagedChangeV1:
        state = self._value("#categorisation-counterparty-state")
        request = LedgerCounterpartyRequest.model_validate(
            {
                **self._identity(),
                "action": "confirm",
                "territorial_scope": self._value("#categorisation-counterparty-scope"),
                "identification_state": None if state is None else state.upper(),
                "note": self.query_one("#categorisation-counterparty-note", Input).value.strip(),
                "asserted_by": self._value("#categorisation-counterparty-asserted"),
            }
        )
        return StagedChangeV1(
            summary=lambda: tr(
                "tui.ledger.categorisation.counterparty.stage_confirm",
                identifier=request.tax_identifier,
                scope=request.territorial_scope or "-",
                state=request.identification_state or "-",
            ),
            write=self._writer(request),
        )


__all__ = ["LedgerCounterpartiesScreen", "counterparty_outcome_text"]
