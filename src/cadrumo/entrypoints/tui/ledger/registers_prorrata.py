"""The IVA prorrata register in the Ledger workspace.

The screen lists every register entry and differentiated sector the registered
list operation returns, and stages a sector declaration, an election, a
revocation, a carried seed or a sector settlement for review. Every percentage
and definitive figure shown is the operation's own; the screen never derives one.
"""

from __future__ import annotations

from typing import Final, Protocol, override
from uuid import UUID

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.widgets import Static

from ....application.ledger.workspace import LedgerWorkspaceArea
from ....application.prorrata_register.operation_requests import (
    ProrrataDeclareSectorRequest,
    ProrrataElectEspecialRequest,
    ProrrataElectGeneralRequest,
    ProrrataListRequest,
    ProrrataRevokeEspecialRequest,
    ProrrataSeedRequest,
    ProrrataSeedSectorRequest,
    ProrrataSettleSectorRequest,
)
from ....application.prorrata_register.projection_contracts import (
    ProrrataEntryProjection,
    ProrrataListProjection,
    ProrrataMutationProjection,
    ProrrataRefusalProjection,
    ProrrataSectorDefinitionProjection,
)
from ....core.i18n.render import tr
from .controller import LedgerWorkspaceController
from .registers_input import (
    blank_to_none,
    decimal_text,
    parse_public_decimal,
    parse_whole_number,
    request_summary,
    require_text,
)
from .registers_presentation import (
    LedgerRegisterScreen,
    RegisterColumnV1,
    RegisterListV1,
    RegisterOutcomeV1,
    RegisterRow,
    labelled_input,
    labelled_select,
    show_fields,
)
from .tools import LedgerToolV1
from .workspace_screen import LedgerWorkspaceScreen

type ProrrataMutationRequestV1 = (
    ProrrataDeclareSectorRequest
    | ProrrataElectGeneralRequest
    | ProrrataElectEspecialRequest
    | ProrrataRevokeEspecialRequest
    | ProrrataSeedRequest
    | ProrrataSeedSectorRequest
    | ProrrataSettleSectorRequest
)
"""Every prorrata register change, each its own registered operation."""

PRORRATA_TOOL_KEY: Final = "ledger.tool.registers.prorrata"

_MUTATION_TYPES: Final = (
    ProrrataDeclareSectorRequest,
    ProrrataElectGeneralRequest,
    ProrrataElectEspecialRequest,
    ProrrataRevokeEspecialRequest,
    ProrrataSeedRequest,
    ProrrataSeedSectorRequest,
    ProrrataSettleSectorRequest,
)

_SCREEN_LOCALE_KEYS: Final[dict[str, str]] = {
    "title": "tui.ledger.registers.prorrata.title",
    "prompt": "tui.ledger.registers.prorrata.prompt",
    "empty": "tui.ledger.registers.prorrata.empty",
    "tool": "tui.ledger.registers.prorrata.tool",
    "entries": "tui.ledger.registers.prorrata.entries",
    "sectors": "tui.ledger.registers.prorrata.sectors",
}
_ACTION_LOCALE_KEYS: Final[dict[str, str]] = {
    "elect_general": "tui.ledger.registers.prorrata.action.elect_general",
    "elect_especial": "tui.ledger.registers.prorrata.action.elect_especial",
    "revoke_especial": "tui.ledger.registers.prorrata.action.revoke_especial",
    "declare_sector": "tui.ledger.registers.prorrata.action.declare_sector",
    "seed": "tui.ledger.registers.prorrata.action.seed",
    "seed_sector": "tui.ledger.registers.prorrata.action.seed_sector",
    "settle_sector": "tui.ledger.registers.prorrata.action.settle_sector",
}
_DONE_LOCALE_KEYS: Final[dict[str, str]] = {
    "elect_general": "tui.ledger.registers.prorrata.done.elect_general",
    "elect_especial": "tui.ledger.registers.prorrata.done.elect_especial",
    "revoke_especial": "tui.ledger.registers.prorrata.done.revoke_especial",
    "declare_sector": "tui.ledger.registers.prorrata.done.declare_sector",
    "seed": "tui.ledger.registers.prorrata.done.seed",
    "seed_sector": "tui.ledger.registers.prorrata.done.seed_sector",
    "settle_sector": "tui.ledger.registers.prorrata.done.settle_sector",
}
_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    "validation": "tui.ledger.registers.prorrata.refusal.validation",
    "provenance_required": "tui.ledger.registers.prorrata.refusal.provenance_required",
    "provenance_not_electable": "tui.ledger.registers.prorrata.refusal.provenance_not_electable",
    "reference_required": "tui.ledger.registers.prorrata.refusal.reference_required",
    "reference_not_permitted": "tui.ledger.registers.prorrata.refusal.reference_not_permitted",
    "seed_source_absent": "tui.ledger.registers.prorrata.refusal.seed_source_absent",
    "seed_source_blocked": "tui.ledger.registers.prorrata.refusal.seed_source_blocked",
    "seed_existing_blocked": "tui.ledger.registers.prorrata.refusal.seed_existing_blocked",
    "regulated_override_standing": "tui.ledger.registers.prorrata.refusal.regulated_override_standing",
    "sector_prior_definitive_absent": "tui.ledger.registers.prorrata.refusal.sector_prior_definitive_absent",
    "sector_settlement_entry_absent": "tui.ledger.registers.prorrata.refusal.sector_settlement_entry_absent",
}
_FIELD_LOCALE_KEYS: Final[dict[str, str]] = {
    "action": "tui.ledger.registers.prorrata.field.action",
    "ejercicio": "tui.ledger.registers.prorrata.field.ejercicio",
    "sector_id": "tui.ledger.registers.prorrata.field.sector_id",
    "letra": "tui.ledger.registers.prorrata.field.letra",
    "member_activity_codes": "tui.ledger.registers.prorrata.field.member_activity_codes",
    "percentage": "tui.ledger.registers.prorrata.field.percentage",
    "provenance": "tui.ledger.registers.prorrata.field.provenance",
    "reference": "tui.ledger.registers.prorrata.field.reference",
    "evidence_reference": "tui.ledger.registers.prorrata.field.evidence_reference",
    "con_derecho_volume": "tui.ledger.registers.prorrata.field.con_derecho_volume",
    "sin_derecho_volume": "tui.ledger.registers.prorrata.field.sin_derecho_volume",
}
_FIELDS: Final = (
    "prorrata-ejercicio",
    "prorrata-sector",
    "prorrata-letra",
    "prorrata-activities",
    "prorrata-percentage",
    "prorrata-provenance",
    "prorrata-reference",
    "prorrata-evidence",
    "prorrata-con-derecho",
    "prorrata-sin-derecho",
)
_ELECTION_FIELDS: Final = frozenset(
    {"prorrata-ejercicio", "prorrata-sector", "prorrata-percentage", "prorrata-provenance", "prorrata-reference"}
)
_ACTION_FIELDS: Final[dict[str, frozenset[str]]] = {
    "elect_general": _ELECTION_FIELDS,
    "elect_especial": _ELECTION_FIELDS | {"prorrata-evidence"},
    "revoke_especial": _ELECTION_FIELDS | {"prorrata-evidence"},
    "declare_sector": frozenset({"prorrata-sector", "prorrata-letra", "prorrata-activities"}),
    "seed": frozenset({"prorrata-ejercicio"}),
    "seed_sector": frozenset({"prorrata-ejercicio", "prorrata-sector"}),
    "settle_sector": frozenset(
        {"prorrata-ejercicio", "prorrata-sector", "prorrata-con-derecho", "prorrata-sin-derecho"}
    ),
}
_ENTRY_COLUMN_LOCALE_KEYS: Final = (
    RegisterColumnV1("ejercicio", "tui.ledger.registers.prorrata.column.ejercicio", 6),
    RegisterColumnV1("sector", "tui.ledger.registers.prorrata.column.sector", 8),
    RegisterColumnV1("regime", "tui.ledger.registers.prorrata.column.regime", 10),
    RegisterColumnV1("provisional", "tui.ledger.registers.prorrata.column.provisional", 8),
    RegisterColumnV1("definitive", "tui.ledger.registers.prorrata.column.definitive", 8),
    RegisterColumnV1("provenance", "tui.ledger.registers.prorrata.column.provenance", 10),
)
_SECTOR_COLUMN_LOCALE_KEYS: Final = (
    RegisterColumnV1("sector", "tui.ledger.registers.prorrata.column.sector", 10),
    RegisterColumnV1("letra", "tui.ledger.registers.prorrata.column.letra", 6),
    RegisterColumnV1("activities", "tui.ledger.registers.prorrata.column.activities", 20),
)


class LedgerProrrataRegisterDoorV1(Protocol):
    """Injected door to the registered prorrata register operations of one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def read_register(self, request: ProrrataListRequest) -> ProrrataListProjection:
        """Read every register entry and sector through ``ledger.prorrata.list``."""
        ...

    async def apply(self, request: ProrrataMutationRequestV1) -> ProrrataMutationProjection:
        """Submit one register change; a registered refusal is returned, not raised."""
        ...


def prorrata_entry_key(ejercicio: int, sector_id: str | None) -> str:
    """The register's own identity of one entry: its exercise and its sector, if any."""
    return f"{ejercicio}|{sector_id or ''}"


def _entry_line(entry: ProrrataEntryProjection) -> str:
    return tr(
        "tui.ledger.registers.prorrata.result.entry",
        ejercicio=entry.ejercicio,
        sector=entry.sector_id or tr("tui.ledger.registers.prorrata.whole_entity"),
        regime=entry.regime,
        provisional=decimal_text(entry.provisional_percentage),
        definitive=decimal_text(entry.definitive_percentage),
    )


def _sector_line(sector: ProrrataSectorDefinitionProjection) -> str:
    return tr(
        "tui.ledger.registers.prorrata.result.sector",
        sector=sector.sector_id,
        letra=sector.letra,
        activities=", ".join(sector.member_activity_codes) or "-",
    )


def prorrata_refusal_text(refusal: ProrrataRefusalProjection) -> str:
    """The operation's own refusal: its reason in words, then the detail and findings it carried."""
    lines = [tr(_REFUSAL_LOCALE_KEYS[refusal.reason]), refusal.detail]
    lines.extend(f"[{finding.code}] {finding.message}" for finding in refusal.findings if finding.blocking)
    if refusal.accepted_provenances:
        lines.append(
            tr("tui.ledger.registers.prorrata.accepted_provenances", values=", ".join(refusal.accepted_provenances))
        )
    return "\n".join(line for line in lines if line)


def prorrata_outcome(result: ProrrataMutationProjection) -> RegisterOutcomeV1:
    """Describe one settled change exactly as the operation reported it."""
    if result.refusal is not None:
        return RegisterOutcomeV1(refusal=prorrata_refusal_text(result.refusal))
    lines = [tr(_DONE_LOCALE_KEYS[result.operation_id])]
    if result.entry is not None:
        lines.append(_entry_line(result.entry))
    if result.sector_definition is not None:
        lines.append(_sector_line(result.sector_definition))
    if result.seed_source is not None:
        source = result.seed_source
        lines.append(
            tr(
                "tui.ledger.registers.prorrata.result.seed_source",
                modelo=source.modelo,
                year=source.filing_year,
                period=source.period,
            )
        )
    if result.prior_ejercicio is not None:
        lines.append(tr("tui.ledger.registers.prorrata.result.prior", ejercicio=result.prior_ejercicio))
    lines.extend(
        tr("tui.ledger.registers.prorrata.result.finding", code=finding.code, message=finding.message)
        for finding in result.findings
    )
    return RegisterOutcomeV1(lines=tuple(lines))


class LedgerProrrataRegisterScreen(LedgerRegisterScreen):
    """List the prorrata register and stage each registered change to it for review."""

    TITLE_LOCALE_KEY = _SCREEN_LOCALE_KEYS["title"]
    PROMPT_LOCALE_KEY = _SCREEN_LOCALE_KEYS["prompt"]
    EMPTY_LOCALE_KEY = _SCREEN_LOCALE_KEYS["empty"]

    def __init__(self, controller: LedgerWorkspaceController, door: LedgerProrrataRegisterDoorV1) -> None:
        """Keep the injected profile-bound door for every request this screen submits."""
        super().__init__(controller, id="ledger-prorrata-register-screen")
        self.door = door
        self.entries: tuple[ProrrataEntryProjection, ...] = ()
        self.sectors: tuple[ProrrataSectorDefinitionProjection, ...] = ()

    @override
    def register_lists(self) -> tuple[RegisterListV1, ...]:
        return (
            RegisterListV1(
                "prorrata-entries", _SCREEN_LOCALE_KEYS["entries"], _ENTRY_COLUMN_LOCALE_KEYS, self._entry_rows
            ),
            RegisterListV1(
                "prorrata-sectors",
                _SCREEN_LOCALE_KEYS["sectors"],
                _SECTOR_COLUMN_LOCALE_KEYS,
                self._sector_rows,
            ),
        )

    def _entry_rows(self) -> tuple[RegisterRow, ...]:
        return tuple(
            (
                prorrata_entry_key(entry.ejercicio, entry.sector_id),
                (
                    str(entry.ejercicio),
                    entry.sector_id or "-",
                    entry.regime,
                    decimal_text(entry.provisional_percentage),
                    decimal_text(entry.definitive_percentage),
                    entry.provisional_provenance or "-",
                ),
            )
            for entry in self.entries
        )

    def _sector_rows(self) -> tuple[RegisterRow, ...]:
        return tuple(
            (sector.sector_id, (sector.sector_id, sector.letra, ", ".join(sector.member_activity_codes) or "-"))
            for sector in self.sectors
        )

    @override
    def choice_options(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"prorrata-action": tuple((tr(key), action) for action, key in _ACTION_LOCALE_KEYS.items())}

    @override
    def compose_form(self) -> ComposeResult:
        yield from labelled_select(
            _FIELD_LOCALE_KEYS["action"], "prorrata-action", self.choice_options()["prorrata-action"]
        )
        yield from labelled_input(_FIELD_LOCALE_KEYS["ejercicio"], "prorrata-ejercicio")
        yield from labelled_input(_FIELD_LOCALE_KEYS["sector_id"], "prorrata-sector")
        yield from labelled_input(_FIELD_LOCALE_KEYS["letra"], "prorrata-letra")
        yield from labelled_input(_FIELD_LOCALE_KEYS["member_activity_codes"], "prorrata-activities")
        yield from labelled_input(_FIELD_LOCALE_KEYS["percentage"], "prorrata-percentage")
        yield from labelled_input(_FIELD_LOCALE_KEYS["provenance"], "prorrata-provenance")
        yield from labelled_input(_FIELD_LOCALE_KEYS["reference"], "prorrata-reference")
        yield from labelled_input(_FIELD_LOCALE_KEYS["evidence_reference"], "prorrata-evidence")
        yield from labelled_input(_FIELD_LOCALE_KEYS["con_derecho_volume"], "prorrata-con-derecho")
        yield from labelled_input(_FIELD_LOCALE_KEYS["sin_derecho_volume"], "prorrata-sin-derecho")

    @override
    def form_mounted(self) -> None:
        self._show_action_fields()

    def on_select_changed(self) -> None:
        """Show only the fields the chosen change takes."""
        self._show_action_fields()

    def _show_action_fields(self) -> None:
        show_fields(self, _FIELDS, _ACTION_FIELDS[self.select_value("#prorrata-action")])

    @override
    def form_controls(self) -> tuple[str, ...]:
        return ("#prorrata-action", *(f"#{field}" for field in _FIELDS))

    @override
    async def read_register(self) -> None:
        result = await self.door.read_register(ProrrataListRequest(profile_id=self.door.profile_id))
        self.entries = result.entries
        self.sectors = result.sectors

    @override
    def clear_register(self) -> None:
        self.entries = ()
        self.sectors = ()

    @override
    def choose_row(self, table_id: str, key: str) -> None:
        if table_id == "prorrata-sectors":
            self._choose_sector(key)
            return
        entry = next(item for item in self.entries if prorrata_entry_key(item.ejercicio, item.sector_id) == key)
        self.set_input("#prorrata-ejercicio", str(entry.ejercicio))
        self.set_input("#prorrata-sector", entry.sector_id or "")
        percentage = entry.provisional_percentage
        self.set_input("#prorrata-percentage", "" if percentage is None else percentage.decimal)
        self.set_input("#prorrata-provenance", entry.provisional_provenance or "")
        self.set_input("#prorrata-reference", entry.authorisation_reference or "")
        transition = entry.especial_transition
        self.set_input("#prorrata-evidence", transition.evidence_reference if transition is not None else "")
        self.query_one("#register-detail", Static).update(_entry_line(entry))

    def _choose_sector(self, key: str) -> None:
        sector = next(item for item in self.sectors if item.sector_id == key)
        self.set_input("#prorrata-sector", sector.sector_id)
        self.set_input("#prorrata-letra", sector.letra)
        self.set_input("#prorrata-activities", ", ".join(sector.member_activity_codes))
        self.query_one("#register-detail", Static).update(_sector_line(sector))

    def _request(self, action: str) -> ProrrataMutationRequestV1:
        """Build the chosen change's own request from the visible fields only."""
        profile_id = self.door.profile_id
        if action == "declare_sector":
            codes = tuple(code.strip() for code in self.input_value("#prorrata-activities").split(",") if code.strip())
            return ProrrataDeclareSectorRequest(
                profile_id=profile_id,
                sector_id=require_text(self.input_value("#prorrata-sector"), field_key=_FIELD_LOCALE_KEYS["sector_id"]),
                letra=require_text(self.input_value("#prorrata-letra"), field_key=_FIELD_LOCALE_KEYS["letra"]),
                member_activity_codes=codes,
            )
        ejercicio = parse_whole_number(
            self.input_value("#prorrata-ejercicio"), field_key=_FIELD_LOCALE_KEYS["ejercicio"]
        )
        if action == "seed":
            return ProrrataSeedRequest(profile_id=profile_id, ejercicio=ejercicio)
        sector = blank_to_none(self.input_value("#prorrata-sector"))
        if action == "seed_sector":
            return ProrrataSeedSectorRequest(
                profile_id=profile_id,
                ejercicio=ejercicio,
                sector_id=require_text(self.input_value("#prorrata-sector"), field_key=_FIELD_LOCALE_KEYS["sector_id"]),
            )
        if action == "settle_sector":
            return ProrrataSettleSectorRequest(
                profile_id=profile_id,
                ejercicio=ejercicio,
                sector_id=require_text(self.input_value("#prorrata-sector"), field_key=_FIELD_LOCALE_KEYS["sector_id"]),
                con_derecho_volume=parse_public_decimal(
                    self.input_value("#prorrata-con-derecho"),
                    field_key=_FIELD_LOCALE_KEYS["con_derecho_volume"],
                    signed=False,
                ),
                sin_derecho_volume=parse_public_decimal(
                    self.input_value("#prorrata-sin-derecho"),
                    field_key=_FIELD_LOCALE_KEYS["sin_derecho_volume"],
                    signed=False,
                ),
            )
        election: dict[str, object] = {
            "profile_id": profile_id,
            "ejercicio": ejercicio,
            "percentage": parse_public_decimal(
                self.input_value("#prorrata-percentage"), field_key=_FIELD_LOCALE_KEYS["percentage"], signed=False
            ),
            "provenance": blank_to_none(self.input_value("#prorrata-provenance")),
            "reference": blank_to_none(self.input_value("#prorrata-reference")),
            "sector_id": sector,
        }
        evidence = blank_to_none(self.input_value("#prorrata-evidence"))
        if action == "elect_general":
            return ProrrataElectGeneralRequest.model_validate(election)
        if action == "elect_especial":
            return ProrrataElectEspecialRequest.model_validate({**election, "evidence_reference": evidence})
        return ProrrataRevokeEspecialRequest.model_validate(
            {
                **election,
                "evidence_reference": require_text(
                    self.input_value("#prorrata-evidence"), field_key=_FIELD_LOCALE_KEYS["evidence_reference"]
                ),
            }
        )

    @override
    async def stage(self) -> tuple[BaseModel, str]:
        action = self.select_value("#prorrata-action")
        request = self._request(action)
        heading = tr(_ACTION_LOCALE_KEYS[action])
        return request, f"{heading}\n{request_summary(request, field_keys=_FIELD_LOCALE_KEYS)}"

    @override
    async def send(self, request: BaseModel) -> RegisterOutcomeV1:
        if not isinstance(request, _MUTATION_TYPES):
            raise TypeError("the prorrata register submits only its own change requests")
        result = await self.door.apply(request)
        if result.entry is not None:
            self.selected_key = prorrata_entry_key(result.entry.ejercicio, result.entry.sector_id)
        elif result.sector_definition is not None:
            self.selected_key = result.sector_definition.sector_id
        return prorrata_outcome(result)


def prorrata_register_tool(door: LedgerProrrataRegisterDoorV1) -> LedgerToolV1:
    """Offer the prorrata register from the Records overview."""

    def build(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerProrrataRegisterScreen(controller, door)

    return LedgerToolV1(
        key=PRORRATA_TOOL_KEY,
        label_key=_SCREEN_LOCALE_KEYS["tool"],
        area=LedgerWorkspaceArea.OVERVIEW,
        build=build,
    )


__all__ = [
    "PRORRATA_TOOL_KEY",
    "LedgerProrrataRegisterDoorV1",
    "LedgerProrrataRegisterScreen",
    "ProrrataMutationRequestV1",
    "prorrata_entry_key",
    "prorrata_outcome",
    "prorrata_refusal_text",
    "prorrata_register_tool",
]
