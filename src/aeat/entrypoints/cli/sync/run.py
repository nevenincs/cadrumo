"""``aeat sync run`` -- execute a single live-to-local sync run.

The runner depends on several adjacent subsystems -- the certificate
backend, corpus loader, schema loader, manual-rules pipeline, and
LLM client -- that are not yet wired in. Until those land this
command validates settings and then refuses with a structured exit
code rather than constructing a half-wired runner.
"""

from __future__ import annotations

import typer
from rich.console import Console

from ....core.config import load_settings
from .._observability import cli_run_context

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
    """Validate sync settings and report the missing runner prerequisites.

    The command refuses to launch until the cross-cutting
    dependencies (certificate backend, corpus loader, schema loader,
    manual rules, LLM client) are wired in. The bounded auto-heal
    invariant still applies once the runner is fully composed.

    Args:
        modelo: Optional modelo identifier scoping the run.
        period: Optional filing-period filter.
        auto_heal: When ``True``, permit bounded auto-heal on
            additive divergences whose casilla is allowlisted via
            :attr:`aeat.core.config.Settings.aeat_sync_auto_heal_allowlist`.

    Raises:
        typer.Exit: Always exits with code ``2`` until the runner is
            fully wired.
    """
    arguments = {"modelo": modelo, "period": period, "auto-heal": auto_heal}
    with cli_run_context(entrypoint="aeat sync run", arguments=arguments):
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
