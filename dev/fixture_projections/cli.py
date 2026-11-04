"""Seed, report, check and clean the generated fixture projections.

``seed`` runs the producer of every stale or missing family and stamps what it
wrote; ``seed --force`` runs every producer. ``status`` reports each family as
fresh, stale (naming the changed inputs) or missing. ``check`` writes no
fixture: it validates the persona catalogue and runs every family's own check.
``check --determinism`` also builds each family that accepts an output
directory twice into scratch to prove the bytes repeat; a full build can take
many minutes, so it is a scheduled or manual proof, not part of the fast check.
``clean`` removes only outputs a family declares generated; committed outputs
are refused, never deleted.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from .._paths import REPO_ROOT, TEMP_ROOT
from ..temporary_output import prepare_temp_root
from .personas import persona_catalogue_findings
from .registry import FAMILIES, OUTPUT, PERSONA_ROOT, PYTHON, Command, FixtureFamily, family_named
from .stamps import (
    FixtureState,
    InputDigests,
    family_inputs,
    family_status,
    output_digests,
    output_paths,
    stamp_path,
    write_stamp,
)

SEED_RECIPE = "just fixtures-seed"


class FixtureProjectionError(RuntimeError):
    """A fixture projection verb cannot proceed."""


def authority_identity() -> dict[str, str]:
    """The published authority's identity: the exact database bytes and the law they record.

    Raises:
        FixtureProjectionError: When no published authority resolves.
    """
    from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
    from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, AuthorityStoreError
    from cadrumo.domain.calculations.registry.errors import AuthorityDescriptorUnavailableError

    try:
        descriptor = AuthorityDescriptor.read(bundled_authority_descriptor_path())
    except (AuthorityDescriptorUnavailableError, AuthorityStoreError, OSError) as exc:
        raise FixtureProjectionError(
            f"No published authority resolves ({type(exc).__name__}); run "
            "`just registry-publish-authority-if-authority-stale` first"
        ) from exc
    return {"database_sha256": descriptor.database_sha256, "logical_generation": descriptor.logical_generation}


def _argv(command: Command, *, output: Path | None = None) -> list[str]:
    resolved = []
    for token in command.argv:
        if token == PYTHON:
            resolved.append(sys.executable)
        elif token == OUTPUT:
            if output is None:
                raise FixtureProjectionError("A command naming an output directory was run without one")
            resolved.append(str(output))
        else:
            resolved.append(token)
    return resolved


def _run(command: Command, *, output: Path | None = None) -> int:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(REPO_ROOT), environment.get("PYTHONPATH", "")) if part
    )
    environment.update(command.environment)
    argv = _argv(command, output=output)
    executable = shutil.which(argv[0])
    if executable is None:
        print(f"  cannot run {argv[0]!r}: not on PATH", file=sys.stderr)
        return 127
    return subprocess.run([executable, *argv[1:]], cwd=REPO_ROOT, env=environment, check=False).returncode


def _unmet_prerequisites(family: FixtureFamily) -> tuple[str, ...]:
    return tuple(
        f"{requirement.path} is absent; run `{requirement.remedy}`"
        for requirement in family.prerequisites
        if not (REPO_ROOT / requirement.path).exists()
    )


def _selected(names: Sequence[str]) -> tuple[FixtureFamily, ...]:
    try:
        return tuple(family_named(name) for name in names) if names else FAMILIES
    except KeyError as exc:
        raise FixtureProjectionError(str(exc.args[0])) from exc


def status(names: Sequence[str]) -> int:
    """Report each family's state; reporting never fails, ``check`` is the gate."""
    digests = InputDigests(REPO_ROOT)
    authority = authority_identity()
    unfresh = False
    for family in _selected(names):
        result = family_status(family, REPO_ROOT, family_inputs(family, digests, authority))
        print(f"{family.name}: {result.state}")
        for reason in result.reasons[:12]:
            print(f"  {reason}")
        if len(result.reasons) > 12:
            print(f"  ... and {len(result.reasons) - 12} more")
        unfresh = unfresh or result.state in {FixtureState.STALE, FixtureState.MISSING}
    if unfresh:
        print(f"Run `{SEED_RECIPE}` to regenerate the families that are not fresh.")
    return 0


def seed(names: Sequence[str], *, force: bool) -> int:
    """Run the producer of each selected family that is not fresh, or of each one under ``force``."""
    digests = InputDigests(REPO_ROOT)
    authority = authority_identity()
    failed: list[str] = []
    for family in _selected(names):
        if family.producer is None:
            continue
        # Inputs are read before the producer runs: an input edited during the
        # run then shows as stale, never as a fresh stamp over older outputs.
        inputs = family_inputs(family, digests, authority)
        current = family_status(family, REPO_ROOT, inputs)
        if current.state is FixtureState.FRESH and not force:
            print(f"{family.name}: fresh")
            continue
        print(f"{family.name}: producing ({current.state})", flush=True)
        unmet = _unmet_prerequisites(family)
        for reason in unmet:
            print(f"  {reason}", file=sys.stderr)
        if unmet or _run(family.producer) != 0:
            failed.append(family.name)
            continue
        if not output_digests(family, REPO_ROOT):
            print(f"  {family.name} produced no declared output", file=sys.stderr)
            failed.append(family.name)
            continue
        write_stamp(family, REPO_ROOT, inputs)
    if failed:
        print(f"Producers failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def _determinism_findings(family: FixtureFamily) -> tuple[str, ...]:
    if family.determinism is None:
        return ()
    stamp = datetime.now(UTC).date().isoformat()
    scratch = prepare_temp_root(override=TEMP_ROOT / f"{stamp}-fixture-projections-{uuid.uuid4().hex[:12]}")
    try:
        trees: list[dict[str, bytes]] = []
        for run in ("first", "second"):
            output = scratch / run
            output.mkdir()
            if _run(family.determinism, output=output) != 0:
                return (f"the {run} determinism build failed",)
            trees.append(
                {path.relative_to(output).as_posix(): path.read_bytes() for path in output.rglob("*") if path.is_file()}
            )
        first, second = trees
        if not first:
            return ("the determinism build wrote nothing",)
        differing = sorted(name for name in first.keys() | second.keys() if first.get(name) != second.get(name))
        return tuple(f"not byte-identical across two builds: {name}" for name in differing)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def check(names: Sequence[str], *, determinism: bool) -> int:
    """Validate the personas, run every selected family's own check and, when asked, prove determinism."""
    started = time.monotonic()
    failures: list[str] = []
    personas = persona_catalogue_findings(REPO_ROOT / PERSONA_ROOT)
    print(f"personas: {'ok' if not personas else 'failed'}")
    for finding in personas:
        print(f"  {finding}")
    if personas:
        failures.append("personas")
    for family in _selected(names):
        family_started = time.monotonic()
        verdict = "ok"
        unmet = _unmet_prerequisites(family)
        for reason in unmet:
            print(f"  {reason}")
        if unmet:
            verdict = "unavailable"
        elif any(_run(command) != 0 for command in family.check):
            verdict = "failed"
        # Determinism is its own finding, so it is proven even when the stored
        # outputs are stale or the check cannot run.
        findings = _determinism_findings(family) if determinism else ()
        for finding in findings:
            print(f"  {finding}")
        if findings:
            proof = "nondeterministic" if findings[0].startswith("not byte-identical") else "determinism unproven"
            verdict = proof if verdict == "ok" else f"{verdict}, {proof}"
        if verdict != "ok":
            failures.append(family.name)
        print(f"{family.name}: {verdict} ({time.monotonic() - family_started:.1f}s)", flush=True)
    print(f"fixtures-check took {time.monotonic() - started:.1f}s")
    if failures:
        print(f"Failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def _removable_targets(family: FixtureFamily) -> list[Path]:
    if family.output_root is None:
        return []
    output_root = (REPO_ROOT / family.output_root).resolve()
    if not output_root.is_relative_to(REPO_ROOT.resolve()) or output_root == REPO_ROOT.resolve():
        raise FixtureProjectionError(f"{family.name}: output root {output_root} is not inside the checkout")
    targets = [*output_paths(family, REPO_ROOT), stamp_path(family, REPO_ROOT)]
    for target in targets:
        if target.is_symlink() or target.is_junction():
            raise FixtureProjectionError(f"{family.name}: refusing to follow the link {target}")
        if not target.resolve().is_relative_to(output_root):
            raise FixtureProjectionError(f"{family.name}: {target} is outside its output root")
    return [target for target in targets if target.exists()]


def clean(names: Sequence[str]) -> int:
    """Remove each selected family's generated outputs; refuse a family whose outputs are committed."""
    refused: list[str] = []
    for family in _selected(names):
        if family.producer is None:
            continue
        if family.committed:
            print(f"{family.name}: refused, its outputs are committed in place")
            refused.append(family.name)
            continue
        targets = _removable_targets(family)
        for target in targets:
            target.unlink()
        print(f"{family.name}: removed {len(targets)} files")
    # A named family that cannot be cleaned is a refusal; a sweep only reports them.
    return 1 if refused and names else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run one fixture projection verb."""
    parser = argparse.ArgumentParser(prog="python -m dev.fixture_projections", description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)
    seeding = verbs.add_parser("seed", help="Produce stale or missing families.")
    seeding.add_argument("--force", action="store_true", help="Produce every selected family.")
    seeding.add_argument("families", nargs="*")
    for verb, summary in (
        ("status", "Report fresh, stale or missing."),
        ("clean", "Remove generated outputs."),
    ):
        verbs.add_parser(verb, help=summary).add_argument("families", nargs="*")
    checking = verbs.add_parser("check", help="Run every check without writing a fixture.")
    checking.add_argument(
        "--determinism", action="store_true", help="Also build each family twice into scratch and compare the bytes."
    )
    checking.add_argument("families", nargs="*")
    args = parser.parse_args(argv)
    try:
        if args.verb == "seed":
            return seed(args.families, force=args.force)
        if args.verb == "status":
            return status(args.families)
        if args.verb == "check":
            return check(args.families, determinism=args.determinism)
        return clean(args.families)
    except FixtureProjectionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
