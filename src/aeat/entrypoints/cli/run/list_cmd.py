"""``aeat run list`` command implementation.

Iterates persisted run traces via
:func:`aeat.core.observability.iter_runs` and renders them as a Rich
table.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ....core.observability import iter_runs

_CONSOLE = Console()


def list_cmd() -> None:
    """List every persisted :class:`RunTrace` under the configured runs dir.

    The configured directory is read from
    :attr:`aeat.core.config.Settings.aeat_runs_dir` via
    :func:`aeat.core.observability.iter_runs`.
    """
    runs = list(iter_runs())
    table = Table(title=f"runs ({len(runs)})", header_style="bold")
    table.add_column("run_id", style="cyan")
    table.add_column("started_at")
    table.add_column("entrypoint")
    table.add_column("outcome")
    for run_id, trace in runs:
        table.add_row(
            run_id,
            trace.started_at.isoformat(),
            trace.entrypoint,
            trace.outcome.value,
        )
    _CONSOLE.print(table)
