"""``aeat inbox`` sub-app — CLI surface for the notifications inbox.

Wires five subcommands under ``aeat inbox`` per the inbox ADR
[[2026-04-12-notifications-inbox-adr]]:

- ``aeat inbox fetch [--since YYYY-MM-DD]`` — pull new notifications.
- ``aeat inbox list [--unread] [--priority ...]`` — show records.
- ``aeat inbox show <notificacion-id>`` — pretty-print one.
- ``aeat inbox ack <notificacion-id> --by <initials>`` — **local**
  acknowledgement. AEAT is not notified.
- ``aeat inbox next-deadline`` — surface the soonest unacked
  CRITICAL/HIGH deadline within the lead window.
"""

from __future__ import annotations

import typer

from .ack import ack_cmd
from .fetch import fetch_cmd
from .list import list_cmd
from .next_deadline import next_deadline_cmd
from .show import show_cmd

app = typer.Typer(
    name="inbox",
    no_args_is_help=True,
    help="AEAT notifications inbox (#46).",
)

app.command(name="fetch", help="Pull new notifications from the configured source.")(fetch_cmd)
app.command(name="list", help="List persisted Notificacion records.")(list_cmd)
app.command(name="show", help="Pretty-print a Notificacion by notificacion_id.")(show_cmd)
app.command(
    name="ack",
    help="Locally acknowledge a notification. Does NOT notify AEAT.",
)(ack_cmd)
app.command(
    name="next-deadline",
    help="Surface the soonest unacknowledged CRITICAL/HIGH appeal deadline.",
)(next_deadline_cmd)


__all__ = ["app"]
