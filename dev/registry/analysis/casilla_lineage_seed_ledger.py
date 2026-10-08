"""Carry refusals honestly and render the closed lineage-seeding ledger."""

from __future__ import annotations

import collections
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from cadrumo.core.toml import parse_toml

from .casilla_lineage_seed_paths import _UTF_8, LEDGER_PATH
from .casilla_lineage_seed_types import (
    EXCLUDED_MODELOS,
    CarriedRefusal,
    LineagePlan,
    ModeloLoadFailure,
    PartialStamping,
    PreviousLedger,
)


def run_identifier(moment: datetime | None = None) -> str:
    """The identifier a run stamps on what it judges: a UTC instant, to the second."""
    return (moment or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_previous_ledger(path: Path = LEDGER_PATH) -> PreviousLedger:
    """Read the committed ledger, so a modelo this run cannot rejudge keeps its entries.

    A missing ledger is a first run and carries nothing. Refusals are kept as
    their raw tables rather than parsed into :class:`Refusal`, because carrying
    forward must be verbatim: whatever the previous run wrote is the previous
    run's judgement, and reshaping it here would quietly restate it.
    """
    if not path.is_file():
        return PreviousLedger(judged_at="", refusals={})
    document = parse_toml(path.read_text(encoding=_UTF_8))
    run = document.get("run")
    judged_at = run.get("judged_at", "") if isinstance(run, Mapping) else ""
    by_modelo: dict[str, list[Mapping[str, object]]] = collections.defaultdict(list)
    for entry in document.get("refusal", ()):
        modelo = entry.get("modelo")
        if isinstance(modelo, str):
            by_modelo[modelo].append(entry)
    return PreviousLedger(
        judged_at=str(judged_at),
        refusals={modelo: tuple(entries) for modelo, entries in by_modelo.items()},
    )


def carried_refusals(previous: PreviousLedger, skipped: Mapping[str, str]) -> tuple[CarriedRefusal, ...]:
    """Carry every previous refusal of a skipped modelo forward, dated by its last real judgement.

    ``skipped`` maps each modelo this run could neither load nor plan to the
    reason it was skipped. An entry the previous run itself carried keeps its
    original ``last_judged`` and increments its carry count; an entry the
    previous run judged takes that run's identifier. A previous ledger naming no
    run cannot date what it judged, so its entries carry the only honest value
    available -- ``unknown`` -- rather than being backdated to a run that never
    judged them.
    """
    carried: list[CarriedRefusal] = []
    for modelo in sorted(skipped):
        for entry in previous.refusals.get(modelo, ()):
            was_carried = entry.get("carried_from_previous_run") is True
            last_judged = entry.get("last_judged") if was_carried else previous.judged_at
            runs = entry.get("carried_runs", 0) if was_carried else 0
            predecessor = entry.get("predecessor")
            carried.append(
                CarriedRefusal(
                    modelo=modelo,
                    revision=str(entry["revision"]),
                    casilla=str(entry["casilla"]),
                    category=str(entry["category"]),
                    reason=str(entry["reason"]),
                    predecessor=None if predecessor is None else str(predecessor),
                    carried_reason=skipped[modelo],
                    last_judged=str(last_judged) if isinstance(last_judged, str) and last_judged else "unknown",
                    carried_runs=(runs if isinstance(runs, int) and not isinstance(runs, bool) else 0) + 1,
                )
            )
    return tuple(carried)


def partition_contradictions(
    checks: Mapping[str, list[str]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Split contradictions into the ones that refuse the write and the ones recorded instead.

    An excluded modelo is adjudicated by hand outside this tool: its plan comes
    from :func:`residual_plan` and proposes no edit, so a contradiction found in
    it survives every run the seeder will ever make. Refusing the whole corpus
    on its behalf deadlocks every other modelo against a repair this run is not
    the one to make, and the ledger is whole-corpus or nothing, so the deadlock
    is total rather than partial.

    Returning it separately is not forgiving it. The second mapping is rendered
    into the ledger as ``[[excluded_contradiction]]`` with every offending row
    named, and the first still refuses the write outright, so a modelo this run
    seeds gains nothing from this split.
    """
    blocking: dict[str, list[str]] = {}
    excluded: dict[str, list[str]] = {}
    for modelo_id, problems in checks.items():
        if not problems:
            continue
        target = excluded if modelo_id in EXCLUDED_MODELOS else blocking
        target[modelo_id] = problems
    return blocking, excluded


def render_ledger(
    plans: list[LineagePlan],
    checks: Mapping[str, list[str]],
    load_failures: Iterable[ModeloLoadFailure],
    partial_stampings: Iterable[PartialStamping],
    *,
    excluded_contradictions: Mapping[str, list[str]] | None = None,
    carried: Iterable[CarriedRefusal] = (),
    judged_at: str = "",
) -> str:
    """Render the ledger: one refusal per unresolved row, plus the run's modelo-level records.

    A load failure is rendered as its own ``[[load_failed]]`` entry, and a
    modelo skipped for a partly stamped identifier as its own
    ``[[stamping_in_progress]]`` entry. Both are modelo-level because a modelo
    skipped whole dispositions no row and so can name none: neither record
    invents a row key, and neither is read by the lineage totality gate.

    An ``[[excluded_contradiction]]`` records a contradiction found in an
    excluded modelo's residual plan, naming every offending row. It is
    modelo-level for a different reason: the rows it names exist and are real,
    but they are a hand adjudication's to resolve and not this run's, so the
    entry must not be read as covering them. The gate keeps its teeth where
    they matter -- a contradiction in a modelo this run seeds still refuses the
    write outright -- and stops holding the other modelos hostage to a repair
    it is structurally unable to make.

    Skipping a modelo does not drop its rows. It means this run did not rejudge
    them, not that they stopped needing an entry, so every ``[[refusal]]`` the
    previous run wrote for a skipped modelo is carried forward verbatim as a
    ``[[refusal]]`` again, marked ``carried_from_previous_run``, naming in
    ``carried_reason`` why it could not be rejudged and in ``last_judged`` the
    identifier of the run that did judge it. The ledger therefore stays the
    closed list over the whole corpus whatever fails, and nothing is quietly
    covered either: a carried entry states in the ledger that it asserts
    something about an older corpus state, and ``carried_runs`` says how long it
    has been asserting it.

    That is what keeps the gate honest once it stops compiling the whole corpus
    at once. A gate partitioned by modelo judges only the modelos it could load,
    reports the rest as ``unjudged``, and is never green while that list is
    non-empty. It withholds a carried entry from both the uncovered and the
    stale side rather than reading a record of an older judgement as a claim
    about a corpus it never saw. When the modelo loads again it is judged again,
    its carried entries with it, and any that no longer fit are reported stale
    until the seeder runs and replaces them with fresh ones.

    ``judged_at`` identifies this run and dates every entry not marked carried.
    """
    out = _ledger_header()
    _append_run(out, judged_at)
    _append_excluded(out)
    _append_load_failures(out, load_failures)
    _append_partial_stampings(out, partial_stampings)
    _append_excluded_contradictions(out, excluded_contradictions)
    _append_summaries(out, plans, checks)
    judged = _append_current_refusals(out, plans)
    _append_carried_refusals(out, carried, judged)
    return "\n".join(out)


def _ledger_header() -> list[str]:
    return [
        "# Casilla lineage ledger, written by casilla_lineage_seed.py --apply. Do not edit by hand.",
        "#",
        "# Every successor row that neither carries lineage nor declares its kind of none is listed",
        "# here, one refusal per row, with the category and reason it stopped. That includes every",
        "# such row of an excluded modelo, whether examined or not. The list is closed: a row missing",
        "# from it, or an entry whose row no longer needs it, fails the lineage totality gate.",
        "#",
        "# [run].judged_at identifies the run that wrote this file. Every [[refusal]] that does not",
        "# say otherwise was judged in that run, against the corpus as it then stood.",
        "#",
        "# A [[load_failed]] modelo is recorded at modelo level and names no row, because a modelo",
        "# that does not compile has no rows to name. It is deliberately not a [[refusal]]: the",
        "# totality gate reads rows, and a modelo-level entry must neither cover one nor go stale.",
        "# Nothing is lost by that, because skipping a modelo never shrinks this list: each previous",
        "# [[refusal]] of a skipped modelo is carried forward verbatim with carried_from_previous_run",
        "# = true, the carried_reason it could not be rejudged, the last_judged run that did judge it,",
        "# and carried_runs counting the carries since. The gate is partitioned by modelo: it judges",
        "# only what it could load, reports the rest as unjudged, and is never green while one is",
        "# listed here. An entry whose carried_runs keeps climbing is a repair nobody finished.",
        "#",
        "# A [[stamping_in_progress]] modelo was skipped whole because the corpus stamps one of its",
        "# casilla identifiers on some editions and neither stamps nor excuses it on the others. It is",
        "# modelo-level and not a [[refusal]] for the same reason, and it closes no hole either. The",
        "# closing is not this seeder's: the registry's own partial-stamping gate already pins half-",
        "# stamped chains at zero and calls them a defect rather than a backlog, and it scans the",
        "# authored corpus, so it is red for exactly as long as an entry stands here. This record",
        "# keeps one modelo's half-finished pass from stopping the other fifty-seven; it does not",
        "# make the half-finished pass tolerable, and no entry here is ever a resting state.",
        "#",
        "# An [[excluded_contradiction]] names a contradiction this run found in an EXCLUDED modelo,",
        "# with every offending row spelled out. An excluded modelo is adjudicated by hand outside",
        "# this tool, so its plan proposes no edit and the seeder cannot resolve the contradiction",
        "# however often it runs; refusing the whole corpus on its behalf would deadlock every other",
        "# modelo against a repair this run is not the one to make. Recording it here is not",
        "# tolerating it. The contradiction is a live defect in the authored corpus, it is named so a",
        "# hand adjudication can find it, and the same contradiction in a modelo this run DOES seed",
        "# still refuses the write outright.",
        "",
    ]


def _append_run(out: list[str], judged_at: str) -> None:
    if judged_at:
        out.extend(["[run]", f"judged_at = {json.dumps(judged_at)}", ""])


def _append_excluded(out: list[str]) -> None:
    for modelo_id, excluded in sorted(EXCLUDED_MODELOS.items()):
        out.extend(["[[excluded]]", f"modelo = {json.dumps(modelo_id)}", f"reason = {json.dumps(excluded.reason)}", ""])


def _append_load_failures(out: list[str], load_failures: Iterable[ModeloLoadFailure]) -> None:
    for failure in sorted(load_failures, key=lambda entry: entry.modelo):
        out.extend(
            [
                "[[load_failed]]",
                f"modelo = {json.dumps(failure.modelo)}",
                f"reason = {json.dumps(failure.reason, ensure_ascii=False)}",
                "",
            ]
        )


def _append_partial_stampings(out: list[str], partial_stampings: Iterable[PartialStamping]) -> None:
    for record in sorted(partial_stampings, key=lambda entry: (entry.modelo, entry.casilla)):
        out.extend(
            [
                "[[stamping_in_progress]]",
                f"modelo = {json.dumps(record.modelo)}",
                f"casilla = {json.dumps(record.casilla, ensure_ascii=False)}",
                f"chain = {json.dumps(record.chain, ensure_ascii=False)}",
                f"stamped = {json.dumps(list(record.stamped), ensure_ascii=False)}",
                f"unstamped = {json.dumps(list(record.unstamped), ensure_ascii=False)}",
                "",
            ]
        )


def _append_excluded_contradictions(out: list[str], excluded_contradictions: Mapping[str, list[str]] | None) -> None:
    for modelo_id, problems in sorted((excluded_contradictions or {}).items()):
        out.extend(
            [
                "[[excluded_contradiction]]",
                f"modelo = {json.dumps(modelo_id)}",
                "contradictions = [",
                *(f"  {json.dumps(problem, ensure_ascii=False)}," for problem in problems),
                "]",
                "",
            ]
        )


def _append_summaries(out: list[str], plans: list[LineagePlan], checks: Mapping[str, list[str]]) -> None:
    for plan in plans:
        _append_summary(out, plan, checks[plan.modelo])


def _append_summary(out: list[str], plan: LineagePlan, problems: list[str]) -> None:
    out.append(f"[summary.{json.dumps(plan.modelo)}]")
    # Chain starts are an artefact of one write, not a disposition; the rows carry them.
    out.extend([f"{json.dumps(key)} = {value}" for key, value in sorted(plan.counts.items()) if key != "chain_start"])
    out.append(f"contradictions = {len(problems)}")
    if plan.notes:
        out.append("notes = [")
        out.extend([f"  {json.dumps(note, ensure_ascii=False)}," for note in plan.notes])
        out.append("]")
    out.append("")


def _append_current_refusals(out: list[str], plans: list[LineagePlan]) -> set[tuple[str, str, str]]:
    judged: set[tuple[str, str, str]] = set()
    for plan in plans:
        for refusal in plan.refusals:
            judged.add((refusal.modelo, refusal.revision, refusal.casilla_id))
            _append_refusal(
                out,
                refusal.modelo,
                refusal.revision,
                refusal.casilla_id,
                refusal.category,
                refusal.reason,
                refusal.predecessor,
            )
    return judged


def _append_refusal(
    out: list[str], modelo: str, revision: str, casilla: str, category: str, reason: str, predecessor: str | None
) -> None:
    out.extend(
        [
            "[[refusal]]",
            f"modelo = {json.dumps(modelo)}",
            f"revision = {json.dumps(revision)}",
            f"casilla = {json.dumps(casilla, ensure_ascii=False)}",
        ]
    )
    if predecessor is not None:
        out.append(f"predecessor = {json.dumps(predecessor, ensure_ascii=False)}")
    out.extend([f"category = {json.dumps(category)}", f"reason = {json.dumps(reason, ensure_ascii=False)}", ""])


def _append_carried_refusals(
    out: list[str], carried: Iterable[CarriedRefusal], judged: set[tuple[str, str, str]]
) -> None:
    for entry in sorted(carried, key=lambda record: record.key):
        if entry.key in judged:
            raise ValueError(f"carried refusal {entry.key} is also judged in this run")
        _append_carried_refusal(out, entry)


def _append_carried_refusal(out: list[str], entry: CarriedRefusal) -> None:
    _append_refusal(out, entry.modelo, entry.revision, entry.casilla, entry.category, entry.reason, entry.predecessor)
    out[-1:-1] = [
        "carried_from_previous_run = true",
        f"carried_reason = {json.dumps(entry.carried_reason, ensure_ascii=False)}",
        f"last_judged = {json.dumps(entry.last_judged)}",
        f"carried_runs = {entry.carried_runs}",
    ]
