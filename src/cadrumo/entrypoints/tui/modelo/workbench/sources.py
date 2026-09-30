"""Where the declaration's values come from, grouped the way a filer thinks of sources.

Every source the form carries is listed under its family -- your records,
registers you keep, your profile, earlier filings, the AEAT draft, values you
enter, values the official design fixes. Each source says in words what may be
done about its values (corrected at the source, replaced, changed in the
profile, entered, fixed, or not decided yet) and whether it produced them, and
lists the boxes it feeds with the workbench's own vocabulary, so an imported,
missing, overridden or staged value reads exactly as it does on its page. A box
fed by several sources is listed once, under the first, and noted under the
others.

The view decides nothing and edits nothing. Enter returns to the workbench on
the chosen box, where it can be changed if its policy allows; ``o`` asks the
workbench to open the product area that owns the source, such as the ledger.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

from .....application.modelo.source_policy import SourceFamily, SourcePolicyV1, SourceSurface
from .....application.modelo.work_form_models import ModeloFormField, ModeloWorkForm, address_key
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.theme import tokenised
from ...navigation import TuiDestinationIdV1, TuiFocusIdentityV1, TuiNavigationTargetV1
from .casilla_list import (
    AddressKey,
    CasillaList,
    CasillaListEntry,
    CasillaListHeading,
    CasillaListItem,
    CasillaListNote,
)
from .dialog_width import fit_dialog_width
from .keys import describe_bindings
from .page_items import StagedDisplay

_FAMILY_ORDER: Final[tuple[SourceFamily, ...]] = (
    SourceFamily.RECORDS,
    SourceFamily.REGISTERS,
    SourceFamily.PROFILE,
    SourceFamily.EARLIER_FILINGS,
    SourceFamily.AEAT_DRAFT,
    SourceFamily.YOUR_ENTRIES,
    SourceFamily.FIXED_BY_DESIGN,
)
_SURFACE_DESTINATIONS: Final[Mapping[SourceSurface, tuple[TuiDestinationIdV1, str]]] = {
    SourceSurface.LEDGER: ("workbench.ledger", "ledger.overview"),
    SourceSurface.WITHHOLDING: ("workbench.withholding", "withholding.overview"),
    SourceSurface.PROFILE: ("workbench.profile", "profile.overview"),
    SourceSurface.DECLARATIONS: ("workbench.declarations", "declarations.work"),
}
_ENTRY_INDENT: Final[int] = 2
_SCREEN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "escape": "tui.modelo.workbench.key.back",
    "o": "tui.modelo.workbench.sources.key.open",
}
_LIST_LOCALE_KEYS: Final[Mapping[str, str]] = {"enter": "tui.modelo.workbench.sources.key.go"}


@dataclass(frozen=True, slots=True)
class SourceGroup:
    """One source kind the form draws on, the boxes it feeds and how many of its bindings produced nothing."""

    policy: SourcePolicyV1
    bindings: int
    missing: int
    fields: tuple[ModeloFormField, ...]


@dataclass(frozen=True, slots=True)
class SourcesListing:
    """The lines of the sources view and the source each listed box sits under."""

    items: tuple[CasillaListItem, ...]
    listed_under: Mapping[AddressKey, SourcePolicyV1]


@dataclass(frozen=True, slots=True)
class GoToCasilla:
    """The filer chose a box: return to the workbench on it."""

    key: AddressKey


@dataclass(frozen=True, slots=True)
class OpenSourceSurface:
    """The filer asked to open the product area that owns a source."""

    surface: SourceSurface


type SourcesChoice = GoToCasilla | OpenSourceSurface


def source_groups(form: ModeloWorkForm) -> tuple[SourceGroup, ...]:
    """Collect every source kind the form's fields name, in family order, then first appearance."""
    policies: dict[str, SourcePolicyV1] = {}
    resolved: dict[str, dict[str, bool]] = {}
    fed: dict[str, dict[AddressKey, ModeloFormField]] = {}
    for field in form.fields():
        for binding in field.bindings:
            kind = binding.policy.source_kind.value
            policies.setdefault(kind, binding.policy)
            seen = resolved.setdefault(kind, {})
            seen[binding.binding_id] = seen.get(binding.binding_id, False) or binding.resolved
            fed.setdefault(kind, {}).setdefault(address_key(field.address), field)
    ordered = sorted(policies, key=lambda kind: _FAMILY_ORDER.index(policies[kind].family))
    return tuple(
        SourceGroup(
            policy=policies[kind],
            bindings=len(resolved[kind]),
            missing=sum(1 for produced in resolved[kind].values() if not produced),
            fields=tuple(fed[kind].values()),
        )
        for kind in ordered
    )


def _state_text(group: SourceGroup) -> str:
    if group.missing:
        return tr("tui.modelo.workbench.sources.state.missing", missing=group.missing, total=group.bindings)
    return tr("tui.modelo.workbench.sources.state.complete")


def _listed_above_text(field: ModeloFormField) -> str:
    box = f"[{field.box}] " if field.box else ""
    return tr("tui.modelo.workbench.sources.listed_above", field=f"{box}{field.label.text}")


def sources_listing(groups: tuple[SourceGroup, ...], *, staged: Mapping[AddressKey, StagedDisplay]) -> SourcesListing:
    """Lay the groups out under family headings; each box is a line once and a note elsewhere."""
    items: list[CasillaListItem] = []
    listed_under: dict[AddressKey, SourcePolicyV1] = {}
    family: SourceFamily | None = None
    for group in groups:
        if group.policy.family is not family:
            family = group.policy.family
            items.append(CasillaListHeading(tr(f"tui.modelo.workbench.sources.family.{family.value}")))
        policy_words = tr(f"tui.modelo.workbench.sources.policy.{group.policy.override_policy.value}")
        items.append(
            CasillaListHeading(f"{tr(group.policy.label_key)} · {policy_words} · {_state_text(group)}", level=1)
        )
        for field in group.fields:
            key = address_key(field.address)
            if key in listed_under:
                items.append(CasillaListNote(_listed_above_text(field), indent=_ENTRY_INDENT))
                continue
            listed_under[key] = group.policy
            change = staged.get(key)
            items.append(
                CasillaListEntry(
                    field=field,
                    indent=_ENTRY_INDENT,
                    staged_text=None if change is None else change.text,
                    previous_text=None if change is None else change.previous_text,
                )
            )
    return SourcesListing(items=tuple(items), listed_under=listed_under)


def surface_target(surface: SourceSurface) -> TuiNavigationTargetV1 | None:
    """The product area that owns a source's data, or ``None`` when no area owns it."""
    destination = _SURFACE_DESTINATIONS.get(surface)
    if destination is None:
        return None
    destination_id, semantic_key = destination
    return TuiNavigationTargetV1(
        destination=destination_id,
        focus=TuiFocusIdentityV1(destination=destination_id, semantic_key=semantic_key),
    )


class WorkbenchSourcesScreen(ModalScreen[SourcesChoice | None]):
    """The declaration's sources, grouped by family; choosing a box returns to it."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        WorkbenchSourcesScreen #sources-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        WorkbenchSourcesScreen #sources-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        WorkbenchSourcesScreen.-narrow #sources-panel {
            width: 100%;
        }
        WorkbenchSourcesScreen #sources-title {
            text-style: bold;
            color: $primary;
        }
        WorkbenchSourcesScreen #sources-intro {
            color: $secondary;
        }
        WorkbenchSourcesScreen #sources-notice {
            color: $warning;
            height: auto;
            margin-bottom: $cadrumo-stack;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("escape,q", "close", "", show=False),
        Binding("o", "open_source", "", show=False),
    ]

    def __init__(
        self,
        form: ModeloWorkForm,
        *,
        language: OutputLanguage,
        staged: Mapping[AddressKey, StagedDisplay],
        focus: AddressKey | None = None,
    ) -> None:
        """Hold the form to list, the filer's staged changes and the box to start on."""
        super().__init__()
        self._listing = sources_listing(source_groups(form), staged=staged)
        self._language = language
        self._focus = focus

    @override
    def compose(self) -> ComposeResult:
        with Container(id="sources-backdrop"), Vertical(id="sources-panel"):
            yield Static(tr("tui.modelo.workbench.sources.title"), id="sources-title", markup=False)
            intro = (
                tr("tui.modelo.workbench.sources.intro")
                if self._listing.items
                else tr("tui.modelo.workbench.sources.none")
            )
            yield Static(intro, id="sources-intro", markup=False)
            yield Static("", id="sources-notice", markup=False)
            yield CasillaList(self._listing.items, language=self._language, id="sources-list")
        yield Footer(compact=True)

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Describe the keys, start on the requested box and take the focus."""
        fit_dialog_width(self, self.app.size.width)
        describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS)
        self.refresh_bindings()
        casilla_list = self.query_one(CasillaList)
        casilla_list.describe_keys(_LIST_LOCALE_KEYS)
        if self._focus is not None:
            casilla_list.focus_address(self._focus)
        casilla_list.focus()

    def on_casilla_list_edit_requested(self, message: CasillaList.EditRequested) -> None:
        """Return to the workbench on the chosen box."""
        message.stop()
        self.dismiss(GoToCasilla(message.entry.key))

    def action_open_source(self) -> None:
        """Ask to open the product area that owns the source of the box under the cursor."""
        entry = self.query_one(CasillaList).highlighted
        if entry is None:
            return
        policy = self._listing.listed_under[entry.key]
        if surface_target(policy.surface) is None:
            self.query_one("#sources-notice", Static).update(
                tr("tui.modelo.workbench.sources.no_surface", source=tr(policy.label_key))
            )
            return
        self.dismiss(OpenSourceSurface(policy.surface))

    def action_close(self) -> None:
        """Return to the workbench where it was."""
        self.dismiss(None)


__all__ = [
    "GoToCasilla",
    "OpenSourceSurface",
    "SourceGroup",
    "SourcesChoice",
    "SourcesListing",
    "WorkbenchSourcesScreen",
    "source_groups",
    "sources_listing",
    "surface_target",
]
