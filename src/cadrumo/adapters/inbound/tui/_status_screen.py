"""Read-only full-screen status page: profile, buckets, auth, recovery.

This adapter is a pure projection surface. It renders a
:class:`StatusPageData` view-model — assembled by the entry-point layer
from the application authorities (the active profile record, the profile
bucket scan, the workflow auth state, and the recovery-wrapper status) —
into four bordered zones and mutates nothing. It owns no data access: the
adapter tier may name Textual but must not reach the application layer, so
the entry-point gathers the view-model and injects it here, mirroring the
way :func:`~cadrumo.adapters.inbound.tui.run_flow_tui` receives a
pre-built :class:`~cadrumo.application.flows.FlowDefinition`.

Masking is a rendering invariant, not a policy decision: a fact row
carrying ``masked=True`` renders the mask token in place of its value and
its raw value never reaches a widget, so a SECRET-shaped or otherwise
key-like fact can never appear on screen (or in a captured session log).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import override

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingsMap
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Footer, Static

from ....core.i18n import tr
from ._theme import BASE_CSS, install_cadrumo_themes, toggle_appearance

# Copyable custody / recovery next-step lines. These are literal CLI
# invocations (command tokens, not operator prose), rendered verbatim so an
# operator can copy them into a terminal. The surrounding labels resolve
# through ``tr``; the command tokens do not.
_RECOVERY_COMMANDS: tuple[str, ...] = (
    "aeat config recovery create",
    "aeat config recovery rotate",
    "aeat config recovery verify",
    "aeat config recover",
    "aeat config passphrase change",
    "aeat config login NAME",
)


@dataclass(frozen=True, slots=True)
class StatusFactRow:
    """One resolved profile fact: its display label, value, and mask flag.

    ``masked`` is decided by the entry-point builder from the schema
    sensitivity (and a defensive key-like path/label heuristic); when it is
    ``True`` the screen renders the mask token and never the ``value``.
    """

    label: str
    value: str
    masked: bool = False


@dataclass(frozen=True, slots=True)
class StatusProfileRow:
    """One registered profile bucket: label, lifecycle status token, active marker."""

    label: str
    status: str
    active: bool = False


@dataclass(frozen=True, slots=True)
class StatusAuthView:
    """Local AEAT access readiness projected from the workflow auth state."""

    provider: str | None = None
    login_ready: bool = False
    subject: str | None = None
    certificate_source: str | None = None


@dataclass(frozen=True, slots=True)
class StatusRecoveryView:
    """Recovery-wrapper enrollment state (no secret, never a mnemonic)."""

    enrolled: bool = False
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class StatusPageData:
    """The full read-only view-model rendered by :class:`StatusApp`.

    Masking is a render-side invariant today: a ``StatusFactRow`` still
    carries its raw value and the screen substitutes the mask token when the
    row is masked. Should a genuinely secret-bearing zone ever be added, the
    direction is to redact at build time so the secret never enters the
    view-model at all, rather than relying on render-side substitution.
    """

    active_profile_label: str | None = None
    facts: tuple[StatusFactRow, ...] = ()
    profiles: tuple[StatusProfileRow, ...] = ()
    auth: StatusAuthView = field(default_factory=StatusAuthView)
    recovery: StatusRecoveryView = field(default_factory=StatusRecoveryView)


_PROFILE_STATUS_KEYS: dict[str, str] = {
    "active": "flows.status.profiles.status.active",
    "setup_incomplete": "flows.status.profiles.status.setup_incomplete",
    "tombstoned": "flows.status.profiles.status.tombstoned",
}

_ACTIVE_MARKER = "●"
"""Glyph marking the active profile row — a marker, not prose."""


class StatusApp(App[None]):
    """Full-screen read-only projection of the operator's configuration state."""

    CSS = (
        BASE_CSS
        + """
    VerticalScroll { align-horizontal: center; }
    #status-header {
        dock: top;
        height: 1;
        width: 100%;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 2;
    }
    .status-panel {
        border: round $primary;
        border-title-color: $accent;
        border-title-style: bold;
        background: $surface;
        padding: 1 3;
        margin: 1 2;
        width: 100%;
        max-width: 110;
        height: auto;
    }
    .status-panel DataTable { height: auto; width: 100%; background: $surface; }
    .status-empty { color: $text-muted; text-style: italic; }
    .status-commands { color: $text-muted; margin: 1 0 0 0; }
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
        yield Static(id="status-header")
        with VerticalScroll(id="status-body"):
            yield Static(id="panel-profile", classes="status-panel")
            yield Static(id="panel-profiles", classes="status-panel")
            yield Static(id="panel-auth", classes="status-panel")
            yield Static(id="panel-recovery", classes="status-panel")
        yield Footer()

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self._localize_bindings()
        self.query_one("#status-header", Static).update(tr("flows.status.title"))
        self._mount_profile_panel()
        self._mount_profiles_panel()
        self._mount_auth_panel()
        self._mount_recovery_panel()

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

    # ── zone (a): active profile facts ──────────────────────────────────

    def _mount_profile_panel(self) -> None:
        panel = self.query_one("#panel-profile", Static)
        panel.border_title = tr("flows.status.section.profile")
        if not self._data.facts:
            panel.mount(Static(tr("flows.status.profile.none"), classes="status-empty"))
            return
        table = DataTable(id="profile-facts", cursor_type="none", zebra_stripes=True)
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
        table = DataTable(id="profiles-table", cursor_type="none", zebra_stripes=True)
        panel.mount(table)
        table.add_columns(
            tr("flows.status.profiles.column.label"),
            tr("flows.status.profiles.column.status"),
            tr("flows.status.profiles.column.active"),
        )
        for index, row in enumerate(self._data.profiles):
            # An unmapped lifecycle token renders as its raw value, never a
            # reassuring "active" label: a future status member must not be
            # silently misreported as healthy on a status surface.
            status_key = _PROFILE_STATUS_KEYS.get(row.status)
            status_label = tr(status_key) if status_key is not None else row.status
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
        panel.mount(Static("\n".join(lines), id="auth-lines"))

    # ── zone (d): recovery / custody pointers ───────────────────────────

    def _mount_recovery_panel(self) -> None:
        panel = self.query_one("#panel-recovery", Static)
        panel.border_title = tr("flows.status.section.recovery")
        recovery = self._data.recovery
        state = tr("flows.status.recovery.enrolled") if recovery.enrolled else tr("flows.status.recovery.not_enrolled")
        lines = [f"{tr('flows.status.recovery.state')}\t{state}"]
        if recovery.fingerprint:
            lines.append(f"{tr('flows.status.recovery.fingerprint')}\t{recovery.fingerprint}")
        panel.mount(Static("\n".join(lines), id="recovery-lines"))
        panel.mount(
            Static(
                tr("flows.status.recovery.commands_title") + "\n" + "\n".join(_RECOVERY_COMMANDS),
                id="recovery-commands",
                classes="status-commands",
            ),
        )


__all__ = [
    "StatusApp",
    "StatusAuthView",
    "StatusFactRow",
    "StatusPageData",
    "StatusProfileRow",
    "StatusRecoveryView",
]
