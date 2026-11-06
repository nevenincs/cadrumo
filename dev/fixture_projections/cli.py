"""Seed, report, check and clean the generated fixture projections.

``seed`` runs the producer of every family that is not fresh and stamps what it
wrote; ``seed --force`` runs every producer. A family whose outputs exist but
carry no stamp is adopted instead when its check proves their bytes: the check
passes, the outputs are stamped and nothing is produced. ``status`` reports
each family as fresh, stale (naming the changed inputs), unstamped or missing.
``check`` writes no fixture: it validates the persona catalogue and runs every
family's own check. ``check --determinism`` also builds each producer family
twice into scratch to prove the bytes repeat, and reports a family that
declares no such build as ``determinism undeclared``; a full build can take
many minutes, so it is a scheduled or manual proof, not part of the fast check.
``clean`` removes only outputs a family declares generated; committed outputs
are refused, never deleted.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..packaging.command_execution import run_command
from ..paths import REPO_ROOT, TEMP_ROOT
from ..temporary_output import prepare_temp_root
from .registry import (
    FAMILIES,
    OUTPUT,
    PERSONA_ROOT,
    PYTHON,
    RECORDING_SWITCHES,
    Command,
    FixtureFamily,
    family_named,
    window_families,
)
from .stamps import (
    FixtureState,
    InputDigests,
    InputRecord,
    family_inputs,
    family_status,
    output_digests,
    output_paths,
    stamp_path,
    write_stamp,
)

SEED_RECIPE = "just fixtures-seed"
DETERMINISM_UNDECLARED = "determinism undeclared"


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


def _repository_persona_check() -> tuple[str, ...]:
    from .personas import persona_catalogue_findings

    return persona_catalogue_findings(REPO_ROOT / PERSONA_ROOT)


@dataclass(frozen=True, slots=True)
class Workspace:
    """Where the verbs act: the checkout, its families and the checks and stores they consult."""

    root: Path = REPO_ROOT
    families: tuple[FixtureFamily, ...] = FAMILIES
    authority: Callable[[], Mapping[str, str]] = authority_identity
    persona_check: Callable[[], tuple[str, ...]] = _repository_persona_check
    cache_directory: Path | None = None
    scratch_root: Path = TEMP_ROOT


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


def child_environment(command: Command, root: Path, inherited: Mapping[str, str]) -> dict[str, str]:
    """The environment a command runs in: the inherited one without any recording switch, plus its own entries."""
    environment = {name: value for name, value in inherited.items() if name not in RECORDING_SWITCHES}
    environment["PYTHONPATH"] = os.pathsep.join(
        dict.fromkeys(part for part in (str(root), str(REPO_ROOT), environment.get("PYTHONPATH", "")) if part)
    )
    environment.update(command.environment)
    return environment


def _run(workspace: Workspace, command: Command, *, output: Path | None = None) -> int:
    argv = _argv(command, output=output)
    executable = shutil.which(argv[0])
    if executable is None:
        print(f"  cannot run {argv[0]!r}: not on PATH", file=sys.stderr)
        return 127
    return run_command(
        [executable, *argv[1:]],
        cwd=workspace.root,
        environment=child_environment(command, workspace.root, os.environ),
        inherit_output=True,
    ).returncode


def _unmet_prerequisites(workspace: Workspace, family: FixtureFamily) -> tuple[str, ...]:
    return tuple(
        f"{requirement.path} is absent; run `{requirement.remedy}`"
        for requirement in family.prerequisites
        if not (workspace.root / requirement.path).exists()
    )


def _selected(workspace: Workspace, names: Sequence[str], *, window: bool = False) -> tuple[FixtureFamily, ...]:
    if window:
        # A build that imports the window projections names no family; an empty
        # selection would let it go on to meet missing modules.
        if names:
            raise FixtureProjectionError("Name families or select the window projections, not both")
        selected = window_families(workspace.families)
        if not selected:
            raise FixtureProjectionError("No generated family writes the window projections")
        return selected
    try:
        return tuple(family_named(name, workspace.families) for name in names) if names else workspace.families
    except KeyError as exc:
        raise FixtureProjectionError(str(exc.args[0])) from exc


def _inputs(family: FixtureFamily, digests: InputDigests, authority: Mapping[str, str]) -> InputRecord:
    try:
        return family_inputs(family, digests, authority)
    except FileNotFoundError as exc:
        raise FixtureProjectionError(f"{family.name}: {exc}") from exc


def status(names: Sequence[str], workspace: Workspace | None = None) -> int:
    """Report each family's state; reporting never fails, ``check`` is the gate."""
    workspace = workspace or Workspace()
    digests = InputDigests(workspace.root)
    authority = workspace.authority()
    unfresh = False
    for family in _selected(workspace, names):
        inputs = _inputs(family, digests, authority)
        result = family_status(family, workspace.root, inputs, cache_directory=workspace.cache_directory)
        print(f"{family.name}: {result.state}")
        for reason in result.reasons[:12]:
            print(f"  {reason}")
        if len(result.reasons) > 12:
            print(f"  ... and {len(result.reasons) - 12} more")
        unfresh = unfresh or result.state in {FixtureState.STALE, FixtureState.UNSTAMPED, FixtureState.MISSING}
    if unfresh:
        print(f"Run `{SEED_RECIPE}` to regenerate the families that are not fresh.")
    return 0


def _adopted(workspace: Workspace, family: FixtureFamily, inputs: InputRecord) -> bool:
    """Stamp unstamped outputs when the family's check proves their bytes; produce nothing."""
    print(f"{family.name}: checking its unstamped outputs", flush=True)
    if not all(_run(workspace, command) == 0 for command in family.check):
        print(f"  {family.name}: the check failed, so it is produced", flush=True)
        return False
    write_stamp(family, workspace.root, inputs, cache_directory=workspace.cache_directory)
    print(f"{family.name}: adopted, its check proved the stored outputs")
    return True


def seed(names: Sequence[str], *, force: bool, window: bool = False, workspace: Workspace | None = None) -> int:
    """Run the producer of each selected family that is not fresh, or of each one under ``force``.

    ``window`` selects the generated families whose outputs are the window
    projections, the ones a frontend build imports, instead of named families.
    """
    workspace = workspace or Workspace()
    selected = _selected(workspace, names, window=window)
    digests = InputDigests(workspace.root)
    authority = workspace.authority()
    failed: list[str] = []
    for family in selected:
        if family.producer is None:
            continue
        # Inputs are read before the producer runs: an input edited during the
        # run then shows as stale, never as a fresh stamp over older outputs.
        inputs = _inputs(family, digests, authority)
        current = family_status(family, workspace.root, inputs, cache_directory=workspace.cache_directory)
        if current.state is FixtureState.FRESH and not force:
            print(f"{family.name}: fresh")
            continue
        unmet = _unmet_prerequisites(workspace, family)
        for reason in unmet:
            print(f"  {family.name}: {reason}", file=sys.stderr)
        if unmet:
            failed.append(family.name)
            continue
        if (
            current.state is FixtureState.UNSTAMPED
            and family.check_proves_outputs
            and not force
            and _adopted(workspace, family, inputs)
        ):
            continue
        print(f"{family.name}: producing ({current.state})", flush=True)
        if _run(workspace, family.producer) != 0:
            failed.append(family.name)
            continue
        if not output_digests(family, workspace.root):
            print(f"  {family.name} produced no declared output", file=sys.stderr)
            failed.append(family.name)
            continue
        write_stamp(family, workspace.root, inputs, cache_directory=workspace.cache_directory)
    if failed:
        print(f"Producers failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def _determinism_findings(workspace: Workspace, family: FixtureFamily) -> tuple[str, ...]:
    if family.producer is None:
        return ()
    if family.determinism is None:
        return (DETERMINISM_UNDECLARED,)
    stamp = datetime.now(UTC).date().isoformat()
    scratch = workspace.scratch_root / f"{stamp}-fixture-projections-{uuid.uuid4().hex[:12]}"
    # The checkout's scratch goes through its admission; an isolated workspace
    # names its own. Only the directory made here is ever removed.
    if workspace.scratch_root == TEMP_ROOT:
        if prepare_temp_root(override=scratch) != scratch:
            raise FixtureProjectionError(f"scratch {scratch} was not admitted")
    else:
        scratch.mkdir(parents=True)
    try:
        trees: list[dict[str, bytes]] = []
        for run in ("first", "second"):
            output = scratch / run
            output.mkdir()
            if _run(workspace, family.determinism, output=output) != 0:
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


def _determinism_verdict(findings: tuple[str, ...]) -> str:
    if findings == (DETERMINISM_UNDECLARED,):
        return DETERMINISM_UNDECLARED
    return "nondeterministic" if findings[0].startswith("not byte-identical") else "determinism unproven"


def check(names: Sequence[str], *, determinism: bool, workspace: Workspace | None = None) -> int:
    """Validate the personas, run every selected family's own check and, when asked, prove determinism."""
    workspace = workspace or Workspace()
    started = time.monotonic()
    failures: list[str] = []
    personas = workspace.persona_check()
    print(f"personas: {'ok' if not personas else 'failed'}")
    for finding in personas:
        print(f"  {finding}")
    if personas:
        failures.append("personas")
    for family in _selected(workspace, names):
        family_started = time.monotonic()
        verdict = "ok"
        unmet = _unmet_prerequisites(workspace, family)
        for reason in unmet:
            print(f"  {reason}")
        if unmet:
            verdict = "unavailable"
        elif any(_run(workspace, command) != 0 for command in family.check):
            verdict = "failed"
        # Determinism is its own finding, so it is proven even when the stored
        # outputs are stale or the check cannot run.
        findings = _determinism_findings(workspace, family) if determinism else ()
        for finding in findings:
            print(f"  {finding}")
        if findings:
            proof = _determinism_verdict(findings)
            verdict = proof if verdict == "ok" else f"{verdict}, {proof}"
        if verdict != "ok":
            failures.append(family.name)
        print(f"{family.name}: {verdict} ({time.monotonic() - family_started:.1f}s)", flush=True)
    print(f"fixtures-check took {time.monotonic() - started:.1f}s")
    if failures:
        print(f"Failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def removable_targets(family: FixtureFamily, root: Path) -> list[Path]:
    """Return the family's existing outputs and stamp, refusing any that leave its output root or follow a link."""
    if family.output_root is None:
        return []
    checkout = root.resolve()
    output_root = (root / family.output_root).resolve()
    if not output_root.is_relative_to(checkout) or output_root == checkout:
        raise FixtureProjectionError(f"{family.name}: output root {output_root} is not inside the checkout")
    targets = [*output_paths(family, root), stamp_path(family, root)]
    for target in targets:
        if target.is_symlink() or target.is_junction():
            raise FixtureProjectionError(f"{family.name}: refusing to follow the link {target}")
        if not target.resolve().is_relative_to(output_root):
            raise FixtureProjectionError(f"{family.name}: {target} is outside its output root")
    return [target for target in targets if target.exists()]


def clean(names: Sequence[str], workspace: Workspace | None = None) -> int:
    """Remove each selected family's generated outputs; refuse a family whose outputs are committed."""
    workspace = workspace or Workspace()
    refused: list[str] = []
    for family in _selected(workspace, names):
        if family.producer is None:
            continue
        if family.committed:
            print(f"{family.name}: refused, its outputs are committed in place")
            refused.append(family.name)
            continue
        targets = removable_targets(family, workspace.root)
        for target in targets:
            target.unlink()
        print(f"{family.name}: removed {len(targets)} files")
    # A named family that cannot be cleaned is a refusal; a sweep only reports them.
    return 1 if refused and names else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run one fixture projection verb."""
    parser = argparse.ArgumentParser(prog="python -m dev.fixture_projections", description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)
    seeding = verbs.add_parser("seed", help="Produce or adopt families that are not fresh.")
    seeding.add_argument("--force", action="store_true", help="Produce every selected family.")
    seeding.add_argument(
        "--window", action="store_true", help="Select the generated families the desktop frontend imports."
    )
    seeding.add_argument("families", nargs="*")
    for verb, summary in (
        ("status", "Report fresh, stale, unstamped or missing."),
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
            return seed(args.families, force=args.force, window=args.window)
        if args.verb == "status":
            return status(args.families)
        if args.verb == "check":
            return check(args.families, determinism=args.determinism)
        return clean(args.families)
    except FixtureProjectionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
