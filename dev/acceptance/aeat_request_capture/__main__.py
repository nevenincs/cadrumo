"""List the planned AEAT read flows, or run them live under an explicit flag.

Without the flag, a run prints the plan and stops before any product or browser
code is imported. Only the listed flows can run: a selector that names anything
else, such as opening a notification document, is refused.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final
from uuid import uuid4

from dev.paths import REPO_ROOT, TEMP_ROOT

from .flows import ReadFlow, UnknownFlowSelectorError, select_flows

LIVE_FLAG: Final = "--live-aeat-read-capture"
EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_REFUSED: Final = 2
_DEFAULT_MODELO: Final = "100"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dev.acceptance.aeat_request_capture", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="List the flows a run would drive; contacts nothing.")
    run = commands.add_parser("run", help=f"Drive the flows against live AEAT; refuses without {LIVE_FLAG}.")
    for command in (plan, run):
        command.add_argument(
            "--select",
            action="append",
            default=[],
            help="A flow id, CLI command or aeat_live test id; repeatable. Default: every flow.",
        )
    run.add_argument(LIVE_FLAG, action="store_true", help="Authorise contact with AEAT and Cl@ve, phone in hand.")
    run.add_argument("--env-file", type=Path, help="Env file to read when this worktree has no env/.env.")
    run.add_argument("--modelo", default=_DEFAULT_MODELO, help="Modelo for the filed-declarations query.")
    run.add_argument(
        "--year",
        type=int,
        default=None,
        help="Ejercicio for that query. Default: the earliest filing year the pinned authority supports.",
    )
    return parser


def _print_plan(flows: Sequence[ReadFlow]) -> None:
    for flow in flows:
        print(f"{flow.flow_id}\n  command: {flow.cli_command}\n  reader: {flow.reader}")
        print(f"  policies: {', '.join(flow.policy_ids)}\n  read-only: {flow.read_only_because}")


def _missing_configuration(settings: object) -> list[str]:
    required = {
        "CADRUMO_CLAVE_MOVIL_DNI_NIE": "cadrumo_clave_movil_dni_nie",
        "CADRUMO_CLAVE_MOVIL_NIE_SOPORTE": "cadrumo_clave_movil_nie_soporte",
    }
    return [name for name, attribute in required.items() if not getattr(settings, attribute, None)]


def _authority_floor_year() -> int:
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years().floor


def _run_live(flows: Sequence[ReadFlow], arguments: argparse.Namespace) -> int:
    # Secrets reach the environment before the settings first read it.
    from cadrumo.tests.env_loader import bridge_env_file_into_environ

    bridge_env_file_into_environ(arguments.env_file or REPO_ROOT / "env" / ".env")

    from cadrumo.core.config import load_settings

    settings = load_settings()
    missing = _missing_configuration(settings)
    if missing:
        print(f"Refused before any browser: not configured: {', '.join(missing)}", file=sys.stderr)
        return EXIT_REFUSED
    if settings.cadrumo_wallet_diagnostic_dump_dir is not None:
        print("Refused: CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR would write raw pages to disk; unset it.", file=sys.stderr)
        return EXIT_REFUSED

    from cadrumo.application.browser_location import playwright_browsers_root

    if not any(playwright_browsers_root(settings=settings).glob("chromium-*")):
        print("Refused before any browser: Chromium is not provisioned; run `just setup-browser`.", file=sys.stderr)
        return EXIT_REFUSED

    from .live_flows import LIVE_DRIVERS, run_live_capture

    output = TEMP_ROOT / f"{date.today():%Y-%m-%d}-aeat-request-capture-{uuid4().hex[:8]}" / "request-capture.json"
    print(f"Report: {output}")
    recorder = run_live_capture(
        flows,
        LIVE_DRIVERS,
        settings=settings,
        modelo=arguments.modelo,
        ejercicio=arguments.year if arguments.year is not None else _authority_floor_year(),
        profile_base=TEMP_ROOT / "live-tests",
        output=output,
        show=lambda line: print(line, file=sys.stderr, flush=True),
    )
    if recorder.notification_detail_requests:
        print("A notification detail request was attempted; review the report.", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return its exit status."""
    arguments = _parser().parse_args(argv)
    try:
        flows = select_flows(arguments.select)
    except UnknownFlowSelectorError as refusal:
        print(f"Refused: {refusal}", file=sys.stderr)
        return EXIT_REFUSED
    _print_plan(flows)
    if arguments.command == "plan":
        return EXIT_OK
    if not arguments.live_aeat_read_capture:
        print(f"Refused: nothing was started. Pass {LIVE_FLAG} to contact AEAT and Cl@ve.", file=sys.stderr)
        return EXIT_REFUSED
    return _run_live(flows, arguments)


if __name__ == "__main__":
    sys.exit(main())
