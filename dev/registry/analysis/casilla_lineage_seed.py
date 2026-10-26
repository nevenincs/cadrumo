"""Seed casilla lineage across successor editions, refusing what it cannot prove.

For every adjacent pair of editions of an in-scope modelo, each successor
casilla row is disposed of exactly once:

- **declared** -- it already carries a ``continuidad_id`` its predecessor
  edition carries. Left untouched.
- **seeded** -- a bare chain admitted only when the casilla identifier, the
  ``semantic_role`` and the ``data_type`` all agree and the dedicated printed box
  number ``form_number`` agrees where both rows state one. The general
  ``number`` field is heterogeneous by design (a byte range on one modelo, a
  one-byte wire campo's plain integer on another) and is never read for
  identity; a byte span never chains.
- **grounded** -- a continuation an adjudicated ruling proves from the official
  record designs.
- an absence of one of three kinds -- ``new_on_form`` (the box is not on the
  predecessor form), ``predecessor_edition_silent`` (the box is on the
  predecessor form but the predecessor edition does not declare it) or
  ``not_on_form`` (a product concept the form does not number). A kind is
  written only on evidence from the pinned official record design, which is
  trusted for an edition pair only when every printed number both editions
  declare resolves in its own design and the successor design retires no box.
- **refused** -- anything else, recorded in the ledger with its reason rather
  than falling through to a weaker signal.

An excluded modelo is never written. Each of its successor rows that neither
carries lineage nor declares a kind of none is still refused in the ledger, one
row at a time, under the category its exclusion names, so the ledger stays the
closed list of every unresolved row in the corpus.

Modelos are compiled one directory at a time rather than through the
whole-corpus authority, which refuses the whole corpus when any single modelo
fails and so let one modelo's defect stop seeding for every other -- including
modelos it shares nothing with, and modelos this seeder is excluded from
writing at all. A modelo that cannot be compiled is recorded for that run as a
``[[load_failed]]`` entry carrying the first message its loader raised, and
every other modelo is seeded as before.

A modelo whose corpus already stamps a casilla identifier on some editions and
neither stamps nor excuses it on the others is held back the same way. The
registry refuses such an identifier, so no chain may be written into it and the
seeder must not try; but that is one modelo's half-finished stamping, and it is
not a reason to stop seeding the rest of the corpus. The modelo is recorded for
that run as a ``[[stamping_in_progress]]`` entry naming the chain, the editions
that carry it and the editions that do not, is skipped entirely, and every other
modelo is planned as before. The refusal to write into such a chain is unchanged:
the modelo is skipped, never seeded on weaker evidence. The run prints both kinds
of skip so a reader sees it without opening the ledger. Nor does the record make
a half-stamped chain tolerable: the registry's own partial-stamping gate pins
such chains at zero as a defect rather than a backlog, and reads the authored
corpus directly, so it stays red for exactly as long as an entry stands here.

Neither kind of skip is allowed to shrink the ledger. A skipped modelo's rows
were not judged this run, so they cannot be rejudged -- but they were judged
before, and dropping their entries would silently remove that modelo from the
closed list. Every previous ``[[refusal]]`` of a skipped modelo is therefore
carried forward verbatim, marked ``carried_from_previous_run``, naming why it
could not be rejudged and the run identifier of the last run that actually
judged it; see :func:`render_ledger`.

Coverage is a different question from identity: whether a row has a printed box
at all is read from ``form_number`` OR a plain-integer ``number`` (that is the
shipped printed-number contract); whether two rows are the same box is read
from ``form_number`` alone.

A chain is also refused when writing it would break the registry's own load
contract: every occurrence of a chain crossing a revision boundary must carry a
``semantic_role``, and a chain whose role is unique in every revision it spans
must use the role-derived identifier.

Usage::

    python -m dev.registry.analysis.casilla_lineage_seed            # report only
    python -m dev.registry.analysis.casilla_lineage_seed --apply    # write rows and ledger

Reads each modelo through the registry loader and the shared source catalogue.
Writes insert keys into the casilla declaration files as text, never
reformatting them, and refuse to overwrite a differing value already present.
"""

from __future__ import annotations

import argparse
import collections
import sys
from collections.abc import Mapping, Sequence

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader import load_shared_catalogues
from ..compiler.loader_cache import discover_modelo_sources
from .casilla_lineage_seed_corpus import load_corpus
from .casilla_lineage_seed_design import DesignOracle
from .casilla_lineage_seed_ledger import (
    carried_refusals,
    load_previous_ledger,
    partition_contradictions,
    render_ledger,
    run_identifier,
)
from .casilla_lineage_seed_paths import _MODELOS_ROOT, _REGISTRY_ROOT, _UTF_8, LEDGER_PATH
from .casilla_lineage_seed_planner import plan_corpus, residual_plan
from .casilla_lineage_seed_rules import load_rulings
from .casilla_lineage_seed_types import (
    _EVIDENCE_ADVISORY,
    EXCLUDED_MODELOS,
    SCHEMA_EVIDENCE_LIMIT,
    LineagePlan,
    ModeloLoadFailure,
    PartialStamping,
)
from .casilla_lineage_seed_validation import contradictions, gate_regressions
from .casilla_lineage_seed_writer import apply_plan

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Plan or apply casilla-lineage rows while keeping the refusal ledger closed."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write the planned keys and the ledger")
    parser.add_argument("--modelo", action="append", help="limit to these modelos (repeatable)")
    args = parser.parse_args(argv)

    loaded, load_failures = load_corpus(discover_modelo_sources(_MODELOS_ROOT))
    oracle = DesignOracle(load_shared_catalogues(_REGISTRY_ROOT).sources)
    rulings = load_rulings()
    modelo_ids, selected = _select_scope(loaded, load_failures, rulings, args.modelo)
    plans, partial_stampings = _plan_scope(selected, modelo_ids, loaded, oracle, rulings, args.modelo)
    checks = _checks_by_modelo(plans, loaded)

    _print_load_failures(load_failures)
    _print_partial_stampings(partial_stampings)
    _print_plan_totals(plans, checks)
    _print_partial_summary(partial_stampings)
    skipped = _skipped_modelos(load_failures, partial_stampings)
    carried = carried_refusals(load_previous_ledger(), skipped)
    _print_carried_refusals(carried, skipped)
    blocking, excluded_contradictions = partition_contradictions(checks)
    _print_excluded_contradictions(excluded_contradictions)
    if any(blocking.values()):
        print("refusing to write: the plan contains contradictions", file=sys.stderr)
        return 1
    return _apply_requested(
        args.apply,
        bool(args.modelo),
        plans,
        checks,
        load_failures,
        partial_stampings,
        excluded_contradictions,
        carried,
    )


def _select_scope(loaded, load_failures, rulings, requested):
    modelo_ids = sorted(loaded)
    selected = [
        modelo_id
        for modelo_id in modelo_ids
        if modelo_id not in EXCLUDED_MODELOS
        and len(loaded[modelo_id].revisions) > 1
        and (not requested or modelo_id in requested)
    ]
    failed = {failure.modelo for failure in load_failures}
    unknown = set(rulings) - set(selected) - set(EXCLUDED_MODELOS) - failed
    if unknown and not requested:
        raise SystemExit(f"rulings name modelos outside scope: {sorted(unknown)}")
    return modelo_ids, selected


def _plan_scope(selected, modelo_ids, loaded, oracle, rulings, requested):
    plans, partial_stampings = plan_corpus(selected, loaded, oracle, rulings)
    plans.extend(
        residual_plan(modelo_id, loaded[modelo_id], rulings.get(modelo_id, ()))
        for modelo_id in modelo_ids
        if modelo_id in EXCLUDED_MODELOS and (not requested or modelo_id in requested)
    )
    plans.sort(key=lambda plan: plan.modelo)
    return plans, partial_stampings


def _checks_by_modelo(plans: Sequence[LineagePlan], loaded: Mapping[str, ModeloDefinition]):
    return {
        plan.modelo: [
            *contradictions(loaded[plan.modelo], plan),
            *(f"gate: {failure}" for failure in gate_regressions(loaded[plan.modelo], plan)),
        ]
        for plan in plans
    }


def _print_load_failures(load_failures: Sequence[ModeloLoadFailure]) -> None:
    for failure in sorted(load_failures, key=lambda entry: entry.modelo):
        print(f"{failure.modelo}: load_failed; {failure.reason}")


def _print_partial_stampings(records: Sequence[PartialStamping]) -> None:
    for record in sorted(records, key=lambda entry: (entry.modelo, entry.casilla)):
        print(f"{record.modelo}: stamping_in_progress; {record.describe()}")


def _print_plan_totals(plans: Sequence[LineagePlan], checks: Mapping[str, Sequence[str]]) -> None:
    totals: collections.Counter[str] = collections.Counter()
    for plan in plans:
        _print_plan(plan, checks[plan.modelo])
        totals.update(plan.counts)
    print("total:", ", ".join(f"{key}={value}" for key, value in sorted(totals.items())))
    _print_evidence_advisory(plans)


def _print_plan(plan: LineagePlan, problems: Sequence[str]) -> None:
    totals = ", ".join(f"{key}={value}" for key, value in sorted(plan.counts.items()))
    print(f"{plan.modelo}: {totals}; contradictions={len(problems)}")
    for problem in problems[:5]:
        print(f"    CONTRADICTION {problem}")


def _print_evidence_advisory(plans: Sequence[LineagePlan]) -> None:
    long_evidence = [entry for plan in plans for entry in plan.long_evidence]
    if not long_evidence:
        return
    longest = max(long_evidence, key=lambda entry: entry.length)
    print(
        f"warning: {len(long_evidence)} evidence string(s) longer than {_EVIDENCE_ADVISORY} characters, within "
        f"the schema cap of {SCHEMA_EVIDENCE_LIMIT}; longest {longest.length} at "
        f"{longest.modelo} {longest.revision}/{longest.casilla}"
    )


def _print_partial_summary(records: Sequence[PartialStamping]) -> None:
    if not records:
        return
    skipped = sorted({record.modelo for record in records})
    print(f"skipped {len(skipped)} modelo(s) for partly stamped chains: {', '.join(skipped)}")
    for record in sorted(records, key=lambda entry: (entry.modelo, entry.casilla)):
        print(f"    SKIPPED {record.modelo} {record.describe()}")


def _skipped_modelos(load_failures: Sequence[ModeloLoadFailure], records: Sequence[PartialStamping]) -> dict[str, str]:
    skipped = {failure.modelo: f"modelo could not be compiled this run: {failure.reason}" for failure in load_failures}
    skipped.update(
        {
            record.modelo: f"modelo was skipped this run for a partly stamped identifier: {record.describe()}"
            for record in records
        }
    )
    return skipped


def _print_carried_refusals(carried, skipped: Mapping[str, str]) -> None:
    if carried:
        by_modelo = collections.Counter(entry.modelo for entry in carried)
        print(f"carried {len(carried)} previous refusal(s) forward for {len(by_modelo)} unjudged modelo(s):")
        for modelo_id, count in sorted(by_modelo.items()):
            _print_carried_modelo(modelo_id, count, carried)
    carried_modelos = {entry.modelo for entry in carried}
    for modelo_id in sorted(skipped):
        if modelo_id not in carried_modelos:
            print(f"    CARRIED {modelo_id} no previous refusal to carry; the ledger names none of its rows")


def _print_carried_modelo(modelo_id, count, carried) -> None:
    entries = [entry for entry in carried if entry.modelo == modelo_id]
    oldest = min(entry.last_judged for entry in entries)
    runs = max(entry.carried_runs for entry in entries)
    print(f"    CARRIED {modelo_id} {count} row(s), last judged {oldest}, carried {runs} run(s)")


def _print_excluded_contradictions(excluded_contradictions: Mapping[str, Sequence[str]]) -> None:
    for modelo_id, problems in sorted(excluded_contradictions.items()):
        print(f"{modelo_id}: excluded_contradiction; {len(problems)} contradiction(s) left to hand adjudication")
        for problem in problems:
            print(f"    EXCLUDED_CONTRADICTION {problem}")


def _apply_requested(
    apply,
    limited,
    plans,
    checks,
    load_failures,
    partial_stampings,
    excluded_contradictions,
    carried,
) -> int:
    if not apply:
        return 0
    edited = sum(apply_plan(plan) for plan in plans)
    if not limited:
        _write_ledger(plans, checks, load_failures, partial_stampings, excluded_contradictions, carried)
    print(f"edited {edited} rows")
    return 0


def _write_ledger(plans, checks, load_failures, partial_stampings, excluded_contradictions, carried) -> None:
    LEDGER_PATH.write_text(
        render_ledger(
            plans,
            checks,
            load_failures,
            partial_stampings,
            excluded_contradictions=excluded_contradictions,
            carried=carried,
            judged_at=run_identifier(),
        )
        + "\n",
        encoding=_UTF_8,
        newline="\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())
