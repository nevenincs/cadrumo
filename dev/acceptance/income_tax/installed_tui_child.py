"""Executable installed-TUI bootstrap for the INCOME-01 acceptance runner.

The module is deliberately run by a fresh interpreter whose ``cadrumo``
package came from a built wheel.  It does not inject a workbench root or call
application persistence services.  Instead it drives the production
registration screen, then starts the ordinary installed launcher and reaches
the user-visible profile route.

This is the first installed-composition slice.  Later journey stages reuse the
same child process and its admitted session for ledger and declaration work.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class InstalledTuiChildError(RuntimeError):
    """Raised when the child cannot prove it used installed TUI composition."""

    def __init__(self, message: str, *, diagnostic: dict[str, object] | None = None) -> None:
        """Keep the stable error message and optional sanitized diagnostic."""
        super().__init__(message)
        self.diagnostic = diagnostic


@dataclass(frozen=True, slots=True)
class InstalledTuiBootstrapEvidence:
    """Sanitized result of registration plus one production launcher session."""

    schema_version: str
    stage: str
    product_origin: str
    product_init_sha256: str
    registration: str
    launcher_exit_code: int
    profile_route: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe receipt that contains neither credentials nor facts."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InstalledProductEvidence:
    """Installed-package identity shared by the TUI acceptance children."""

    product_origin: str
    product_init_sha256: str

    def to_dict(self) -> dict[str, object]:
        """Return the value-free installed-package receipt fragment."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InstalledTuiChildProcessEvidence:
    """Sanitized outer-process evidence for one installed TUI child run."""

    child_module: str
    returncode: int
    receipt_status: str
    receipt_sha256: str
    receipt_size: int
    stdout_sha256: str
    stderr_sha256: str

    def to_dict(self) -> dict[str, object]:
        """Return an artifact-oriented receipt fragment with no child output."""
        return asdict(self)


def is_installed_product_origin(*, product_init: Path, workspace_root: Path) -> bool:
    """Return whether ``product_init`` is outside this checkout's source tree.

    A development harness may stay in the checkout so it can be changed and
    reviewed, but an installed acceptance claim is false if the product itself
    imports from ``<checkout>/src/cadrumo``.
    """
    resolved_product = product_init.resolve()
    source_package = (workspace_root.resolve() / "src" / "cadrumo").resolve()
    return not resolved_product.is_relative_to(source_package)


def assert_installed_product_origin(*, workspace_root: Path) -> Path:
    """Require the child interpreter to load ``cadrumo`` from site-packages."""
    import cadrumo

    product_init = Path(cadrumo.__file__ or "").resolve()
    if not product_init.exists() or not is_installed_product_origin(
        product_init=product_init,
        workspace_root=workspace_root,
    ):
        raise InstalledTuiChildError("installed TUI child imported cadrumo from the checkout source tree")
    if "site-packages" not in {part.casefold() for part in product_init.parts}:
        raise InstalledTuiChildError("installed TUI child product origin is not a site-packages wheel installation")
    return product_init


def installed_product_evidence(*, workspace_root: Path) -> InstalledProductEvidence:
    """Assert installed composition and return its durable identity fragment."""
    product_init = assert_installed_product_origin(workspace_root=workspace_root)
    return InstalledProductEvidence(
        product_origin="site-packages",
        product_init_sha256=hashlib.sha256(product_init.read_bytes()).hexdigest(),
    )


async def _wait_for_selector(pilot: Any, selector: str, *, polls: int = 80) -> None:
    """Wait for a visible public control without reaching into app routing."""
    from textual.css.query import NoMatches

    for _ in range(polls):
        try:
            _query_public_selector(pilot, selector)
        except NoMatches:
            await pilot.pause()
        else:
            return
    raise InstalledTuiChildError(
        f"installed TUI did not expose {selector}",
        diagnostic=_public_surface_diagnostic(pilot),
    )


async def _wait_for_any_selector(pilot: Any, selectors: tuple[str, ...], *, polls: int = 80) -> str:
    """Wait for one public surface in an admitted installed-session branch."""
    from textual.css.query import NoMatches

    for _ in range(polls):
        for selector in selectors:
            try:
                _query_public_selector(pilot, selector)
            except NoMatches:
                continue
            else:
                return selector
        await pilot.pause()
    expected = ", ".join(selectors)
    raise InstalledTuiChildError(
        f"installed TUI did not expose one of: {expected}",
        diagnostic=_public_surface_diagnostic(pilot),
    )


def _public_surface_diagnostic(pilot: Any) -> dict[str, object]:
    """Return a value-free description of the mounted public TUI surface."""
    screen = pilot.app.screen
    widget_ids = sorted(
        {
            widget_id
            for scope in (pilot.app, screen)
            for widget in scope.query("*")
            if isinstance(widget_id := getattr(widget, "id", None), str)
        }
    )
    return {
        "current_screen_class": type(screen).__name__,
        "current_screen_id": screen.id,
        "mounted_widget_ids": widget_ids,
    }


def _query_public_selector(pilot: Any, selector: str, expected_type: type[Any] | None = None) -> object:
    """Resolve a public selector from the root, then the pushed public screen."""
    from textual.css.query import NoMatches

    def query(scope: Any) -> object:
        if expected_type is None:
            return scope.query_one(selector)
        return scope.query_one(selector, expected_type)

    try:
        return query(pilot.app)
    except NoMatches:
        return query(pilot.app.screen)


# These public aliases are the only driver primitives shared with subsequent
# financial and continuation children.  They intentionally expose controls and
# rendered screen identity, never a workbench service or persisted payload.
wait_for_public_selector = _wait_for_selector
wait_for_any_public_selector = _wait_for_any_selector
public_surface_diagnostic = _public_surface_diagnostic
query_public_selector = _query_public_selector


async def _register_via_production_screen(*, profile_label: str, passphrase: str) -> None:
    """Create and unlock one profile through the actual installed screen.

    The callbacks are the same production callbacks that
    ``run_installed_workbench_session`` supplies.  Direct profile creation is
    intentionally absent from this harness.
    """
    from textual.widgets import Input

    from cadrumo.core.credentials import assess_profile_password
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.secret.registration import (
        RegistrationScreen,
        build_profile_recovery_enrollment_attempt,
        build_profile_registration_attempt,
    )

    screen = RegistrationScreen(
        assess=assess_profile_password,
        register=build_profile_registration_attempt,
        enroll_recovery=build_profile_recovery_enrollment_attempt,
    )
    app = ScreenHostApp(screen)
    async with app.run_test(size=(160, 60)) as pilot:
        await pilot.pause()
        screen.query_one("#field-username", Input).value = profile_label
        screen.query_one("#field-password", Input).value = passphrase
        screen.query_one("#field-confirm", Input).value = passphrase
        await pilot.click("#btn-create")
        await pilot.app.workers.wait_for_complete()
        await _wait_for_selector(pilot, "#btn-skip-recovery")
        await pilot.click("#btn-skip-recovery")
        await pilot.pause()
    if screen.outcome is None:
        raise InstalledTuiChildError("registration screen closed without an admitted profile")


register_profile_through_installed_tui = _register_via_production_screen


async def admit_installed_session(*, pilot: Any, passphrase: str) -> None:
    """Unlock an installed session through its visible admission surface.

    A newly registered profile can reach either the Login screen or an already
    admitted Home screen depending on the surrounding production composition.
    Both branches remain ordinary public TUI interactions.
    """
    from textual.widgets import Input

    initial_surface = await wait_for_any_public_selector(
        pilot,
        ("#field-passphrase", "#home-agenda"),
        polls=180,
    )
    if initial_surface == "#field-passphrase":
        query_public_selector(pilot, "#field-passphrase", Input).value = passphrase
        await pilot.click("#btn-unlock")
    await wait_for_public_selector(pilot, "#home-agenda", polls=180)


def admitted_session_autopilot(
    *,
    passphrase: str,
    drive_after_home: Callable[[Any], Awaitable[None]],
):
    """Build a launcher callback that admits, then delegates real TUI work."""

    async def drive(pilot: Any) -> None:
        await admit_installed_session(pilot=pilot, passphrase=passphrase)
        await drive_after_home(pilot)

    return drive


async def open_profile_manager_field(*, pilot: Any, path: str) -> None:
    """Open one visible Profile Manager row by its canonical fact path.

    Manager section tables deliberately have no per-field widget IDs.  Their
    public row keys are canonical schema paths, which is stable across
    translated labels and section row ordering.  This helper scans only the
    mounted ``DataTable`` controls, focuses the matching visible row, and uses
    the normal Enter interaction to open the editor.
    """
    from textual.widgets import DataTable

    if not isinstance(path, str) or not path:
        raise InstalledTuiChildError("Profile Manager field path must be a non-empty canonical path")
    for table in pilot.app.screen.query(DataTable):
        for row_key in table.rows:
            if str(row_key.value) != path:
                continue
            table.focus()
            table.move_cursor(row=table.get_row_index(row_key))
            await pilot.press("enter")
            return
    raise InstalledTuiChildError(
        f"installed Profile Manager did not expose canonical field {path}",
        diagnostic=public_surface_diagnostic(pilot),
    )


async def select_public_data_table_row(*, pilot: Any, table_selector: str, row_key: str) -> None:
    """Select a visible DataTable row by its stable public semantic key."""
    from textual.widgets import DataTable

    if not isinstance(table_selector, str) or not table_selector.startswith("#"):
        raise InstalledTuiChildError("installed TUI table selector must be a public widget ID")
    if not isinstance(row_key, str) or not row_key:
        raise InstalledTuiChildError("installed TUI DataTable row key must be a non-empty semantic key")
    await wait_for_public_selector(pilot, table_selector)
    table = query_public_selector(pilot, table_selector, DataTable)
    for candidate in table.rows:
        if str(candidate.value) != row_key:
            continue
        table.focus()
        table.move_cursor(row=table.get_row_index(candidate))
        await pilot.press("enter")
        return
    raise InstalledTuiChildError(
        f"installed TUI table {table_selector} did not expose row key {row_key}",
        diagnostic=public_surface_diagnostic(pilot),
    )


async def set_profile_manager_field(*, pilot: Any, path: str, value: str) -> None:
    """Persist one text or enum profile value through the normal editor UI."""
    from textual.widgets import Input, Select

    await open_profile_manager_field(pilot=pilot, path=path)
    editor = await wait_for_any_public_selector(pilot, ("#edit-input", "#edit-options"))
    if editor == "#edit-input":
        query_public_selector(pilot, editor, Input).value = value
    else:
        query_public_selector(pilot, editor, Select).value = value
    await pilot.click("#btn-edit-save")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#manager-status")


def _profile_route_autopilot(*, observed: list[str], passphrase: str):
    """Return one real-pilot callback that unlocks and reaches Profile.

    Registration creates the profile through its own production screen.  The
    subsequent installed launcher deliberately owns a separate credential
    admission, so this pilot supplies the same stdin-only secret through the
    visible Login screen rather than assuming registration leaked a session
    into the new launcher composition.
    """

    async def drive(pilot: Any) -> None:
        await admit_installed_session(pilot=pilot, passphrase=passphrase)
        await pilot.press("f4")
        await wait_for_public_selector(pilot, "#manager-status", polls=180)
        observed.append("workbench.profile")
        pilot.app.exit()

    return drive


def run_bootstrap(*, workspace_root: Path, profile_label: str, passphrase: str) -> InstalledTuiBootstrapEvidence:
    """Run the visible registration and production-launcher bootstrap once."""
    product = installed_product_evidence(workspace_root=workspace_root)

    # This mirrors the installed-session composition around its registration
    # door.  The subsequent launcher has its own normal existing-session
    # admission, which the visible Login/Home branch above handles.
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition
    from cadrumo.entrypoints.tui.launcher import main

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(_register_via_production_screen(profile_label=profile_label, passphrase=passphrase))

    observed: list[str] = []
    exit_code = main(headless=True, auto_pilot=_profile_route_autopilot(observed=observed, passphrase=passphrase))
    if exit_code != 0:
        raise InstalledTuiChildError(f"production launcher returned {exit_code}")
    if observed != ["workbench.profile"]:
        raise InstalledTuiChildError("production launcher did not reach the visible profile route")
    return InstalledTuiBootstrapEvidence(
        schema_version="income-01-installed-tui-bootstrap-v1",
        stage="registration_then_production_launcher_profile_route",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        registration="proven",
        launcher_exit_code=exit_code,
        profile_route="proven",
    )


def _read_passphrase_from_stdin() -> str:
    """Read exactly the credential transport contract without echoing it."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise InstalledTuiChildError("credential stdin is not one JSON object") from exc
    if not isinstance(payload, dict):
        raise InstalledTuiChildError("credential stdin is not one JSON object")
    passphrase = payload.get("profile_passphrase")
    if not isinstance(passphrase, str) or not passphrase:
        raise InstalledTuiChildError("credential stdin has no profile_passphrase")
    return passphrase


read_passphrase_from_stdin = _read_passphrase_from_stdin


def write_installed_tui_failure_receipt(
    *,
    path: Path,
    schema_version: str,
    error: InstalledTuiChildError,
) -> None:
    """Persist only a sanitized child failure receipt for another driver."""
    failure: dict[str, object] = {
        "schema_version": schema_version,
        "status": "failed",
        "error": str(error),
    }
    if error.diagnostic is not None:
        failure["diagnostic"] = _sanitized_public_diagnostic(error.diagnostic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sanitized_public_diagnostic(diagnostic: dict[str, object]) -> dict[str, object]:
    """Keep a durable failure diagnostic to public screen identity only."""
    sanitized: dict[str, object] = {}
    current_class = diagnostic.get("current_screen_class")
    if isinstance(current_class, str):
        sanitized["current_screen_class"] = current_class
    current_id = diagnostic.get("current_screen_id")
    if isinstance(current_id, str) or current_id is None:
        sanitized["current_screen_id"] = current_id
    widget_ids = diagnostic.get("mounted_widget_ids")
    if isinstance(widget_ids, list) and all(isinstance(item, str) for item in widget_ids):
        sanitized["mounted_widget_ids"] = sorted(set(widget_ids))
    return sanitized


def run_installed_tui_child_process(
    *,
    python_executable: Path,
    workspace_root: Path,
    child_module: str,
    child_args: Sequence[str],
    storage_root: Path,
    receipt_path: Path,
    passphrase: str,
    authority_root: Path | None = None,
    timeout_seconds: int = 240,
) -> InstalledTuiChildProcessEvidence:
    """Run a development child against an installed product interpreter.

    The workspace is present only to make the reviewed development module
    importable.  The child itself asserts that ``cadrumo`` came from
    site-packages.  Product environment variables are rebuilt from scratch,
    and the credential crosses the process boundary only through stdin.
    """
    executable = python_executable.resolve(strict=True)
    workspace = workspace_root.resolve(strict=True)
    receipt = receipt_path.resolve()
    store = storage_root.resolve()
    if receipt.exists():
        raise InstalledTuiChildError("installed TUI child receipt path must be fresh")
    if not child_module or any(not isinstance(argument, str) for argument in child_args):
        raise InstalledTuiChildError("installed TUI child module and arguments must be strings")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CADRUMO_") and key != "PYTHONPATH"
    }
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(store),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    if authority_root is not None:
        environment["CADRUMO_AUTHORITY_ROOT"] = str(authority_root.resolve(strict=True))
    completed = subprocess.run(  # noqa: S603 - executable is an explicit acceptance input
        [str(executable), "-m", child_module, *child_args],
        check=False,
        capture_output=True,
        cwd=workspace,
        env=environment,
        input=json.dumps({"profile_passphrase": passphrase}, separators=(",", ":")),
        text=True,
        timeout=timeout_seconds,
        encoding="utf-8",
    )
    if not receipt.is_file():
        raise InstalledTuiChildError(
            f"installed TUI child {child_module} exited without a durable receipt",
        )
    receipt_bytes = receipt.read_bytes()
    try:
        receipt_document = json.loads(receipt_bytes)
    except json.JSONDecodeError as exc:
        raise InstalledTuiChildError(f"installed TUI child {child_module} wrote non-JSON receipt") from exc
    status = receipt_document.get("status") if isinstance(receipt_document, dict) else None
    if not isinstance(status, str) or not status:
        raise InstalledTuiChildError(f"installed TUI child {child_module} receipt has no status")
    return InstalledTuiChildProcessEvidence(
        child_module=child_module,
        returncode=completed.returncode,
        receipt_status=status,
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
        receipt_size=len(receipt_bytes),
        stdout_sha256=hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        stderr_sha256=hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the installed INCOME-01 TUI bootstrap child.")
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--profile-label", default="income-tui-acceptance")
    parser.add_argument("--receipt", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the child and write a sanitised receipt on success."""
    args = _parser().parse_args(argv)
    try:
        evidence = run_bootstrap(
            workspace_root=args.workspace_root,
            profile_label=args.profile_label,
            passphrase=_read_passphrase_from_stdin(),
        )
    except InstalledTuiChildError as exc:
        # The caller records this stable class message; no raw screen state,
        # passphrase, or profile payload reaches the durable receipt.
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version="income-01-installed-tui-bootstrap-v1",
            error=exc,
        )
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True))
        return 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(evidence.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "proven", "stage": evidence.stage}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())


__all__ = [
    "InstalledProductEvidence",
    "InstalledTuiBootstrapEvidence",
    "InstalledTuiChildError",
    "InstalledTuiChildProcessEvidence",
    "admit_installed_session",
    "admitted_session_autopilot",
    "assert_installed_product_origin",
    "installed_product_evidence",
    "is_installed_product_origin",
    "main",
    "open_profile_manager_field",
    "public_surface_diagnostic",
    "query_public_selector",
    "read_passphrase_from_stdin",
    "register_profile_through_installed_tui",
    "run_bootstrap",
    "run_installed_tui_child_process",
    "select_public_data_table_row",
    "set_profile_manager_field",
    "wait_for_any_public_selector",
    "wait_for_public_selector",
    "write_installed_tui_failure_receipt",
]
