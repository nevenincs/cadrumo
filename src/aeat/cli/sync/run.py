"""``aeat sync run`` — execute a single live-to-local sync run.

The runner requires the in-flight dependencies from #8 (certificate
backend), #17 (corpus loader), #9 (schema loader), #25 (manual rules),
and #21 (LLM client). Until those branches merge, this command
performs its settings validation and then refuses with a structured
error instead of attempting to construct a half-wired runner.

Phase 5 of the ``aeat-verify`` feature (#239) inserts an
auto-reconciliation stage ahead of the prerequisites-pending refusal.
The stage iterates every :attr:`aeat.filing.FilingDraftStatus.APPROVED`
filing draft on disk, reconciles it against AEAT through a single
:class:`aeat.remote.RemoteFilingFetcher` (session reuse per the ADR),
persists :attr:`ReconciliationStatus.DIVERGENT` and
:attr:`ReconciliationStatus.NOT_YET_FOUND` reports through the Phase-3
:class:`aeat.filing.reconciliation.FilingReconciliationDivergenceRecord`
adapter, and surfaces ``NOT_YET_FOUND`` prominently in the end-of-run
summary. The reconcile stage is the only part of ``aeat sync run``
that functions today; the rest remains stubbed behind the refusal
until the cross-branch dependencies merge.

Wiring is injectable via the :func:`register` factory: production
passes a real fetcher + sink (one per invocation so one AEAT session
backs the whole pass); the unit suite passes Protocol-conforming
Python classes to assert session reuse and persistence semantics
without touching the live Playwright stack.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from ...config import load_settings
from ...remote import RemoteFilingFetcher
from .._observability import cli_run_context
from ._reconcile_stage import (
    ReconciliationSink,
    emit_reconcile_summary,
    run_reconcile_stage,
)

_CONSOLE = Console()


def _default_utcnow() -> datetime:
    """Return the current UTC wall-clock time (injection seam default)."""
    return datetime.now(tz=UTC)


def _default_drafts_dir() -> Path:
    """Resolve the persisted-drafts directory from :class:`Settings`."""
    return Path(load_settings().aeat_drafts_dir)


def register(
    app: typer.Typer,
    *,
    fetcher_provider: Callable[[], RemoteFilingFetcher | None] = lambda: None,
    sink_provider: Callable[[], ReconciliationSink | None] = lambda: None,
    drafts_dir_provider: Callable[[], Path] = _default_drafts_dir,
    now_provider: Callable[[], Callable[[], datetime]] = lambda: _default_utcnow,
) -> None:
    """Register the ``aeat sync run`` command on ``app``.

    The providers are factory callables so unit tests can swap a
    Protocol-conforming :class:`aeat.remote.RemoteFilingFetcher`, a
    Protocol-conforming
    :class:`aeat.cli.sync._reconcile_stage.ReconciliationSink`, a
    deterministic drafts directory, and a frozen clock without touching
    module-level state. The defaults return ``None`` for the fetcher
    and sink so the command preserves the pre-Phase-5 refusal behaviour
    in every environment that has not yet wired a live fetcher.

    Args:
        app: The parent ``aeat sync`` :class:`typer.Typer` instance.
        fetcher_provider: Factory for a live
            :class:`aeat.remote.RemoteFilingFetcher`. Returning ``None``
            skips the reconcile stage; one fetcher (backed by one
            :class:`aeat.auth.AeatSession`) is constructed per
            ``aeat sync run`` invocation.
        sink_provider: Factory for the reconciliation divergence sink.
            Returning ``None`` skips the reconcile stage for the same
            reason the ``fetcher_provider`` default does — there is no
            Kent-facing queue to write into.
        drafts_dir_provider: Factory resolving the directory that holds
            the local :class:`aeat.filing.FilingDraft` JSON corpus.
        now_provider: Factory for the wall-clock callable handed to
            :func:`aeat.filing.reconciliation.reconcile`. The default
            returns a ``datetime.now(tz=UTC)`` closure.
    """

    @app.command(name="run", help="Execute a single live-to-local sync run.")
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

        The command runs the Phase-5 auto-reconcile stage against every
        APPROVED local draft before refusing the rest of the sync run
        until the cross-branch dependencies listed in the ADR ship. The
        bounded auto-heal invariant still applies when the runner
        eventually wires up.
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

            fetcher = fetcher_provider()
            sink = sink_provider()
            if fetcher is not None and sink is not None:
                summary, _reports = asyncio.run(
                    run_reconcile_stage(
                        drafts_dir=drafts_dir_provider(),
                        fetcher=fetcher,
                        sink=sink,
                        now=now_provider(),
                    )
                )
                emit_reconcile_summary(summary, console=_CONSOLE)

            _CONSOLE.print(
                "[yellow]runner prerequisites pending[/yellow]: certificate backend (#8), "
                "corpus loader (#17), schema loader (#9), manual rules (#25), LLM client "
                "(#21). The runner refuses to launch until those branches merge."
            )
            raise typer.Exit(code=2)


__all__ = ["register"]
