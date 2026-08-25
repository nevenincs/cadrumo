"""Fail-closed publication leak sweep for runner metadata.

:class:`~dev.packaging.evidence.DistributionEvidence` rows carry runtime
identity fields and command transcripts in which runner hostnames, operating
system usernames (inside absolute paths) and machine identifiers can appear.
Publishing those verbatim on the public ``v<version>`` release would leak
operator machine metadata, so the evidence builders redact at mint time and
refuse the mint outright on any residual identifier.

This module is the tripwire ABOVE those builders: the publication gate sweeps
every asset it is about to attach and refuses the promotion, naming the asset
and the pattern, if anything survived. It exists for payloads the builders did
not mint — archived transcripts, bundled cohort files — and as a regression
ratchet if a new metadata field ever slips past them. It NEVER rewrites: this
is verify-then-refuse.

Inter-workflow payloads ride Actions artifacts, which are intrinsically bound
to their producing run, so nothing here touches the GitHub releases API. An
earlier design moved those payloads onto per-run draft releases to dodge an
artifact-storage quota on a private Free plan, and this module carried the
seal, verify and garbage-collect verbs that transport needed; the repository is
public, that storage is free, and those verbs went with the drafts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import iter_directory, scan_directory

from .._paths import UTF_8

_UTF_8: Final = UTF_8


class EvidenceLeakSweepError(RuntimeError):
    """A publication asset still carries runner metadata, or cannot be read."""


def sweep_directory_for_leaks(directory: Path, *, tokens: tuple[str, ...] = ()) -> list[str]:
    """Return every runner-metadata leak signature across a publication directory.

    JSON files are walked structurally (field-agnostic, exactly the mint-time
    detector); every other file is scanned as text — latin-1 decoded when not
    UTF-8, so plain strings inside uncompressed binaries are still seen. An
    unreadable JSON file is reported as a refusal rather than skipped, because
    a payload the sweep cannot inspect is a payload it cannot clear.
    """
    from .evidence_scrub import find_residual_leaks

    if not directory.is_dir():
        raise EvidenceLeakSweepError(f"leak-sweep directory does not exist: {directory}")
    leaks: list[str] = []
    for path in (p for p in scan_directory(directory, recursive=True) if p.is_file()):
        label = path.relative_to(directory).as_posix()
        document: dict[str, object]
        if path.suffix == ".json":
            try:
                document = {"document": json.loads(path.read_text(encoding=_UTF_8))}
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                leaks.append(f"{label}: unparseable JSON refused ({error})")
                continue
        else:
            try:
                text = path.read_text(encoding=_UTF_8)
            except UnicodeDecodeError:
                text = path.read_bytes().decode("latin-1")
            document = {"lines": text.splitlines()}
        leaks.extend(f"{label}{leak}" for leak in find_residual_leaks(document, tokens))
    return leaks


def _leak_sweep(args: argparse.Namespace) -> int:
    directories: list[Path] = args.directory
    tokens = tuple(args.token or ())
    leaks = [
        f"{directory}: {leak}"
        for directory in directories
        for leak in sweep_directory_for_leaks(directory, tokens=tokens)
    ]
    if leaks:
        raise EvidenceLeakSweepError(
            "publication leak sweep failed:\n" + "\n".join(f"  - {leak}" for leak in leaks),
        )
    files = sum(1 for directory in directories for path in iter_directory(directory, recursive=True) if path.is_file())
    print(f"leak sweep clean: {files} file(s) under {len(directories)} directory(ies)")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refuse publication assets carrying runner metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sweep = subparsers.add_parser(
        "leak-sweep",
        help="Refuse any asset about to be published that still carries runner metadata.",
    )
    sweep.add_argument(
        "--directory",
        required=True,
        action="append",
        type=Path,
        help="Directory of publication assets to sweep (repeatable).",
    )
    sweep.add_argument(
        "--token",
        action="append",
        default=None,
        help="Additional literal token that must not appear in any asset (repeatable).",
    )
    sweep.set_defaults(handler=_leak_sweep)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the requested sweep and return its exit code."""
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except EvidenceLeakSweepError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
