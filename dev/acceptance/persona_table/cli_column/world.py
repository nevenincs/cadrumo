"""Materialise one persona's world into a storage root for the CLI column, and report the returns the table runs on it.

    python -m dev.acceptance.persona_table.cli_column.world --persona <id> --horizon <year> --storage-root <dir>

The world is seeded in process, through the registered operations of the production supervisor, under the persona's
frozen scenario clock, with recorded ECB rates: the same seeding the desktop window's world uses. The process exits
before any runtime starts, so the profile the CLI runtime then serves is the one this wrote and no direct store write
touched it. The returns are not prepared: the CLI creates, states and calculates each of them itself.

The directory must be absent or empty and lie outside every Git project. One JSON object goes to standard output; the
passphrase is not in it.
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

from cadrumo.adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from cadrumo.application.exchange_rate_provider import bind_exchange_rate_provider_factory
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tests.persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    filing_key,
    materialised_persona,
)
from cadrumo.tests.env_scope import scoped_env_var
from cadrumo.tests.personas import Persona, PersonaCatalogueError, persona_ids, read_persona
from dev.desktop_persona_world import refuse_storage_root
from dev.exit_codes import FAILED, OK
from dev.paths import STORAGE_ROOT_ENV

from ..planner import MODELOS_ENV, YEARS_ENV, plan_rows, registry_envelope, replay_scope, stated_refusal, stated_values
from ..rows import PlannedRow


def last_owed_period(persona: Persona, plan: PlannedRow) -> str:
    """The year's last quarterly period the persona owes of the planned return's modelo, else the return's own."""
    periods = {
        period for item in persona.expectations.obligations if item.modelo == plan.modelo for period in item.periods
    }
    return max((period for period in periods if period.endswith("T")), default=plan.period)


def _row(
    materialised: MaterialisedPersona, plan: PlannedRow, emitted: frozenset[tuple[str, str, int, str]]
) -> dict[str, object]:
    world = materialised.world
    refusal = stated_refusal(stated_values(materialised.persona, world.envelope, plan))
    return {
        "modelo": plan.modelo,
        "year": plan.year,
        "period": plan.period,
        "owed": plan.owed,
        "emitted": plan.key in emitted,
        "history_filed": filing_key(plan.modelo, plan.year, plan.period) in materialised.filings,
        "last_owed_period": last_owed_period(materialised.persona, plan),
        "stated_refusal": None if refusal is None else f"{refusal.refusal} at {refusal.refusal_stage}",
    }


def prepare_world(
    persona_id: str, horizon: int, root: Path, modelos: Sequence[str], years: Sequence[int]
) -> dict[str, object]:
    """Materialise ``persona_id`` under ``horizon`` into ``root`` and return the report of its returns.

    ``modelos`` and ``years`` restrict the returns that are written, as the table's ``run`` does; the returns they
    read are replayed too. ``root`` is a checked, absent or empty directory; the profile stays in it.
    """
    with ExitStack() as scope:
        # Settings are read outside the isolated storage root while the world is registered; point that read at a
        # directory of its own, not at the checkout's default storage root.
        scope.enter_context(profile_adapter_composition())
        scope.enter_context(bind_exchange_rate_provider_factory(recorded_ecb_rate_provider))
        ambient = scope.enter_context(tempfile.TemporaryDirectory(prefix="persona-world-"))
        scope.enter_context(scoped_env_var(STORAGE_ROOT_ENV, str(Path(ambient) / "storage")))
        scope.enter_context(scoped_env_var(MODELOS_ENV, ",".join(modelos) or None))
        scope.enter_context(scoped_env_var(YEARS_ENV, ",".join(str(year) for year in years) or None))
        plans, emitted = plan_rows(persona_id, horizon)
        persona = read_persona(persona_id, envelope=registry_envelope())
        with materialised_persona(
            persona_id, root, replay_scope(persona), reuse=False, horizon=horizon
        ) as materialised:
            world = materialised.world
            return {
                "persona": persona_id,
                "horizon": horizon,
                "storage_root": str(world.storage_root.resolve()),
                "profile_id": str(world.profile_id),
                "authority_generation": world.operation.generation.logical_generation,
                "as_of": world.as_of.isoformat(),
                "scope": materialised.scope.value,
                "actor": PERSONA_ACTOR,
                "aeat_filings_in_process": bool(materialised.persona.aeat_filings),
                "needs_statements": bool(
                    world.attested_prior_values or world.work_inputs or world.work_income_none_statements
                ),
                "rows": [_row(materialised, plan, emitted) for plan in plans],
            }


def main(argv: Sequence[str] | None = None) -> int:
    """Materialise the persona's world, print its report as one JSON object and return the exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m dev.acceptance.persona_table.cli_column.world", description=__doc__
    )
    parser.add_argument("--persona", required=True, help="a catalogue persona id")
    parser.add_argument("--horizon", required=True, type=int, help="a supported filing year the replay is run under")
    parser.add_argument("--storage-root", required=True, type=Path, help="an absolute, absent or empty directory")
    parser.add_argument("--modelo", action="append", default=[], help="a modelo whose returns are written (repeatable)")
    parser.add_argument("--year", action="append", default=[], type=int, help="a filing year to write (repeatable)")
    args = parser.parse_args(argv)
    if args.persona not in persona_ids():
        parser.error(f"unknown persona {args.persona!r}")
    refusal = refuse_storage_root(args.storage_root)
    if refusal is not None:
        parser.error(refusal)
    try:
        # Operations may print; standard output carries the report alone.
        with contextlib.redirect_stdout(sys.stderr):
            report = prepare_world(args.persona, args.horizon, args.storage_root.resolve(), args.modelo, args.year)
    except (PersonaMaterialisationError, PersonaCatalogueError) as error:
        sys.stderr.write(f"persona world not prepared: {error}\n")
        return FAILED
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return OK


if __name__ == "__main__":
    sys.exit(main())
