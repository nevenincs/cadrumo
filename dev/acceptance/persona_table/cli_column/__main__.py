"""Run one persona at one horizon through the installed CLI of a snapshot of the tree, and write the CLI column's lines.

    python -m dev.acceptance.persona_table.cli_column --persona autonomo-alta-reciente --horizon <year> \
        --tree <sha> --snapshot <dir>/snap-<sha> --authority <dir>/authority-<sha> \
        --modelo 130 --modelo 303 --period 1T --out <frontend dir>/cli-<sha>.jsonl

Run it from the snapshot (``PYTHONPATH`` the snapshot's ``src`` and root) with the interpreter that runs the table. It
builds the snapshot into an installed wheel, materialises the persona's world in an interpreter of its own, serves a
fresh ``cadrumo-e2e-*`` root with a caller-owned runtime, drives each return through ``aeat app modelo work ...`` and
appends the intake lines to ``--out``. The snapshot is removed at the end, because the build leaves the publisher's
Google OAuth client in it; ``--keep-snapshot`` keeps it for a failed run. The root is kept, and named, only when a
command left its effect unsettled. ``sweep`` runs many personas and horizons on one build.

The OAuth client comes from ``CADRUMO_GOOGLE_OAUTH_CLIENT_JSON`` in the environment or from ``env/.env`` under
``--client-root``; it enters the wheel build's environment alone and is never written to a line, log or message.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from dev.acceptance.installed_cli import InstalledCliError
from dev.exit_codes import FAILED, OK

from .case import (
    CasePlace,
    CaseSpec,
    add_shared_arguments,
    drive_case,
    finish_case,
    log_dir_for,
    release_snapshot,
    run_redactor,
)
from .driver import CaseSummary
from .hygiene import Redactor, SecretLeakError
from .intake import LineWriter
from .runtime import RuntimeSetupError, build_tree_venv, create_e2e_root, e2e_parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dev.acceptance.persona_table.cli_column", description=__doc__)
    parser.add_argument("--persona", required=True, help="a catalogue persona id")
    parser.add_argument("--horizon", required=True, type=int, help="a supported filing year the replay is run under")
    add_shared_arguments(parser)
    return parser


def _spec(args: argparse.Namespace) -> CaseSpec:
    return CaseSpec(
        args.tree,
        args.persona,
        args.horizon,
        args.snapshot,
        args.authority,
        modelos=tuple(args.modelo),
        periods=tuple(args.period),
    )


def _build_and_drive(args: argparse.Namespace, redactor: Redactor, place: CasePlace) -> CaseSummary:
    log = args.out.resolve().parent / "logs" / f"cli-{args.tree}" / "build.log"
    template = build_tree_venv(args.snapshot, args.authority, args.client_root, redactor, log)
    return drive_case(_spec(args), template, LineWriter(args.out, redactor), redactor, place)


def run(args: argparse.Namespace) -> int:
    """Run the case, always tearing down; the exit code is :data:`OK` when the case ran to its end."""
    redactor = run_redactor()
    args.snapshot, args.authority = args.snapshot.resolve(), args.authority.resolve()
    place = CasePlace(create_e2e_root(e2e_parent()), log_dir_for(args.out, args.tree, args.persona, args.horizon))
    summary = CaseSummary()
    status = FAILED
    try:
        summary = _build_and_drive(args, redactor, place)
        status = OK
    except (RuntimeSetupError, InstalledCliError, SecretLeakError, OSError) as error:
        sys.stderr.write(f"CLI column not run: {redactor.error_text(error)}\n")
    finally:
        notes = [*summary.notes, *finish_case(place, redactor, keep_root=summary.stopped_at is not None)]
        notes.extend(release_snapshot(args.snapshot, keep=args.keep_snapshot))
        for note in notes:
            sys.stderr.write(redactor.text(note) + "\n")
    return status


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the command line and run one case."""
    return run(_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
