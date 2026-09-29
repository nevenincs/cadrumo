"""Profile-free CLI presentation of installed runtime management."""

from __future__ import annotations

import asyncio

import typer

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ..runtime_management import (
    configure_installed_runtime_management,
    inspect_installed_runtime_management,
    preview_installed_runtime_stop,
    start_installed_runtime_management,
)
from .app_runtime_payloads import RuntimeManagerConfigResult, RuntimeStatusResult, RuntimeStopResult
from .common import emit_envelope
from .errors import CliRefusedBoundaryError


def runtime_root(ctx: typer.Context) -> None:
    """Show the runtime management command group when no action was selected."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def runtime_status(ctx: typer.Context) -> None:
    """Observe the local listener and manager without admission or startup."""
    try:
        snapshot = asyncio.run(inspect_installed_runtime_management(timeout=3))
    except RuntimeRefusalError as refusal:
        raise CliRefusedBoundaryError(context={"reason": refusal.reason.value}) from refusal
    result = RuntimeStatusResult(
        listener=snapshot.listener,
        manager_availability=snapshot.manager_availability,
        manager=snapshot.manager,
    )
    lines = [f"listener\t{result.listener.value}", f"manager_availability\t{result.manager_availability.value}"]
    if result.manager is not None:
        manager = result.manager
        lines.extend(
            (
                f"manager_kind\t{manager.kind.value}",
                f"manager_available\t{str(manager.available).lower()}",
                f"manager_provisioned\t{str(manager.provisioned).lower()}",
                f"manager_binding_matches\t{str(manager.binding_matches).lower()}",
                f"manager_login_autostart\t{str(manager.login_autostart).lower()}",
                f"manager_process_state\t{manager.process_state.value}",
            )
        )
    emit_envelope(ctx, command="app.runtime.status", result=result, lines=lines)


def runtime_start(ctx: typer.Context) -> None:
    """Explicitly request the existing installed runtime and verify readiness."""
    try:
        snapshot = asyncio.run(start_installed_runtime_management())
    except RuntimeRefusalError as refusal:
        raise CliRefusedBoundaryError(context={"reason": refusal.reason.value}) from refusal
    result = RuntimeStatusResult(
        listener=snapshot.listener,
        manager_availability=snapshot.manager_availability,
        manager=snapshot.manager,
    )
    emit_envelope(ctx, command="app.runtime.start", result=result, lines=[f"listener\t{result.listener.value}"])


def _runtime_configure(ctx: typer.Context, *, login_autostart: bool) -> None:
    try:
        manager = asyncio.run(configure_installed_runtime_management(login_autostart=login_autostart))
    except RuntimeRefusalError as refusal:
        raise CliRefusedBoundaryError(context={"reason": refusal.reason.value}) from refusal
    result = RuntimeManagerConfigResult(manager=manager)
    command = "app.runtime.enable" if login_autostart else "app.runtime.disable"
    emit_envelope(
        ctx,
        command=command,
        result=result,
        lines=(
            f"manager_provisioned\t{str(manager.provisioned).lower()}",
            f"manager_binding_matches\t{str(manager.binding_matches).lower()}",
            f"manager_login_autostart\t{str(manager.login_autostart).lower()}",
        ),
    )


def runtime_enable(ctx: typer.Context) -> None:
    """Provision or enable login startup without starting the runtime now."""
    _runtime_configure(ctx, login_autostart=True)


def runtime_disable(ctx: typer.Context) -> None:
    """Provision on-demand startup or disable the existing login trigger."""
    _runtime_configure(ctx, login_autostart=False)


def runtime_stop(ctx: typer.Context, *, acknowledge_all_profiles_and_work: bool = False) -> None:
    """Preview and acknowledge a shared-runtime stop on one owner connection."""
    if not acknowledge_all_profiles_and_work:
        raise CliRefusedBoundaryError(context={"reason": RuntimeRefusalCode.INVALID_FRAME.value})

    async def stop() -> RuntimeStopResult:
        consent = await preview_installed_runtime_stop()
        try:
            accepted = await consent.confirm()
            return RuntimeStopResult(runtime_boot_id=accepted.runtime_boot_id, scope=accepted.scope)
        finally:
            consent.close()

    try:
        result = asyncio.run(stop())
    except RuntimeRefusalError as refusal:
        raise CliRefusedBoundaryError(context={"reason": refusal.reason.value}) from refusal
    emit_envelope(ctx, command="app.runtime.stop", result=result, lines=[f"scope\t{result.scope}"])


__all__ = ["runtime_disable", "runtime_enable", "runtime_root", "runtime_start", "runtime_status", "runtime_stop"]
