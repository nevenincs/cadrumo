"""Look up, confirm and withdraw what is known about one counterparty's establishment.

A lookup shows how the ladder settles the counterparty's territorial scope and
identification state, and any contradiction it withholds, and the filing name
stated for it with who stated it. It also shows every export field the pinned
authority files a party name into, by width and edition, with whether the
stated name fills it, and the longest each part can be to fit whole. A
confirmation records the operator's own assertion of one or both of those
facts; a withdrawal removes the whole record, every answer stated for the
counterparty, and asks once more before it is sent. A filing-name statement
sends the kind, the name parts and any width-scoped shorter renderings through
the registered operation; the operation's own words say what it refuses or
flags.

Opened from a served way out, the tool starts on the counterparty, country and
kind the way out bound, and looks the counterparty up at once when it is named.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from typing import Final, cast, override

from textual.widget import Widget
from textual.widgets import Checkbox, Input, Select, Static

from ....application.ledger.counterparty_filing_name_slots import (
    CounterpartyFilingNamePartLimit,
    CounterpartyFilingNameSlot,
)
from ....application.ledger.counterparty_operation import (
    CounterpartyFilingNameProjection,
    CounterpartyResolutionProjection,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ....application.operator_actions.projection import ActionArgumentSnapshot
from ....core.i18n.render import tr
from ....core.operator_action_enums import ActionArgumentStatus
from ....domain.filing.declared_party_name import DeclaredPartyKind
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

_KIND_LOCALE_KEYS: Final[dict[str, str]] = {
    DeclaredPartyKind.NATURAL_PERSON.value: "tui.ledger.categorisation.counterparty.filing_kind_natural_person",
    DeclaredPartyKind.ENTITY.value: "tui.ledger.categorisation.counterparty.filing_kind_entity",
}
_SLOT_STATE_LOCALE_KEYS: Final[dict[str, str]] = {
    "fits": "tui.ledger.categorisation.counterparty.filing_slot_fits",
    "uses_rendering": "tui.ledger.categorisation.counterparty.filing_slot_uses_rendering",
    "missing": "tui.ledger.categorisation.counterparty.filing_slot_missing",
    "single_surname": "tui.ledger.categorisation.counterparty.filing_slot_single_surname",
    "too_wide": "tui.ledger.categorisation.counterparty.filing_slot_too_wide",
}
_PART_LOCALE_KEYS: Final[dict[str, str]] = {
    "primer_apellido": "tui.ledger.categorisation.counterparty.filing_primer",
    "segundo_apellido": "tui.ledger.categorisation.counterparty.filing_segundo",
    "nombre": "tui.ledger.categorisation.counterparty.filing_nombre",
    "razon_social": "tui.ledger.categorisation.counterparty.filing_razon",
}
_RENDERING_SEPARATOR: Final = ";"
_RENDERING_ASSIGN: Final = "="
_FILING_INPUTS: Final = (
    "#categorisation-filing-primer",
    "#categorisation-filing-segundo",
    "#categorisation-filing-nombre",
    "#categorisation-filing-razon",
    "#categorisation-filing-renderings",
)


def _bound(prefill: tuple[ActionArgumentSnapshot, ...], name: str) -> str | None:
    """The text a way out resolved for argument ``name``, or ``None`` when it left it to the operator."""
    for binding in prefill:
        if binding.argument_name == name and binding.status is ActionArgumentStatus.RESOLVED:
            value = binding.value
            if isinstance(value, str) and value.strip():
                return value
    return None


def _kind_label(kind: str) -> str:
    key = _KIND_LOCALE_KEYS.get(kind)
    return kind if key is None else tr(key)


def _name_parts_text(name: CounterpartyFilingNameProjection) -> str:
    parts: list[str] = []
    if name.primer_apellido is not None:
        parts.append(f"{tr('tui.ledger.categorisation.counterparty.filing_primer')}: {name.primer_apellido}")
    if name.segundo_apellido is not None:
        parts.append(f"{tr('tui.ledger.categorisation.counterparty.filing_segundo')}: {name.segundo_apellido}")
    elif name.no_second_surname:
        parts.append(tr("tui.ledger.categorisation.counterparty.filing_no_second"))
    if name.nombre is not None:
        parts.append(f"{tr('tui.ledger.categorisation.counterparty.filing_nombre')}: {name.nombre}")
    if name.razon_social is not None:
        parts.append(f"{tr('tui.ledger.categorisation.counterparty.filing_razon')}: {name.razon_social}")
    return " · ".join(parts)


def _slot_state(slot: CounterpartyFilingNameSlot) -> str:
    if slot.refusal is not None:
        return slot.refusal
    return "uses_rendering" if slot.uses_rendering else "fits"


def _slot_lines(slots: tuple[CounterpartyFilingNameSlot, ...]) -> list[str]:
    """One line per served width and outcome, naming each served edition once, in served order."""
    groups: dict[tuple[int, str], list[str]] = {}
    for slot in slots:
        editions = groups.setdefault((slot.width, _slot_state(slot)), [])
        if slot.edition_words not in editions:
            editions.append(slot.edition_words)
    return [
        tr(
            "tui.ledger.categorisation.counterparty.filing_slot",
            width=width,
            state=tr(_SLOT_STATE_LOCALE_KEYS[state]),
            editions="; ".join(editions),
        )
        for (width, state), editions in groups.items()
    ]


def _part_limit_lines(limits: tuple[CounterpartyFilingNamePartLimit, ...]) -> list[str]:
    return [
        tr(
            "tui.ledger.categorisation.counterparty.filing_part_limit",
            part=tr(_PART_LOCALE_KEYS[limit.part]),
            count=limit.max_length,
        )
        for limit in limits
    ]


def _filing_name_text(result: LedgerCounterpartyResult) -> str:
    """The stated filing name, who stated it, its renderings, the served slots and limits and the findings."""
    name = result.filing_name
    if name is None:
        lines = [tr("tui.ledger.categorisation.counterparty.filing_unstated", identifier=result.tax_identifier)]
    else:
        lines = [
            tr(
                "tui.ledger.categorisation.counterparty.filing_stated",
                identifier=result.tax_identifier,
                kind=_kind_label(name.party_kind),
                name=_name_parts_text(name),
            ),
            tr(
                "tui.ledger.categorisation.counterparty.filing_stated_by",
                name=name.asserted_by,
                date=name.asserted_at.date().isoformat(),
            ),
            *(
                tr("tui.ledger.categorisation.counterparty.filing_rendering", width=item.width, text=item.text)
                for item in name.renderings
            ),
        ]
    lines.extend(finding.words for finding in result.findings if finding.words is not None)
    if result.filing_name_slots:
        lines.append(tr("tui.ledger.categorisation.counterparty.filing_slots_heading"))
        lines.extend(_slot_lines(result.filing_name_slots))
    lines.extend(_part_limit_lines(result.filing_name_part_limits))
    return "\n".join(lines)


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
        return "\n".join((_resolution_text(result.tax_identifier, resolution), _filing_name_text(result)))
    if result.action == "filing_name":
        done = tr(
            "tui.ledger.categorisation.counterparty.filing_done"
            if result.changed
            else "tui.ledger.categorisation.counterparty.filing_unchanged",
            identifier=result.tax_identifier,
        )
        return "\n".join((done, _filing_name_text(result)))
    if result.action == "withdraw":
        return tr(
            "tui.ledger.categorisation.counterparty.withdrawn_everything"
            if result.withdrawn is True
            else "tui.ledger.categorisation.counterparty.nothing_stated_to_withdraw",
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

    @property
    def _prefill(self) -> tuple[ActionArgumentSnapshot, ...]:
        """The arguments the way out this tool was opened from served; none when no way out opened it."""
        return self.controller.context.request_prefill if self.opened_for_way_out else ()

    @override
    def compose_body(self) -> Iterator[Widget]:
        if self.opened_for_way_out:
            yield line("tui.ledger.categorisation.counterparty.filing_asked", id="categorisation-counterparty-asked")
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
        yield heading("tui.ledger.categorisation.counterparty.filing_heading")
        yield Select[str](
            tuple((_kind_label(kind), kind) for kind in _KIND_LOCALE_KEYS),
            value=DeclaredPartyKind.NATURAL_PERSON.value,
            allow_blank=False,
            id="categorisation-filing-kind",
        )
        yield field("tui.ledger.categorisation.counterparty.filing_primer", id="categorisation-filing-primer")
        yield field("tui.ledger.categorisation.counterparty.filing_segundo", id="categorisation-filing-segundo")
        yield Checkbox(
            tr("tui.ledger.categorisation.counterparty.filing_no_second"), id="categorisation-filing-no-second"
        )
        yield field("tui.ledger.categorisation.counterparty.filing_nombre", id="categorisation-filing-nombre")
        yield field("tui.ledger.categorisation.counterparty.filing_razon", id="categorisation-filing-razon")
        yield field("tui.ledger.categorisation.counterparty.filing_renderings", id="categorisation-filing-renderings")
        yield action_row(
            action("tui.ledger.categorisation.counterparty.filing_review", id="categorisation-counterparty-filing")
        )

    @override
    def mount_body(self) -> None:
        """Start on what a way out bound, and look the counterparty up at once when it named one."""
        prefill = self._prefill
        identifier = _bound(prefill, "tax_identifier")
        country = _bound(prefill, "country_code")
        kind = _bound(prefill, "kind")
        if identifier is not None:
            self.query_one("#categorisation-counterparty-identifier", Input).value = identifier
        if country is not None:
            self.query_one("#categorisation-counterparty-country", Input).value = country
        if kind in _KIND_LOCALE_KEYS:
            self.query_one("#categorisation-filing-kind", Select).value = kind
        if identifier is not None:
            self.on_tool_button("categorisation-counterparty-view")
        else:
            self.query_one("#categorisation-counterparty-identifier", Input).focus()

    @override
    async def refresh_language(self) -> None:
        """Reword the kind choices and the checkbox, which hold their words themselves."""
        await super().refresh_language()
        if not self.available:
            return
        kind = self.query_one("#categorisation-filing-kind", Select)
        kind.set_options(tuple((_kind_label(item), item) for item in _KIND_LOCALE_KEYS))
        self.query_one("#categorisation-filing-no-second", Checkbox).label = tr(
            "tui.ledger.categorisation.counterparty.filing_no_second"
        )

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return (
            "#categorisation-filing-kind",
            "#categorisation-filing-no-second",
            "#categorisation-counterparty-filing",
            *_FILING_INPUTS,
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
        elif button_id == "categorisation-counterparty-filing":
            self.stage_from(self._stage_filing_name)

    async def _view(self, request: LedgerCounterpartyRequest) -> None:
        result = await self.door(request)
        self.show_outcome(lambda: counterparty_outcome_text(result))
        self._fill_filing_name(result.filing_name)

    def _fill_filing_name(self, name: CounterpartyFilingNameProjection | None) -> None:
        """Offer the stated name for editing; nothing is changed when none is stated."""
        if name is None:
            return
        if name.party_kind in _KIND_LOCALE_KEYS:
            self.query_one("#categorisation-filing-kind", Select).value = name.party_kind
        shorter = f"{_RENDERING_SEPARATOR} ".join(
            f"{item.width}{_RENDERING_ASSIGN}{item.text}" for item in name.renderings
        )
        for selector, value in (
            ("#categorisation-filing-primer", name.primer_apellido),
            ("#categorisation-filing-segundo", name.segundo_apellido),
            ("#categorisation-filing-nombre", name.nombre),
            ("#categorisation-filing-razon", name.razon_social),
            ("#categorisation-filing-renderings", shorter),
        ):
            self.query_one(selector, Input).value = value or ""
        self.query_one("#categorisation-filing-no-second", Checkbox).value = name.no_second_surname

    def _renderings(self) -> tuple[dict[str, object], ...]:
        """Read ``width=text`` entries; the operation checks the widths and texts themselves."""
        raw = self.query_one("#categorisation-filing-renderings", Input).value
        renderings: list[dict[str, object]] = []
        for entry in raw.split(_RENDERING_SEPARATOR):
            if not entry.strip():
                continue
            width, assign, text = entry.partition(_RENDERING_ASSIGN)
            if not assign or not width.strip().isdecimal() or not text.strip():
                raise ValueError(tr("tui.ledger.categorisation.counterparty.filing_renderings_malformed"))
            renderings.append({"width": int(width), "text": text.strip()})
        return tuple(renderings)

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
                "tui.ledger.categorisation.counterparty.stage_withdraw_everything", identifier=request.tax_identifier
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

    def _stage_filing_name(self) -> StagedChangeV1:
        kind = str(cast("Select[str]", self.query_one("#categorisation-filing-kind", Select)).value)
        request = LedgerCounterpartyRequest.model_validate(
            {
                **self._identity(),
                "action": "filing_name",
                "party_kind": kind,
                "primer_apellido": self._value("#categorisation-filing-primer"),
                "segundo_apellido": self._value("#categorisation-filing-segundo"),
                "no_second_surname": self.query_one("#categorisation-filing-no-second", Checkbox).value,
                "nombre": self._value("#categorisation-filing-nombre"),
                "razon_social": self._value("#categorisation-filing-razon"),
                "renderings": self._renderings(),
                "asserted_by": self._value("#categorisation-counterparty-asserted"),
            }
        )
        return StagedChangeV1(
            summary=lambda: tr(
                "tui.ledger.categorisation.counterparty.filing_stage",
                identifier=request.tax_identifier,
                kind=_kind_label(kind),
            ),
            write=self._writer(request),
        )


__all__ = ["LedgerCounterpartiesScreen", "counterparty_outcome_text"]
