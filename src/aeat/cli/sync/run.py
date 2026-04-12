"""``aeat sync run`` — execute a single live-to-local sync run.

The runner requires the in-flight dependencies from #8 (certificate
backend), #17 (corpus loader), #9 (schema loader), #25 (manual rules),
and #21 (LLM client). Until those branches merge, this command
performs its settings validation and then refuses with a structured
error instead of attempting to construct a half-wired runner.
"""

from __future__ import annotations

import typer
from rich.console import Console

from aeat.config import load_settings

_CONSOLE = Console()


def run(
    modelo: str | None = typer.Option(
        None,
        "--modelo",
        help="Optional modelo identifier to scope the run (e.g. '100').",
    ),
    period: str | None = typer.Option(
        None,
        "--period",
        help="Optional filing period filter (e.g. '2024Q1').",
    ),
    auto_heal: bool = typer.Option(
        False,
        "--auto-heal",
        help="Permit bounded auto-heal on additive+allowlisted divergences.",
    ),
) -> None:
    """Validate settings and report runner prerequisites.

    The command refuses to launch until the cross-branch dependencies
    listed in the ADR ship. The bounded auto-heal invariant still
    applies when the runner eventually wires up.
    """
    settings = load_settings()
    _CONSOLE.print(
        f"[bold]sync run[/bold]: modelo={modelo or '<all>'} period={period or '<all>'} auto_heal={auto_heal}"
    )
    _CONSOLE.print(f"allowlist: {settings.aeat_sync_auto_heal_allowlist}")
    _CONSOLE.print(
        f"sink: {settings.aeat_sync_divergence_sink.value} file_dir={settings.aeat_sync_divergence_file_dir}"
    )
    _CONSOLE.print(
        "[yellow]runner prerequisites pending[/yellow]: certificate backend (#8), "
        "corpus loader (#17), schema loader (#9), manual rules (#25), LLM client "
        "(#21). The runner refuses to launch until those branches merge."
    )
    raise typer.Exit(code=2)
