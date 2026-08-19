"""Read-only full-screen status page: profile, buckets, and auth.

This adapter is a pure projection surface. It renders a
:class:`StatusPageData` view-model — assembled by the entry-point layer
from the application authorities (the active profile record, the profile
bucket scan, the workflow auth state, and any
operator-facing :class:`~cadrumo.core.json_contract.Notice` advisories) —
into five bordered zones and mutates nothing. It owns no data access: the
adapter tier may name Textual but must not reach the application layer, so
the entry-point gathers the view-model and injects it here, mirroring the
way :func:`~cadrumo.adapters.inbound.tui.run_flow_tui` receives a
pre-built :class:`~cadrumo.application.flows.FlowDefinition`.

Masking is a rendering invariant, not a policy decision: a fact row
carrying ``masked=True`` renders the mask token in place of its value and
its raw value never reaches a widget, so a SECRET-shaped or otherwise
key-like fact can never appear on screen (or in a captured session log).

The notices zone is this surface's share of the shared
:class:`~cadrumo.adapters.inbound.tui.NoticeBand` — the same typed
``Notice`` objects a CLI envelope carries on its ``notices`` channel,
rendered here rather than re-modelled as a bespoke TUI-only advisory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import override

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingsMap
from textual.containers import Vertical
from textual.widgets import Footer, Static

from ....core.i18n import tr
from ....core.json_contract import Notice
from ._theme import (
    BASE_CSS,
    NOTICE_BAND_CSS,
    ContentDataTable,
    ContentScroll,
    NoticeBand,
    install_cadrumo_themes,
    toggle_appearance,
)


@dataclass(frozen=True, slots=True)
class StatusFactRow:
    """One resolved profile fact: its display label, value, and mask flag.

    ``masked`` is decided by the entry-point builder from the schema
    sensitivity (and a defensive key-like path/label heuristic). When it is
    ``True`` the builder has ALREADY replaced ``value`` with the mask token,
    so the secret never enters this view-model: a later consumer -- a screen,
    a diagnostic dump, a snapshot -- cannot leak what it was never given.
    The flag remains so a renderer can style a redacted cell distinctly.
    """

    label: str
    value: str
    masked: bool = False


@dataclass(frozen=True, slots=True)
class StatusProfileRow:
    """One registered profile bucket: label, setup-state token, active marker."""

    label: str
    setup_state: str | None = None
    active: bool = False


@dataclass(frozen=True, slots=True)
class StatusAuthView:
    """Local AEAT access readiness projected from the workflow auth state.

    ``idle_deadline`` and ``absolute_deadline`` are a second, unrelated
    fact carried on this same panel: not AEAT auth readiness, but how long
    the operator's own unlocked PROFILE session — the one ``aeat config
    login`` opened — has left before it locks again. They share this zone
    because it is the one place on the page an operator already looks to
    ask "am I authenticated right now", and "for how much longer" is the
    same question. ``None`` for either means no live profile session could
    be read (never logged in, or the session artefacts are unreadable).
    """

    provider: str | None = None
    login_ready: bool = False
    subject: str | None = None
    certificate_source: str | None = None
    idle_deadline: datetime | None = None
    absolute_deadline: datetime | None = None


@dataclass(frozen=True, slots=True)
class StatusPageData:
    """The full read-only view-model rendered by :class:`StatusApp`.

    Masking is a build-time invariant: the entry-point builder substitutes
    the mask token before a ``StatusFactRow`` is constructed, so a secret
    never enters this view-model and no renderer can be trusted wrongly.
    """

    active_profile_label: str | None = None
    facts: tuple[StatusFactRow, ...] = ()
    profiles: tuple[StatusProfileRow, ...] = ()
    auth: StatusAuthView = field(default_factory=StatusAuthView)
    notices: tuple[Notice, ...] = ()
    """Operator-facing advisories, off the same typed channel a CLI envelope
    carries. Empty on a healthy profile; the panel that renders these is
    omitted entirely rather than shown blank."""


_PROFILE_SETUP_STATE_LOCALE_KEYS: dict[str, str] = {
    "complete": "flows.status.profiles.status.complete",
    "incomplete": "flows.status.profiles.status.incomplete",
}

_ACTIVE_MARKER = "●"
"""Glyph marking the active profile row — a marker, not prose."""


class StatusApp(App[None]):
    """Full-screen read-only projection of the operator's configuration state."""

    CSS = (
        BASE_CSS
        + NOTICE_BAND_CSS
        + """
    .status-panel DataTable { height: auto; width: 100%; background: $surface; }
    .status-empty { color: $text-muted; text-style: italic; }
    .status-commands { color: $text-muted; margin: 0; }
    """
    )

    # Keys and actions only; descriptions resolve in on_mount so the footer
    # tracks the active language, not the import-time language.
    BINDINGS = [
        Binding("q", "quit", ""),
        Binding("escape", "quit", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(self, data: StatusPageData) -> None:
        super().__init__()
        self._data = data

    @override
    def compose(self) -> ComposeResult:
        """Yield the status screen's widgets: header and the scrollable status body."""
        yield Static(id="status-header", classes="cadrumo-banner")
        with ContentScroll(id="status-body", classes="cadrumo-scroll"), Vertical(classes="cadrumo-column"):
            yield Static(id="panel-notices", classes="status-panel cadrumo-panel")
            yield Static(id="panel-profile", classes="status-panel cadrumo-panel")
            yield Static(id="panel-profiles", classes="status-panel cadrumo-panel")
            yield Static(id="panel-auth", classes="status-panel cadrumo-panel")
        yield Footer()

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self._localize_bindings()
        self.query_one("#status-header", Static).update(tr("flows.status.title"))
        self._mount_notices_panel()
        self._mount_profile_panel()
        self._mount_profiles_panel()
        self._mount_auth_panel()

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance; the projection is read-only."""
        toggle_appearance(self)

    def _localize_bindings(self) -> None:
        self._bindings = BindingsMap(
            [
                Binding("q", "quit", tr("flows.status.binding_quit")),
                Binding("escape", "quit", tr("flows.status.binding_quit")),
                # Rebuilt here too: this map REPLACES the class-level BINDINGS
                # wholesale, so a binding omitted from this list is dropped at
                # mount rather than merged.
                Binding("f3", "toggle_appearance", "", show=False),
            ],
        )
        self.refresh_bindings()

    # ── zone (0): operator-facing advisories ────────────────────────────

    def _mount_notices_panel(self) -> None:
        """Render the notices zone, or remove it outright when there is nothing to say.

        An empty bordered box reads as a rendering defect on a page whose
        every other zone always has something to show; a healthy profile
        should not carry a permanent "no advisories" placeholder that
        trains the operator to stop reading it.
        """
        panel = self.query_one("#panel-notices", Static)
        if not self._data.notices:
            panel.remove()
            return
        panel.border_title = tr("flows.status.section.notices")
        panel.mount(NoticeBand(self._data.notices, id="status-notice-band"))

    # ── zone (a): active profile facts ──────────────────────────────────

    def _mount_profile_panel(self) -> None:
        panel = self.query_one("#panel-profile", Static)
        panel.border_title = tr("flows.status.section.profile")
        if not self._data.facts:
            panel.mount(Static(tr("flows.status.profile.none"), classes="status-empty"))
            return
        table: ContentDataTable[str] = ContentDataTable(
            id="profile-facts",
            cursor_type="none",
            zebra_stripes=True,
        )
        panel.mount(table)
        table.add_columns(
            tr("flows.status.profile.column.field"),
            tr("flows.status.profile.column.value"),
        )
        for index, row in enumerate(self._data.facts):
            rendered = tr("flows.status.masked_value") if row.masked else row.value
            table.add_row(row.label, rendered, key=f"fact-{index}")

    # ── zone (b): profiles overview ─────────────────────────────────────

    def _mount_profiles_panel(self) -> None:
        panel = self.query_one("#panel-profiles", Static)
        panel.border_title = tr("flows.status.section.profiles")
        if not self._data.profiles:
            panel.mount(Static(tr("flows.status.profiles.none"), classes="status-empty"))
            return
        table: ContentDataTable[str] = ContentDataTable(
            id="profiles-table",
            cursor_type="none",
            zebra_stripes=True,
        )
        panel.mount(table)
        table.add_columns(
            tr("flows.status.profiles.column.label"),
            tr("flows.status.profiles.column.status"),
            tr("flows.status.profiles.column.active"),
        )
        for index, row in enumerate(self._data.profiles):
            # An unmapped setup-state token is not operator copy. It must still
            # refuse to look healthy, but without exposing the storage token.
            setup_state_key = _PROFILE_SETUP_STATE_LOCALE_KEYS.get(row.setup_state or "")
            status_label = (
                tr(setup_state_key) if setup_state_key is not None else tr("flows.status.profiles.status.unknown")
            )
            marker = _ACTIVE_MARKER if row.active else ""
            table.add_row(row.label, status_label, marker, key=f"profile-{index}")

    # ── zone (c): authentication ────────────────────────────────────────

    def _mount_auth_panel(self) -> None:
        panel = self.query_one("#panel-auth", Static)
        panel.border_title = tr("flows.status.section.auth")
        auth = self._data.auth
        provider = auth.provider or tr("flows.status.auth.provider_none")
        login = tr("flows.status.auth.login_ready") if auth.login_ready else tr("flows.status.auth.login_not_ready")
        lines = [
            f"{tr('flows.status.auth.provider')}\t{provider}",
            f"{tr('flows.status.auth.status')}\t{login}",
        ]
        if auth.subject:
            lines.append(f"{tr('flows.status.auth.subject')}\t{auth.subject}")
        if auth.certificate_source:
            lines.append(f"{tr('flows.status.auth.certificate_source')}\t{auth.certificate_source}")
        if auth.idle_deadline is not None:
            lines.append(f"{tr('flows.status.auth.idle_deadline')}\t{auth.idle_deadline.isoformat(timespec='minutes')}")
        if auth.absolute_deadline is not None:
            lines.append(
                f"{tr('flows.status.auth.absolute_deadline')}\t{auth.absolute_deadline.isoformat(timespec='minutes')}",
            )
        panel.mount(Static("\n".join(lines), id="auth-lines"))


__all__ = [
    "StatusApp",
    "StatusAuthView",
    "StatusFactRow",
    "StatusPageData",
    "StatusProfileRow",
]
