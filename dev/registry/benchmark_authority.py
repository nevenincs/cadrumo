"""Measure the installed authority API in independent Python processes."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import date
from time import perf_counter


def measure_authority() -> dict[str, object]:
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


def main() -> None:
    """Print JSON measurements; each sample imports and loads in a fresh process."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.sample:
        print(json.dumps(measure_authority(), sort_keys=True))
        return
    if args.runs < 1:
        parser.error("--runs must be positive")
    samples = [
        json.loads(
            subprocess.check_output(
                [sys.executable, "-m", "dev.registry.benchmark_authority", "--sample"],
                text=True,
                encoding="utf-8",
            )
        )
        for _ in range(args.runs)
    ]
    print(json.dumps({"samples": samples}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
