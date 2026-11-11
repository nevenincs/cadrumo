"""Run catalogue personas end to end through an installed ``aeat`` and write one receipt per persona.

Each persona gets its own fresh run directory under ``--run-root`` (which must
lie outside any Git tree): a secure store served by the installed runtime it
starts and stops, a work directory for the statement and documents, the
runtime log and ``receipt.json``. A run stops at the first persona whose
runtime stopped answering.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from collections.abc import Sequence
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import persona_ids, read_persona
from dev.acceptance.installed_cli import InstalledCli, authority_generation, build_installed_cli_environment
from dev.packaging.installed_runtime import installed_cli_runtime

from .checks import run_journey
from .journey import Journey, JourneyAbortedError
from .receipt import CliGap, PersonaReceipt

_EXIT_FAILED = 1
_EXIT_ABORTED = 2


def _say(text: str) -> None:
    print(text, flush=True)


def _inside_git_tree(path: Path) -> bool:
    return any((ancestor / ".git").exists() for ancestor in (path, *path.parents))


def _fresh_directory(path: Path) -> Path:
    if path.exists() and any(path.iterdir()):
        raise SystemExit(f"run directory must be fresh and empty: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clock_gap(persona_id: str, as_of: str) -> CliGap:
    return CliGap(
        persona_id,
        "scenario.as_of",
        f"no command or environment variable sets the instant the CLI runs at, so the journey runs at the wall "
        f"clock instead of the persona's as_of {as_of}",
    )


def run_persona(persona_id: str, *, cli: Path, authority_root: Path, run_dir: Path, build: str) -> PersonaReceipt:
    """Run one persona in ``run_dir`` and return its receipt; a stopped runtime is raised after the receipt."""
    store = _fresh_directory(run_dir / "store")
    workdir = _fresh_directory(run_dir / "work")
    with ExitStack() as resources:
        operation = resources.enter_context(
            IndexedRegistryAuthority(authority_root / AUTHORITY_DESCRIPTOR_FILENAME).operation()
        )
        envelope = year_envelope(operation)
        persona = read_persona(persona_id, envelope=envelope)
        installed = InstalledCli(
            cli, storage_root=store, authority_root=authority_root, passphrase=secrets.token_urlsafe(32)
        )
        journey = Journey(persona, envelope, operation, installed, workdir, _say)
        environment = build_installed_cli_environment(storage_root=store, authority_root=authority_root)
        aborted: str | None = None
        obligations, values = (), ()
        try:
            with installed_cli_runtime(cli, environment, run_dir / "caller-owned-runtime.log"):
                obligations, values = run_journey(journey)
        except (JourneyAbortedError, RuntimeError) as error:
            aborted = f"{type(error).__name__}: {error}"
            journey.note(f"journey stopped: {aborted}")
        persona_as_of = persona.as_of.resolve(envelope).isoformat()
        receipt = PersonaReceipt(
            persona=persona.id,
            floor=envelope.floor,
            horizon=envelope.horizon,
            as_of=datetime.now(UTC).isoformat(timespec="seconds"),
            authority_generation=authority_generation(authority_root),
            executable=str(cli),
            build=build,
            steps=tuple(journey.steps),
            cli_gaps=(_clock_gap(persona.id, persona_as_of), *journey.gaps),
            obligations=obligations,
            values=values,
            commands=len(installed.commands),
            notes=tuple(journey.notes),
        )
    (run_dir / "receipt.json").write_text(json.dumps(receipt.to_dict(), indent=2) + "\n", encoding="utf-8")
    if aborted is not None:
        raise JourneyAbortedError(aborted)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected personas; non-zero when one failed an expectation or a runtime stopped."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--persona", required=True, help="a catalogue persona id, or 'all'")
    parser.add_argument("--build", default="", help="the build the executable came from, recorded in each receipt")
    args = parser.parse_args(argv)
    run_root = args.run_root.resolve()
    if _inside_git_tree(run_root):
        parser.error(f"the run root must lie outside any Git tree: {run_root}")
    selected = persona_ids() if args.persona == "all" else (args.persona,)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    failed = False
    for persona_id in selected:
        run_dir = run_root / f"cadrumo-taxfx-{persona_id}-{stamp}"
        try:
            receipt = run_persona(
                persona_id,
                cli=args.cli,
                authority_root=args.authority_root.resolve(),
                run_dir=run_dir,
                build=args.build,
            )
        except JourneyAbortedError as error:
            _say(f"{persona_id} STOPPED {error}; receipt {run_dir / 'receipt.json'}")
            return _EXIT_ABORTED
        failed = failed or not receipt.passed()
        _say(f"{persona_id} {json.dumps(receipt.summary())} receipt {run_dir / 'receipt.json'}")
    return _EXIT_FAILED if failed else 0


if __name__ == "__main__":
    sys.exit(main())
