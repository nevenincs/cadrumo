"""Measure paired authority workloads in independent Python processes."""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Callable
from multiprocessing import get_context
from pathlib import Path
from time import perf_counter
from typing import cast

_MODEL_WORKLOADS = {
    "modelo-100": ("100", 2025, "0A", "applicability"),
    "modelo-200": ("200", 2025, "0A", "applicability"),
    "modelo-303": ("303", 2025, "4T", "filing"),
}
_AUXILIARY_WORKLOADS = ("fact", "profile", "evidence", "enumeration")
_WORKLOADS = (*_MODEL_WORKLOADS, *_AUXILIARY_WORKLOADS)


def _measure_sample(specification: tuple[str, str | None, str]) -> dict[str, object]:
    """Measure one workload/backend pair inside one fresh worker process."""
    backend, resource, workload = specification
    if backend == "sqlite":
        if resource is None:
            raise ValueError("sqlite benchmark sample requires a descriptor")
        return measure_sqlite_authority(Path(resource), workload=workload)
    return measure_json_authority(None if resource is None else Path(resource), workload=workload)


def _median(samples: list[dict[str, object]], member: str) -> float:
    return statistics.median(cast(float, sample[member]) for sample in samples)


def _summary(samples: list[dict[str, object]]) -> dict[str, object]:
    """Keep workload medians separate so no failing modelo can be averaged away."""
    by_workload: dict[str, list[dict[str, object]]] = {}
    for sample in samples:
        by_workload.setdefault(str(sample["workload"]), []).append(sample)
    workloads: dict[str, object] = {}
    for workload, rows in sorted(by_workload.items()):
        summary: dict[str, object] = {
            "runs": len(rows),
            "post_import_admission_and_first_median_seconds": _median(rows, "post_import_admission_and_first_seconds"),
            "incremental_authority_rss_median_bytes": _median(rows, "incremental_authority_rss_bytes"),
        }
        if workload in _MODEL_WORKLOADS:
            summary["warm_context_median_seconds"] = _median(rows, "warm_context_median_seconds")
        workloads[workload] = summary
    return {
        "backend": str(samples[0]["backend"]),
        "fresh_processes": len(samples),
        "workloads": workloads,
    }


def _timed[T](operation: Callable[[], T]) -> tuple[T, float]:
    started = perf_counter()
    return operation(), perf_counter() - started


def measure_json_authority(artifact_path: Path | None = None, *, workload: str) -> dict[str, object]:
    """Measure one eager-JSON baseline workload from the captured generation."""
    import psutil

    process = psutil.Process()
    started = perf_counter()
    from cadrumo.core.authority_grade import RegistryAuthorityGrade
    from dev.registry.authority_json import bundled_authority_json_path, published_authority, read_authority_artifact

    imported = perf_counter()
    rss_before = process.memory_info().rss
    selected_artifact = artifact_path or bundled_authority_json_path()
    authority, admission = _timed(lambda: published_authority(selected_artifact))
    first_started = perf_counter()
    warm_context = 0.0
    detail: dict[str, object] = {}
    if workload in _MODEL_WORKLOADS:
        modelo, year, period, grade_name = _MODEL_WORKLOADS[workload]
        grade = RegistryAuthorityGrade(grade_name)
        snapshot = authority.snapshot(modelo, filing_year=year, period=period, grade=grade)
        timings: list[float] = []
        for _ in range(100):
            repeated, elapsed = _timed(lambda: authority.snapshot(modelo, filing_year=year, period=period, grade=grade))
            if repeated is not snapshot:
                raise AssertionError("a repeated immutable snapshot was not shared")
            timings.append(elapsed)
        warm_context = statistics.median(timings)
        detail = {"modelo": modelo, "revision": str(snapshot.revision.id)}
    elif workload == "fact":
        fact_id = sorted(authority.catalogues.facts.facts)[0]
        detail = {"fact_id": str(authority.catalogues.facts.facts[fact_id].fact_id)}
    elif workload == "profile":
        detail = {"profile_schema": authority.profile_schema().id}
    elif workload == "evidence":
        detail = {"legal_evidence": authority.evidence.legal[0].legal_reference_id}
    elif workload == "enumeration":
        revisions = tuple(revision for modelo in authority.modelos for revision in modelo.revisions.values())
        detail = {"modelos": len(authority.modelos), "revisions": len(revisions)}
    else:
        raise ValueError(f"unknown benchmark workload {workload!r}")
    first = perf_counter() - first_started
    return {
        "backend": "json",
        "workload": workload,
        "import_seconds": imported - started,
        "admission_seconds_after_import": admission,
        "first_operation_seconds": first,
        "post_import_admission_and_first_seconds": admission + first,
        "incremental_authority_rss_bytes": process.memory_info().rss - rss_before,
        "warm_context_median_seconds": warm_context,
        "identity_digest": read_authority_artifact(selected_artifact).identity_digest,
        "detail": detail,
    }


def measure_sqlite_authority(descriptor_path: Path, *, workload: str) -> dict[str, object]:
    """Measure one independently admitted on-demand SQLite workload."""
    import psutil

    process = psutil.Process()
    started = perf_counter()
    from cadrumo.core.authority_grade import RegistryAuthorityGrade
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
    from cadrumo.domain.calculations.registry.authority_artifact import (
        AuthorityComponentKind,
        EvidenceComponentQuery,
        GovernedFactComponentQuery,
    )
    from cadrumo.domain.calculations.registry.authority_store import SQLiteAuthorityReader

    imported = perf_counter()
    rss_before = process.memory_info().rss
    reader, admission = _timed(lambda: SQLiteAuthorityReader(descriptor_path))
    warm_context = 0.0
    detail: dict[str, object] = {}
    try:
        first_started = perf_counter()
        with reader.lease() as pin:
            operation = PinnedAuthorityOperation(reader, pin)
            if workload in _MODEL_WORKLOADS:
                modelo, year, period, grade_name = _MODEL_WORKLOADS[workload]
                snapshot = operation.snapshot(
                    modelo,
                    filing_year=year,
                    period=period,
                    grade=RegistryAuthorityGrade(grade_name),
                )
                first = perf_counter() - first_started
                timings: list[float] = []
                for _ in range(100):
                    _selected, elapsed = _timed(
                        lambda: operation.revision_for_context(modelo, filing_year=year, period=period)
                    )
                    timings.append(elapsed)
                warm_context = statistics.median(timings)
                detail = {"modelo": modelo, "revision": str(snapshot.revision.id)}
            elif workload == "fact":
                query = next(
                    query for query in reader.component_queries() if isinstance(query, GovernedFactComponentQuery)
                )
                fact = operation.governed_fact(query.fact_id)
                first = perf_counter() - first_started
                detail = {"fact_id": str(fact.fact_id)}
            elif workload == "profile":
                profile = operation.profile_schema()
                first = perf_counter() - first_started
                detail = {"profile_schema": profile.id}
            elif workload == "evidence":
                query = next(
                    query
                    for query in reader.component_queries()
                    if isinstance(query, EvidenceComponentQuery) and query.kind is AuthorityComponentKind.LEGAL_EVIDENCE
                )
                evidence = operation.legal_evidence(query.reference_id)
                first = perf_counter() - first_started
                detail = {"legal_evidence": evidence.legal_reference_id}
            elif workload == "enumeration":
                detail = {
                    "modelos": len(operation.modelo_ids()),
                    "revisions": len(operation.revision_ids()),
                }
                first = perf_counter() - first_started
            else:
                raise ValueError(f"unknown benchmark workload {workload!r}")
        telemetry = reader.telemetry()
        return {
            "backend": "sqlite",
            "workload": workload,
            "import_seconds": imported - started,
            "admission_seconds_after_import": admission,
            "first_operation_seconds": first,
            "post_import_admission_and_first_seconds": admission + first,
            "incremental_authority_rss_bytes": process.memory_info().rss - rss_before,
            "warm_context_median_seconds": warm_context,
            "identity_digest": reader.pin().logical_generation,
            "detail": detail,
            "cache": {
                "budget": telemetry.budget,
                "retained_weight": telemetry.retained_weight,
                "entries": telemetry.entries,
            },
        }
    finally:
        reader.close()


def main() -> None:
    """Print raw independent samples and release-relevant workload medians."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--backend", choices=("json", "sqlite"), default="json")
    parser.add_argument("--descriptor", type=Path)
    parser.add_argument("--artifact", type=Path, help="JSON baseline artifact from the same validated generation")
    parser.add_argument("--workload", choices=_WORKLOADS)
    parser.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.backend == "sqlite" and args.descriptor is None:
        parser.error("--backend sqlite requires --descriptor")
    workloads = (args.workload,) if args.workload else _WORKLOADS
    if args.sample:
        if len(workloads) != 1:
            parser.error("--sample requires --workload")
        measured = (
            measure_sqlite_authority(args.descriptor, workload=workloads[0])
            if args.backend == "sqlite"
            else measure_json_authority(args.artifact, workload=workloads[0])
        )
        print(json.dumps(measured, sort_keys=True))
        return
    if args.runs < 10:
        parser.error("release comparison requires at least 10 fresh processes per workload")
    selected_path = args.descriptor if args.backend == "sqlite" else args.artifact
    resource = None if selected_path is None else str(selected_path.resolve())
    specifications = [(args.backend, resource, workload) for workload in workloads for _ in range(args.runs)]
    with get_context("spawn").Pool(processes=1, maxtasksperchild=1) as workers:
        samples = workers.map(_measure_sample, specifications, chunksize=1)
    print(json.dumps({"samples": samples, "summary": _summary(samples)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
