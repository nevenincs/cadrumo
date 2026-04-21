"""``aeat inbox next-deadline`` — surface the most urgent appeal deadline."""

from __future__ import annotations

from datetime import date

from rich.console import Console

from ...config import load_settings
from ...inbox import next_appeal_deadline
from .._observability import cli_run_context
from ._helpers import build_fetcher

_CONSOLE = Console()


def next_deadline_cmd() -> None:
    """Print the soonest unacknowledged CRITICAL/HIGH deadline within the lead window."""
    with cli_run_context(entrypoint="aeat inbox next-deadline", arguments={}):
        cfg = load_settings()
        fetcher = build_fetcher(settings=cfg)
        inbox = fetcher.load_inbox()
        record = next_appeal_deadline(
            inbox,
            today=date.today(),
            lead_days=cfg.aeat_inbox_alert_lead_days,
        )
        if record is None:
            _CONSOLE.print(
                f"[green]no upcoming CRITICAL/HIGH deadline within {cfg.aeat_inbox_alert_lead_days} day(s)[/green]"
            )
            return
        assert record.appeal_deadline is not None  # invariant: next_appeal_deadline filters None
        days = (record.appeal_deadline - date.today()).days
        _CONSOLE.print(
            f"[bold red]NEXT DEADLINE[/bold red] {record.notificacion_id} "
            f"[{record.kind.value}/{record.priority.value}] "
            f"due {record.appeal_deadline.isoformat()} ({days} day(s))"
        )
