"""Read-only full-screen status page: profile, buckets, and auth.

This adapter is a pure projection surface. It renders a
:class:`StatusPageData` view-model — assembled by the entry-point layer
from the application authorities (the active profile record, the profile
bucket scan, the workflow auth state, and any
operator-facing :class:`~cadrumo.core.json_contract.Notice` advisories) —
into five bordered zones and mutates nothing. It owns no data access: the
adapter tier may name Textual but must not reach the application layer, so
the entry-point gathers the view-model and injects it here, mirroring the
way a flow renderer receives a
pre-built :class:`~cadrumo.application.flows.definition.FlowDefinition`.

Masking is a rendering invariant, not a policy decision: a fact row
carrying ``masked=True`` renders the mask token in place of its value and
its raw value never reaches a widget, so a SECRET-shaped or otherwise
key-like fact can never appear on screen (or in a captured session log).

The notices zone is this surface's share of the shared
:class:`~cadrumo.entrypoints.tui.components.widgets.NoticeBand` — the same typed
``Notice`` objects a CLI envelope carries on its ``notices`` channel,
rendered here rather than re-modelled as a bespoke TUI-only advisory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ....core.i18n._render import tr
from ....entrypoints.tui.components.keyboard import localize_key_descriptions
from ....entrypoints.tui.components.theme import (
    BASE_CSS,
    NOTICE_BAND_CSS,
    install_cadrumo_themes,
    toggle_appearance,
    tokenised,
)
from ....entrypoints.tui.components.widgets import ContentDataTable, ContentScroll, NoticeBand

if TYPE_CHECKING:
    from ....application.user_profile.status_projection import StatusPageData

_PROFILE_SETUP_STATE_LOCALE_KEYS: dict[str, str] = {
    "complete": "flows.status.profiles.status.complete",
    "incomplete": "flows.status.profiles.status.incomplete",
}

_ACTIVE_MARKER = "●"
"""Glyph marking the active profile row — a marker, not prose."""


class StatusScreen(Screen[None]):
    """Full-screen read-only projection of the operator's configuration state."""

    SCOPED_CSS = False
    DEFAULT_CSS = tokenised(
        BASE_CSS
        + NOTICE_BAND_CSS
        + """
    .status-panel DataTable { height: auto; width: 100%; background: $surface; }
    .status-empty { color: $text-muted; text-style: italic; }
    .status-commands { color: $text-muted; margin: $cadrumo-space-0; }
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
        """Initialize the read-only page from its supplied status projection."""
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
        """Install the presentation theme and mount the populated zones."""
        install_cadrumo_themes(self.app)
        self._localize_bindings()
        self.query_one("#status-header", Static).update(tr("flows.status.title"))
        self._mount_notices_panel()
        self._mount_profile_panel()
        self._mount_profiles_panel()
        self._mount_auth_panel()

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance; the projection is read-only."""
        toggle_appearance(self.app)

    def _localize_bindings(self) -> None:
        localize_key_descriptions(self, {"quit": tr("flows.status.binding_quit")})

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


__all__ = ["StatusScreen"]
