"""Pickers over the served entry-option families a ledger row is linked to a profile row by.

The ledger entry-options read serves, for the exact profile, each lease and each
property as a choice valued by the reference a ledger row stores and worded by
the row's served summary, and the expense concepts each worded under its served
catalogue key. A picker offers exactly those choices and yields the served value
chosen, never a position, and the operation that takes it refuses one that does
not apply. Left unchosen, a picker sends nothing, so the row keeps what it holds.

A row's transaction read serves the links it holds, so a picker for an existing
row starts at the choice that read names and shows that choice's served words; a
link the options do not offer, or a row whose read fails, starts a picker unchosen
rather than guessing what the row holds.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import ClassVar, Final, Protocol, override

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Select, Static

from ....application.ledger.entry_options_operation import (
    EntryOptionFamily,
    LedgerEntryOptionFamilyProjection,
    LedgerEntryOptionProjection,
    LedgerEntryOptionsProjection,
)
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....core.i18n.render import tr
from ..components.language import localized
from ..components.theme import tokenised

LINK_FAMILY_BY_FIELD: Final[Mapping[str, EntryOptionFamily]] = MappingProxyType(
    {
        "arrendamiento_ref": "rental_lease",
        "inmueble_ref": "rental_property",
        "gasto_capital_inmobiliario": "gasto_capital_inmobiliario",
    }
)
"""Each ledger field a link is stated in, and the served family its choices come from, in form order."""

_LABEL_KEY_PREFIX: Final = "tui.ledger.link_picker.field."
_NONE_SERVED_LOCALE_KEY: Final = "tui.ledger.link_picker.none_served"
_UNCHANGED_LOCALE_KEY: Final = "tui.ledger.link_picker.unchanged"
_UNAVAILABLE_LOCALE_KEY: Final = "tui.ledger.link_picker.unavailable"
_HELD_UNAVAILABLE_LOCALE_KEY: Final = "tui.ledger.link_picker.held_unavailable"


class LedgerLinkOptionsDoorV1(Protocol):
    """Read the entry options of the exact profile, in the current output language."""

    async def __call__(self) -> LedgerEntryOptionsProjection:
        """Return the served entry options."""
        ...


class LedgerHeldLinksDoorV1(Protocol):
    """Read the links the row being edited holds now, by link field."""

    async def __call__(self) -> Mapping[str, str]:
        """Return the served value each held link field names; a field the row does not link is absent."""
        ...


def held_links(transaction: LedgerTransactionProjection) -> dict[str, str]:
    """The links a served transaction holds, by field, exactly as it serves them."""
    return {field: value for field in LINK_FAMILY_BY_FIELD if (value := getattr(transaction, field)) is not None}


def option_words(option: LedgerEntryOptionProjection) -> str:
    """A served choice's words: its served label, else the words of its served key, else its value."""
    if option.label_words is not None:
        return option.label_words
    return option.value if option.label_key is None else tr(option.label_key)


def link_families(options: LedgerEntryOptionsProjection) -> dict[str, LedgerEntryOptionFamilyProjection]:
    """The served family of each link field, keyed by the field; a family not served is absent."""
    served = {family.family: family for family in options.families}
    return {field: served[family] for field, family in LINK_FAMILY_BY_FIELD.items() if family in served}


class LedgerLinkPicker(Vertical):
    """Pick one served choice of one link field's family; read the chosen value from ``value``."""

    DEFAULT_CSS: ClassVar[str] = tokenised("""
    LedgerLinkPicker { height: auto; }
    LedgerLinkPicker .ledger-link-note { color: $text-muted; }
    """)

    def __init__(
        self,
        field: str,
        family: LedgerEntryOptionFamilyProjection,
        *,
        initial: str | None = None,
        id: str | None = None,
    ) -> None:
        """Offer ``family``'s served choices for ``field``, starting at ``initial`` when the family offers it."""
        super().__init__(id=id)
        self.field = field
        self._family = family
        offered = initial is not None and any(option.value == initial for option in family.options)
        self._initial = initial if offered else None

    @property
    def label(self) -> str:
        """The field's chrome label."""
        return tr(f"{_LABEL_KEY_PREFIX}{self.field}")

    @property
    def chosen_words(self) -> str | None:
        """The served words of the chosen value, or ``None`` while nothing is chosen."""
        value = self.value
        option = next((option for option in self._family.options if option.value == value), None)
        return None if option is None else option_words(option)

    @property
    def value(self) -> str | None:
        """The served value chosen, or ``None`` while nothing is chosen."""
        selected = self.query_one(Select).value
        return selected if isinstance(selected, str) else None

    @override
    def compose(self) -> ComposeResult:
        label_key = f"{_LABEL_KEY_PREFIX}{self.field}"
        yield localized(Static(tr(label_key), classes="ledger-link-label", markup=False), label_key)
        options = self._family.options
        yield Select[str](
            [(option_words(option), option.value) for option in options],
            value=Select.NULL if self._initial is None else self._initial,
            allow_blank=True,
            prompt=tr(_UNCHANGED_LOCALE_KEY),
            disabled=not options,
            classes="ledger-link-select",
        )
        if not options:
            yield localized(Static(tr(_NONE_SERVED_LOCALE_KEY), classes="ledger-link-note"), _NONE_SERVED_LOCALE_KEY)


def link_picker_id(scope: str, field: str) -> str:
    """The DOM id of one link field's picker on a form."""
    return f"{scope}-link-{field.replace('_', '-')}"


def link_pickers(
    scope: str, options: LedgerEntryOptionsProjection, initial: Mapping[str, str] | None = None
) -> list[LedgerLinkPicker]:
    """One picker per served link family, in form order, each at its ``initial`` value where offered."""
    held = initial or {}
    return [
        LedgerLinkPicker(field, family, initial=held.get(field), id=link_picker_id(scope, field))
        for field, family in link_families(options).items()
    ]


class LedgerLinkPickers(Vertical):
    """The link pickers of one form, mounted once the served entry options are read.

    Without a door nothing is offered; a read that fails says so and the form
    goes on without links.
    """

    DEFAULT_CSS: ClassVar[str] = tokenised("""
    LedgerLinkPickers { height: auto; }
    LedgerLinkPickers .ledger-link-note { color: $text-muted; }
    """)

    def __init__(
        self,
        scope: str,
        door: LedgerLinkOptionsDoorV1 | None,
        *,
        initial: Mapping[str, str] | None = None,
        held: LedgerHeldLinksDoorV1 | None = None,
        id: str | None = None,
    ) -> None:
        """Bind the scope, the options read, what the operator chose before and the read of the links the row holds."""
        super().__init__(id=id)
        self._scope = scope
        self._door = door
        self._initial = dict(initial or {})
        self._held = held

    def on_mount(self) -> None:
        """Read the served options off the event loop's input handling."""
        if self._door is not None:
            self.run_worker(self._offer(self._door), group="ledger-link-options", exit_on_error=False)

    async def _offer(self, door: LedgerLinkOptionsDoorV1) -> None:
        try:
            options = await door()
        except Exception:
            await self.mount(
                localized(Static(tr(_UNAVAILABLE_LOCALE_KEY), classes="ledger-link-note"), _UNAVAILABLE_LOCALE_KEY)
            )
            raise
        held: dict[str, str] = {}
        if self._held is not None:
            try:
                held = dict(await self._held())
            except Exception:
                # Pickers left unchosen send nothing, so the row keeps what it holds; say so rather than guess.
                await self.mount(
                    localized(
                        Static(tr(_HELD_UNAVAILABLE_LOCALE_KEY), classes="ledger-link-note"),
                        _HELD_UNAVAILABLE_LOCALE_KEY,
                    )
                )
        # What the operator chose before wins over what the row held.
        await self.mount_all(link_pickers(self._scope, options, {**held, **self._initial}))

    def chosen(self) -> dict[str, str]:
        """The served value chosen in each mounted picker, by field."""
        return chosen_links(self.query(LedgerLinkPicker))

    def chosen_lines(self) -> tuple[str, ...]:
        """Each chosen link as ``label: served words``, for a review of what will be sent."""
        return tuple(
            f"{picker.label}: {words}"
            for picker in self.query(LedgerLinkPicker)
            if (words := picker.chosen_words) is not None
        )


def chosen_links(pickers: Iterable[LedgerLinkPicker]) -> dict[str, str]:
    """The served value chosen in each picker, by field; a picker left unchosen sends nothing."""
    return {picker.field: value for picker in pickers if (value := picker.value) is not None}


__all__ = [
    "LINK_FAMILY_BY_FIELD",
    "LedgerHeldLinksDoorV1",
    "LedgerLinkOptionsDoorV1",
    "LedgerLinkPicker",
    "LedgerLinkPickers",
    "chosen_links",
    "held_links",
    "link_families",
    "link_picker_id",
    "link_pickers",
    "option_words",
]
