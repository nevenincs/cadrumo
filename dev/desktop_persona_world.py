"""Materialise one catalogue persona into a storage root, with every return its table row runs ready to calculate.

The persona table replays a persona and takes each return it owes through create, calculate, verify, export and
local filing. The desktop window does calculate, verify and export itself, so this tool stops each return where
the table stops before the calculate operation: it replays the persona's world with ``reuse=False`` into a
caller-given directory, then, in the table's own chain order, runs the table's preparation of every planned row
(create, the pending carries and prior figures the table states first and a Modelo 303's evidence), then enters
the values the persona's operator gives. Planning, scope, values and preparation are the table's own functions.

    python -m dev.desktop_persona_world --persona <id> --horizon <year> --storage-root <absolute directory>

The directory must be absent or empty and lie outside every Git project. One JSON object goes to standard output:
the ``CADRUMO_STORAGE_ROOT`` the packaged desktop must be started with, the profile id, where the profile
passphrase is defined (never the passphrase), the scenario instant, and one entry per planned row.

Every operation here ran under the persona's frozen scenario clock, as the table's calculate does; a desktop on the
wall clock calculates at a later instant. Each row is prepared against a profile in which the rows before it are
only prepared, not filed locally, whereas the table files each verified row before it creates the next.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import tempfile
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from cadrumo.adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from cadrumo.application.exchange_rate_provider import bind_exchange_rate_provider_factory
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tests.persona_materialisation import (
    PersonaMaterialisationError,
    materialised_persona,
    settle_operation,
    year_envelope,
)
from cadrumo.entrypoints.tests.persona_work_inputs import WorkInputError, enter_work_inputs
from cadrumo.tests.env_scope import scoped_env_var
from cadrumo.tests.personas import PersonaCatalogueError, persona_ids, read_persona

from .desktop_agent_live.disposable_root import enclosing_git_project
from .exit_codes import FAILED, OK
from .paths import STORAGE_ROOT_ENV

if TYPE_CHECKING:
    from pydantic import BaseModel

    from cadrumo.entrypoints.tests.persona_materialisation import MaterialisedPersona, PersonaWorld

    from .acceptance.persona_table.rows import PlannedRow
    from .acceptance.persona_table.sweep import PreparedReturn

CREDENTIAL_SOURCE: Final = "persona_materialisation._PROFILE_CREDENTIAL"
"""Where the profile passphrase is defined; the tool never prints the passphrase itself."""
TABLE_PERSONAS_ENV: Final = "PERSONA_TABLE_PERSONAS"
"""The variable the table's collector reads, at import, to name the personas it collects."""


def refuse_storage_root(root: Path) -> str | None:
    """Why ``root`` cannot hold a world, or ``None`` when it is an absolute, absent or empty directory outside Git."""
    if not root.is_absolute():
        return f"the storage root must be an absolute path: {root}"
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        return f"the storage root must be absent or an empty directory: {root}"
    project = enclosing_git_project(root)
    if project is not None:
        return f"the storage root {root} lies inside the Git project {project}"
    return None


def _entry(
    plan: PlannedRow,
    *,
    work_unit_id: str | None = None,
    prepared: bool = False,
    outcome: str | None = None,
    reason: str | None = None,
    m303_evidence: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The report entry of one planned row: its work unit when prepared, else the stage where the table stops."""
    return {
        "modelo": plan.modelo,
        "year": plan.year,
        "period": plan.period,
        "owed": plan.owed,
        "work_unit_id": work_unit_id,
        "prepared": prepared,
        "pre_calculate_outcome": outcome,
        "reason": reason,
        "m303_evidence": m303_evidence,
    }


def _enter_work_inputs(world: PersonaWorld, work_unit_id: str) -> None:
    """Enter the values the persona's operator gives for the work unit's return, as the calculate operation does."""

    def settle(definition_id: str, payload: BaseModel, *, subject: str | None = None) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    try:
        enter_work_inputs(
            world.work_inputs,
            envelope=world.envelope,
            operation=world.operation,
            profile_id=world.profile_id,
            work_unit_id=work_unit_id,
            settle=settle,
        )
    except WorkInputError as error:
        raise PersonaMaterialisationError(str(error)) from error


def _m303_evidence(prepared: PreparedReturn) -> dict[str, str] | None:
    """The Modelo 390 attestation the calculate request carries, or none outside the year's last period."""
    evidence = prepared.request.ordinary_m303_filing_evidence
    if evidence is None or evidence.m303_exonerado_390_attachment_id is None:
        return None
    return {
        "attachment_id": evidence.m303_exonerado_390_attachment_id,
        "sha256": str(evidence.m303_exonerado_390_sha256),
    }


def _prepared_rows(materialised: MaterialisedPersona, plans: Sequence[PlannedRow]) -> list[dict[str, Any]]:
    """Run the table's preparation of each planned row, in chain order, and report where each one stands."""
    from .acceptance.persona_table import sweep
    from .acceptance.persona_table.rows import TableRow

    world = materialised.world
    rows: list[dict[str, Any]] = []
    for plan in plans:
        values = sweep.stated_values(materialised.persona, world.envelope, plan)
        prepared = sweep.prepare_return(materialised, plan, values)
        if isinstance(prepared, TableRow):
            rows.append(_entry(plan, outcome=str(prepared.calculate), reason=prepared.reason or None))
            continue
        if world.work_inputs:
            try:
                _enter_work_inputs(world, prepared.work_unit_id)
            except PersonaMaterialisationError as error:
                # The table meets this refusal at calculate, where the operation enters the inputs itself.
                rows.append(_entry(plan, work_unit_id=prepared.work_unit_id, outcome="refused", reason=str(error)))
                continue
        rows.append(
            _entry(
                plan,
                work_unit_id=prepared.work_unit_id,
                prepared=True,
                m303_evidence=_m303_evidence(prepared),
            )
        )
    return rows


def prepare_world(persona_id: str, horizon: int, root: Path) -> dict[str, Any]:
    """Materialise ``persona_id`` under ``horizon`` into ``root``, prepare its rows and return the report.

    ``root`` is a checked, absent or empty directory; the profile stays in it when this returns.
    """
    with ExitStack() as scope:
        # Settings are read outside the isolated storage root while the world is registered; point that
        # read at a directory of its own, not at the checkout's default storage root.
        scope.enter_context(profile_adapter_composition())
        # The table runs on recorded ECB rates, as the repository's test composition binds them.
        scope.enter_context(bind_exchange_rate_provider_factory(recorded_ecb_rate_provider))
        ambient = scope.enter_context(tempfile.TemporaryDirectory(prefix="persona-world-"))
        scope.enter_context(scoped_env_var(STORAGE_ROOT_ENV, str(Path(ambient) / "storage")))
        # The table's collector parametrizes every persona it is allowed to collect when it is imported.
        scope.enter_context(scoped_env_var(TABLE_PERSONAS_ENV, persona_id))
        from .acceptance.persona_table import sweep

        scope.enter_context(scoped_env_var(sweep.MODELOS_ENV, None))
        scope.enter_context(scoped_env_var(sweep.YEARS_ENV, None))
        if sweep.PERSONAS_ENV != TABLE_PERSONAS_ENV:
            raise PersonaMaterialisationError(f"the table now reads its personas from {sweep.PERSONAS_ENV}")
        plans, _emitted = sweep.plan_rows(persona_id, horizon)
        with bundled_indexed_authority().operation() as operation:
            persona = read_persona(persona_id, envelope=year_envelope(operation))
        with materialised_persona(
            persona_id, root, sweep.replay_scope(persona), reuse=False, horizon=horizon
        ) as materialised:
            world = materialised.world
            rows = _prepared_rows(materialised, plans)
            report: dict[str, Any] = {
                "persona": persona_id,
                "horizon": horizon,
                "storage_root": str(world.storage_root.resolve()),
                "profile_id": str(world.profile_id),
                "passphrase_source": CREDENTIAL_SOURCE,
                "as_of": world.as_of.isoformat(),
                "authority_generation": world.operation.generation.logical_generation,
                "scope": materialised.scope.value,
                "rows": rows,
            }
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare the persona's world, print the report as one JSON object and return the exit code."""
    parser = argparse.ArgumentParser(prog="python -m dev.desktop_persona_world", description=__doc__)
    parser.add_argument("--persona", required=True, help="a catalogue persona id")
    parser.add_argument("--horizon", required=True, type=int, help="a supported filing year the replay is run under")
    parser.add_argument("--storage-root", required=True, type=Path, help="an absolute, absent or empty directory")
    args = parser.parse_args(argv)
    if args.persona not in persona_ids():
        parser.error(f"unknown persona {args.persona!r}")
    refusal = refuse_storage_root(args.storage_root)
    if refusal is not None:
        parser.error(refusal)
    try:
        # Operations may print; standard output carries the report alone.
        with contextlib.redirect_stdout(sys.stderr):
            report = prepare_world(args.persona, args.horizon, args.storage_root.resolve())
    except (PersonaMaterialisationError, PersonaCatalogueError) as error:
        sys.stderr.write(f"persona world not prepared: {error}\n")
        return FAILED
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return OK


if __name__ == "__main__":
    sys.exit(main())
