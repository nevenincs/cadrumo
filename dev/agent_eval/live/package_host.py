"""Package-side host of the live agent lane, run by the copied package's own interpreter.

The lane's orchestrator never runs a storage step with checkout code. It starts
this file with the copy's ``python.exe -I``, so ``cadrumo`` below is the
package's, and the file imports nothing from ``dev``. Its short subcommands
print one JSON object per line on standard output.

``run-runtime`` is the relay ``serve`` puts between itself and the runtime so
the runtime's standard streams land in files in the control directory.

``serve`` records the runtime installation on the run's fresh root and launches
the packaged runtime the way the manager does, with the manager's arguments
except ``--supervised``, inside a kill-on-close job this process owns. It
publishes readiness and the child environment every packaged process of the
run is given to a control directory beside the root, then holds the runtime
until a stop file appears there. The orchestrator launches this process in a
kill-on-close job of its own, so neither outlives the run.

``active-profile`` names the profile the installation selects, ``surface``
reports the command graph's live-write and filing-handoff leaves,
``parse-export`` parses exported bytes with the product parser under the
package's authority, and ``delete-session`` removes a profile's stored sign-in
at teardown. No secret is read or printed here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import UUID

_READY_SECONDS = 120.0
_POLL_SECONDS = 0.25
READY_FILE = "ready.json"
STOP_FILE = "stop"
STOPPED_FILE = "stopped.json"
RUNTIME_STDOUT_FILE = "runtime.stdout"
RUNTIME_STDERR_FILE = "runtime.stderr"


def _emit(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, sort_keys=True) + "\n")
    sys.stdout.flush()


def _publish(path: Path, event: dict[str, Any]) -> None:
    """Write one control event whole, so a reader never sees half of it."""
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
    partial.replace(path)


def _runtime_image(package: Path) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return package / "bin" / f"cadrumo-runtime{suffix}"


def _wait_ready(endpoint: Any, process: Any, expected: Any) -> None:
    from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
    from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

    deadline = time.monotonic() + _READY_SECONDS
    while True:
        try:
            channel = endpoint.connect(timeout=0.2)
            VerifiedRuntimeConnection(channel, expected=expected, deadline=deadline).close()
            return
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                raise
            try:
                code = process.wait(timeout=0)
            except RuntimeRefusalError as waiting:
                if waiting.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
            else:
                raise RuntimeError(f"the packaged runtime exited before it was ready: {code}") from None
            time.sleep(0.05)


def serve(root: Path, package: Path, control: Path) -> int:
    """Host the packaged runtime on ``root`` until a stop file appears in ``control``."""
    if sys.platform != "win32":
        _publish(control / STOPPED_FILE, {"event": "error", "code": "unsupported_platform", "detail": sys.platform})
        return 2
    from cadrumo.adapters.local_runtime.installation import runtime_installation
    from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
    from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
    from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
    from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
    from cadrumo.domain.calculations.registry.authority_location import published_authority_generation

    product_version = version("cadrumo")
    environment = child_environment(ChildEnvironmentProfile.STRICT, root)
    with ExitStack() as resources:
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        resources.callback(endpoint.close)
        scope = WindowsProcessScope()
        resources.callback(scope.terminate, timeout=15)
        runtime_installation(
            storage_root=root, os_owner_id=endpoint.os_owner_id, storage_identity=endpoint.storage_identity
        )
        image = _runtime_image(package)
        # The launcher hands its child no standard streams, so the runtime runs under a relay in the same job
        # that points them at files in the control area; the relay's exit status is the runtime's.
        process = scope.launch(
            executable=Path(sys.executable),
            arguments=(
                "-I",
                str(Path(__file__).resolve()),
                "run-runtime",
                str(control / RUNTIME_STDOUT_FILE),
                str(control / RUNTIME_STDERR_FILE),
                str(image),
                "--storage-root",
                str(root),
                "--storage-identity",
                endpoint.storage_identity,
                "--expected-version",
                product_version,
            ),
            directory=image.parent,
            environment=environment,
        )
        expected = RuntimeClientHello(
            product_version=product_version,
            storage_identity=endpoint.storage_identity,
            authority_generation=published_authority_generation(),
        )
        _wait_ready(endpoint, process, expected)
        _publish(
            control / READY_FILE,
            {
                "event": "ready",
                "product_version": product_version,
                "authority_generation": str(expected.authority_generation),
                "environment": environment,
            },
        )
        stop = control / STOP_FILE
        while not stop.exists():
            try:
                code = process.wait(timeout=_POLL_SECONDS)
            except RuntimeRefusalError as waiting:
                if waiting.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
            else:
                _publish(control / STOPPED_FILE, {"event": "runtime_exited", "code": code})
                return 1
    _publish(control / STOPPED_FILE, {"event": "stopped"})
    return 0


def run_runtime(stdout: Path, stderr: Path, command: list[str]) -> int:
    """Run the packaged runtime with its standard streams in files, and return its exit status."""

    async def relay() -> int:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            child = await asyncio.create_subprocess_exec(*command, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
            return await child.wait()

    return asyncio.run(relay())


def surface() -> int:
    """Report the leaf tokens of commands whose policy reaches the tax agency, or hands a filing off."""
    from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH

    _emit(
        {
            "event": "surface",
            "live_write": sorted({spec.token for spec in COMMAND_GRAPH.specs if spec.policy.live_write}),
            "handoff": sorted({spec.token for spec in COMMAND_GRAPH.specs if spec.policy.handoff}),
        }
    )
    return 0


def parse_export(file: Path, modelo: str, filing_year: int, period: str) -> int:
    """Parse exported bytes with the product parser under the package's own authority."""
    from cadrumo.application.filing.runtime import build_runtime_schema_provider
    from cadrumo.core.modelo import Modelo
    from cadrumo.core.period import Period
    from cadrumo.domain.calculations.registry.export_parse import parse_export_payload

    payload = file.read_bytes()
    provider = build_runtime_schema_provider(
        modelos=(modelo,), filing_year=filing_year, period=Period.from_year_and_code(filing_year, period)
    )
    layouts = provider.get_subview(Modelo(modelo)).export_layouts
    if not layouts:
        _emit({"event": "error", "code": "export_layout_missing", "detail": f"modelo {modelo} declares no layout"})
        return 1
    parsed = parse_export_payload(
        layouts[0], payload, sources=provider.sources, source_payloads=provider.source_payloads
    )
    _emit(
        {
            "event": "parsed_export",
            "layout_id": str(parsed.layout_id),
            "casillas": {
                str(item.casilla_id): str(item.value)
                for item in parsed.casillas
                if (item.casilla_id is not None and item.casilla_id)
            },
        }
    )
    return 0


def active_profile(root: Path) -> int:
    """Report the profile the installation's pointer selects; the command line prints it only redacted."""
    from cadrumo.core.bucket_pointer import read_pointer

    selected = read_pointer(root).bucket_id
    if selected is None:
        _emit({"event": "error", "code": "no_active_profile", "detail": "no profile is selected"})
        return 1
    _emit({"event": "active_profile", "profile_id": str(UUID(selected))})
    return 0


def delete_session(root: Path, profile_id: UUID) -> int:
    """Remove the profile's stored sign-in, both receipt halves, at teardown."""
    from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session

    delete_profile_session(storage_root=root, profile_id=profile_id)
    _emit({"event": "session_deleted"})
    return 0


def main() -> int:
    """Dispatch one subcommand; report an unexpected failure as one error line."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    serving = commands.add_parser("serve")
    serving.add_argument("--root", type=Path, required=True)
    serving.add_argument("--package", type=Path, required=True)
    serving.add_argument("--control", type=Path, required=True)
    relaying = commands.add_parser("run-runtime")
    relaying.add_argument("stdout", type=Path)
    relaying.add_argument("stderr", type=Path)
    relaying.add_argument("command_line", nargs=argparse.REMAINDER)
    commands.add_parser("surface")
    parsing = commands.add_parser("parse-export")
    parsing.add_argument("--file", type=Path, required=True)
    parsing.add_argument("--modelo", required=True)
    parsing.add_argument("--year", type=int, required=True)
    parsing.add_argument("--period", required=True)
    selecting = commands.add_parser("active-profile")
    selecting.add_argument("--root", type=Path, required=True)
    deleting = commands.add_parser("delete-session")
    deleting.add_argument("--root", type=Path, required=True)
    deleting.add_argument("--profile-id", type=UUID, required=True)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            return serve(
                args.root.resolve(strict=True), args.package.resolve(strict=True), args.control.resolve(strict=True)
            )
        if args.command == "run-runtime":
            return run_runtime(args.stdout, args.stderr, args.command_line)
        if args.command == "surface":
            return surface()
        if args.command == "parse-export":
            return parse_export(args.file, args.modelo, args.year, args.period)
        if args.command == "active-profile":
            return active_profile(args.root.resolve(strict=True))
        return delete_session(args.root.resolve(strict=True), args.profile_id)
    except Exception as error:  # the orchestrator reads this line instead of a traceback
        _emit({"event": "error", "code": type(error).__name__, "detail": str(error)[:500]})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
