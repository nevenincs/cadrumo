"""Measure the installed authority API in independent Python processes."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import date
from multiprocessing import get_context
from pathlib import Path
from time import perf_counter


def _measure_sample(specification: tuple[str, str | None]) -> dict[str, object]:
    """Measure one backend inside a freshly spawned worker process."""
    backend, descriptor = specification
    if backend == "sqlite":
        if descriptor is None:
            raise ValueError("sqlite benchmark sample requires a descriptor")
        return measure_sqlite_authority(Path(descriptor))
    return measure_json_authority()


def measure_json_authority() -> dict[str, object]:
    """Measure import, hydration, representative queries, and process memory."""
    import psutil

    started = perf_counter()
    from cadrumo.core.authority_grade import RegistryAuthorityGrade
    from cadrumo.domain.calculations.registry.authority import bundled_authority, bundled_authority_artifact_path
    from cadrumo.domain.calculations.registry.authority_artifact import read_shared_authority_artifact

    imported = perf_counter()
    authority = bundled_authority()
    loaded = perf_counter()
    observations: list[dict[str, object]] = []
    for modelo, year, period, grade in (
        ("100", 2025, "0A", RegistryAuthorityGrade.APPLICABILITY),
        ("200", 2025, "0A", RegistryAuthorityGrade.APPLICABILITY),
        ("303", 2025, "4T", RegistryAuthorityGrade.FILING),
    ):
        before = perf_counter()
        snapshot = authority.snapshot(modelo, filing_year=year, period=period, grade=grade)
        first = perf_counter() - before
        timings: list[float] = []
        for _ in range(100):
            before = perf_counter()
            repeated = authority.snapshot(modelo, filing_year=year, period=period, grade=grade)
            timings.append(perf_counter() - before)
            if repeated is not snapshot:
                raise AssertionError("a repeated immutable snapshot was not shared")
        observations.append(
            {"modelo": modelo, "first_seconds": first, "warm_median_seconds": statistics.median(timings)}
        )
    public_query_timings: list[float] = []
    for _ in range(100):
        before = perf_counter()
        repeated = bundled_authority().snapshot("303", filing_year=2025, period="4T")
        public_query_timings.append(perf_counter() - before)
        if repeated is not snapshot:
            raise AssertionError("the bundled entry point did not share the current snapshot")
    before = perf_counter()
    revisions = tuple(revision for modelo in authority.modelos for revision in modelo.revisions.values())
    casillas = sum(len(revision.casillas) for revision in revisions)
    enumeration = perf_counter() - before
    memory = psutil.Process().memory_info()
    return {
        "backend": "json",
        "date": date.today().isoformat(),
        "identity_digest": read_shared_authority_artifact(bundled_authority_artifact_path()).identity_digest,
        "import_seconds": imported - started,
        "load_seconds_after_import": loaded - imported,
        "import_and_load_seconds": loaded - started,
        "rss_bytes_after_queries": memory.rss,
        "peak_working_set_bytes": getattr(memory, "peak_wset", None),
        "modelos": len(authority.modelos),
        "revisions": len(revisions),
        "casillas": casillas,
        "enumeration_seconds": enumeration,
        "bundled_m303_query_median_seconds": statistics.median(public_query_timings),
        "snapshots": observations,
    }


def measure_sqlite_authority(descriptor_path: Path) -> dict[str, object]:
    """Measure full admission and independent on-demand component workloads."""
    import psutil

    process = psutil.Process()
    started = perf_counter()
    from cadrumo.domain.calculations.registry.authority_artifact import (
        AuthorityComponentKind,
        EvidenceComponentQuery,
        GovernedFactComponentQuery,
        ModeloRevisionComponentQuery,
        ProfileSchemaComponentQuery,
    )
    from cadrumo.domain.calculations.registry.authority_store import SQLiteAuthorityReader

    imported = perf_counter()
    rss_before = process.memory_info().rss
    reader = SQLiteAuthorityReader(descriptor_path)
    admitted = perf_counter()
    rss_after_admission = process.memory_info().rss
    observations: list[dict[str, object]] = []
    try:
        with reader.lease() as pin:
            for modelo, revision in (("100", "2025"), ("200", "2025-y-siguientes"), ("303", "2025")):
                query = ModeloRevisionComponentQuery(modelo, revision)
                before = perf_counter()
                selected = reader.load(query, pin=pin)
                first = perf_counter() - before
                timings: list[float] = []
                for _ in range(100):
                    before = perf_counter()
                    repeated = reader.load(query, pin=pin)
                    timings.append(perf_counter() - before)
                    if repeated is not selected:
                        raise AssertionError("a repeated immutable component was not shared")
                observations.append(
                    {
                        "modelo": modelo,
                        "first_seconds": first,
                        "warm_median_seconds": statistics.median(timings),
                    }
                )
            directory = reader.component_queries()
            workload_queries = {
                "profile": next(query for query in directory if isinstance(query, ProfileSchemaComponentQuery)),
                "fact": next(query for query in directory if isinstance(query, GovernedFactComponentQuery)),
                "evidence": next(
                    query
                    for query in directory
                    if isinstance(query, EvidenceComponentQuery) and query.kind is AuthorityComponentKind.LEGAL_EVIDENCE
                ),
            }
            workloads: dict[str, float] = {}
            for name, query in workload_queries.items():
                before = perf_counter()
                reader.load(query, pin=pin)
                workloads[name] = perf_counter() - before
            before = perf_counter()
            component_count = len(reader.component_queries())
            enumeration = perf_counter() - before
        memory = process.memory_info()
        telemetry = reader.telemetry()
        return {
            "backend": "sqlite",
            "date": date.today().isoformat(),
            "identity_digest": reader.pin().logical_generation,
            "import_seconds": imported - started,
            "admission_seconds_after_import": admitted - imported,
            "import_and_admission_seconds": admitted - started,
            "rss_bytes_before_admission": rss_before,
            "rss_bytes_after_admission": rss_after_admission,
            "incremental_rss_bytes": memory.rss - rss_before,
            "rss_bytes_after_queries": memory.rss,
            "peak_working_set_bytes": getattr(memory, "peak_wset", None),
            "component_count": component_count,
            "enumeration_seconds": enumeration,
            "workloads": workloads,
            "cache": {
                "budget": telemetry.budget,
                "retained_weight": telemetry.retained_weight,
                "entries": telemetry.entries,
            },
            "snapshots": observations,
        }
    finally:
        reader.close()


def main() -> None:
    """Print JSON measurements; each sample imports and loads in a fresh process."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--backend", choices=("json", "sqlite"), default="json")
    parser.add_argument("--descriptor", type=Path)
    parser.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.sample:
        if args.backend == "sqlite":
            if args.descriptor is None:
                parser.error("--backend sqlite requires --descriptor")
            measured = measure_sqlite_authority(args.descriptor)
        else:
            measured = measure_json_authority()
        print(json.dumps(measured, sort_keys=True))
        return
    if args.runs < 1:
        parser.error("--runs must be positive")
    if args.backend == "sqlite" and args.descriptor is None:
        parser.error("--backend sqlite requires --descriptor")
    descriptor = None if args.descriptor is None else str(args.descriptor.resolve())
    specifications = [(args.backend, descriptor)] * args.runs
    with get_context("spawn").Pool(processes=1, maxtasksperchild=1) as workers:
        # ``Pool.map`` otherwise batches several samples into one task.  Since
        # ``maxtasksperchild`` counts batches rather than individual iterable
        # members, the default chunksize silently reused one interpreter for
        # multiple measurements and turned most "cold" samples warm.
        samples = workers.map(_measure_sample, specifications, chunksize=1)
    print(json.dumps({"samples": samples}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
