"""Measure the development-only eager JSON baseline against indexed SQLite.

The JSON baseline is an explicit file produced from the same validated
``AuthorityArtifact`` as the candidate database by
``dev.registry.eager_authority_baseline``.  This driver never discovers a
bundled JSON resource and never supplies a product fallback.  Each worker
admits one descriptor/database pair and eagerly decodes the complete JSON
graph or measures the indexed reader's full admission before one equivalent
workload.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Callable
from multiprocessing import get_context
from pathlib import Path
from time import perf_counter
from typing import Any, cast

_MODEL_WORKLOADS: dict[str, tuple[str, int, str, str]] = {
    "modelo-100": ("100", 2025, "0A", "applicability"),
    "modelo-200": ("200", 2025, "0A", "applicability"),
    "modelo-303": ("303", 2025, "4T", "filing"),
}
_AUXILIARY_WORKLOADS = ("fact", "profile", "evidence", "enumeration")
WORKLOADS = (*_MODEL_WORKLOADS, *_AUXILIARY_WORKLOADS)


def _timed[T](operation: Callable[[], T]) -> tuple[T, float]:
    started = perf_counter()
    return operation(), perf_counter() - started


def _candidate_identity(descriptor_path: Path) -> tuple[str, str, int]:
    """Validate the explicit candidate bytes before measuring either backend."""
    from cadrumo.core.hashing import sha256_hex
    from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

    descriptor = AuthorityDescriptor.read(descriptor_path.resolve(strict=True))
    database = descriptor_path.resolve().parent / descriptor.database
    payload = database.read_bytes()
    if len(payload) != descriptor.database_size or sha256_hex(payload) != descriptor.database_sha256:
        raise ValueError("candidate descriptor/database bytes disagree")
    return descriptor.logical_generation, descriptor.database_sha256, descriptor.database_size


def _load_eager_authority(baseline_path: Path) -> Any:
    """Read and materialise the complete development baseline graph."""
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
    from dev.registry.eager_authority_baseline import read_eager_authority_baseline

    artifact = read_eager_authority_baseline(baseline_path.resolve(strict=True))
    authority = ValidatedRegistryAuthority.from_validated_components(
        modelos=artifact.modelos,
        catalogues=artifact.catalogues,
        identity_digest=artifact.identity_digest,
        evidence=artifact.evidence,
        profile_schema=artifact.profile_schema,
    )
    return authority, artifact.identity_digest


def _warm_revision_lookup(authority: Any, workload: str) -> float:
    from cadrumo.domain.calculations.registry.temporal import select_revision

    modelo_id, filing_year, period, _grade = _MODEL_WORKLOADS[workload]
    modelo = authority.modelo(modelo_id)
    support = authority.catalogues.supported_filing_years
    timings: list[float] = []
    for _ in range(100):
        _selected, elapsed = _timed(
            lambda: select_revision(modelo, filing_year=filing_year, period=period, support=support)
        )
        timings.append(elapsed)
    return float(statistics.median(timings))


def measure_json_authority(
    baseline_path: Path,
    descriptor_path: Path,
    *,
    workload: str,
) -> dict[str, object]:
    """Measure full eager-baseline admission plus one equivalent operation."""
    import psutil

    from cadrumo.core.authority_grade import RegistryAuthorityGrade

    process = psutil.Process()
    started = perf_counter()
    generation, database_sha256, database_size = _candidate_identity(descriptor_path)
    imported = perf_counter()
    rss_before = process.memory_info().rss
    (authority, baseline_generation), admission = _timed(lambda: _load_eager_authority(baseline_path))
    if baseline_generation != generation:
        raise ValueError("JSON baseline and candidate have different logical generations")
    first_started = perf_counter()
    warm_context = 0.0
    if workload in _MODEL_WORKLOADS:
        modelo, filing_year, period, grade_name = _MODEL_WORKLOADS[workload]
        snapshot = authority.snapshot(
            modelo,
            filing_year=filing_year,
            period=period,
            grade=RegistryAuthorityGrade(grade_name),
        )
        detail: dict[str, object] = {"modelo": modelo, "revision": str(snapshot.revision.id)}
        warm_context = _warm_revision_lookup(authority, workload)
    elif workload == "fact":
        fact_id = min(authority.catalogues.facts.facts)
        detail = {"fact_id": str(authority.catalogues.facts.facts[fact_id].fact_id)}
    elif workload == "profile":
        detail = {"profile_schema": authority.profile_schema().id}
    elif workload == "evidence":
        evidence = min(authority.evidence.legal, key=lambda item: item.legal_reference_id)
        detail = {"legal_evidence": evidence.legal_reference_id}
    elif workload == "enumeration":
        detail = {
            "modelos": len(authority.modelos),
            "revisions": sum(len(modelo.revisions) for modelo in authority.modelos),
        }
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
        "incremental_authority_rss_bytes": max(0, process.memory_info().rss - rss_before),
        "warm_context_median_seconds": warm_context,
        "identity_digest": generation,
        "database_sha256": database_sha256,
        "database_size": database_size,
        "detail": detail,
    }


def measure_sqlite_authority(descriptor_path: Path, *, workload: str) -> dict[str, object]:
    """Measure SQLite's complete admission plus one equivalent operation."""
    import psutil

    from cadrumo.core.authority_grade import RegistryAuthorityGrade
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
    from cadrumo.domain.calculations.registry.authority_artifact import (
        AuthorityComponentKind,
        EvidenceComponentQuery,
        GovernedFactComponentQuery,
    )
    from cadrumo.domain.calculations.registry.authority_store import SQLiteAuthorityReader
    from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

    process = psutil.Process()
    started = perf_counter()
    _candidate_identity(descriptor_path)
    imported = perf_counter()
    rss_before = process.memory_info().rss
    reader, admission = _timed(lambda: SQLiteAuthorityReader(descriptor_path))
    try:
        with reader.lease() as pin:
            operation = PinnedAuthorityOperation(reader, pin)
            with validating_governed_facts(operation):
                first_started = perf_counter()
                warm_context = 0.0
                if workload in _MODEL_WORKLOADS:
                    modelo, filing_year, period, grade_name = _MODEL_WORKLOADS[workload]
                    snapshot = operation.snapshot(
                        modelo,
                        filing_year=filing_year,
                        period=period,
                        grade=RegistryAuthorityGrade(grade_name),
                    )
                    detail: dict[str, object] = {"modelo": modelo, "revision": str(snapshot.revision.id)}
                    timings: list[float] = []
                    for _ in range(100):
                        _selected, elapsed = _timed(
                            lambda: operation.revision_for_context(
                                modelo,
                                filing_year=filing_year,
                                period=period,
                            )
                        )
                        timings.append(elapsed)
                    warm_context = float(statistics.median(timings))
                elif workload == "fact":
                    query = min(
                        (
                            query
                            for query in reader.component_queries()
                            if isinstance(query, GovernedFactComponentQuery)
                        ),
                        key=lambda item: item.fact_id,
                    )
                    detail = {"fact_id": str(operation.governed_fact(query.fact_id).fact_id)}
                elif workload == "profile":
                    detail = {"profile_schema": operation.profile_schema().id}
                elif workload == "evidence":
                    query = min(
                        (
                            query
                            for query in reader.component_queries()
                            if isinstance(query, EvidenceComponentQuery)
                            and query.kind is AuthorityComponentKind.LEGAL_EVIDENCE
                        ),
                        key=lambda item: item.reference_id,
                    )
                    detail = {"legal_evidence": operation.legal_evidence(query.reference_id).legal_reference_id}
                elif workload == "enumeration":
                    detail = {"modelos": len(operation.modelo_ids()), "revisions": len(operation.revision_ids())}
                else:
                    raise ValueError(f"unknown benchmark workload {workload!r}")
                first = perf_counter() - first_started
        telemetry = reader.telemetry()
        generation = reader.pin().logical_generation
        return {
            "backend": "sqlite",
            "workload": workload,
            "import_seconds": imported - started,
            "admission_seconds_after_import": admission,
            "first_operation_seconds": first,
            "post_import_admission_and_first_seconds": admission + first,
            "incremental_authority_rss_bytes": max(0, process.memory_info().rss - rss_before),
            "warm_context_median_seconds": warm_context,
            "identity_digest": generation,
            "detail": detail,
            "cache": {
                "budget": telemetry.budget,
                "retained_weight": telemetry.retained_weight,
                "entries": telemetry.entries,
            },
        }
    finally:
        reader.close()


def _measure_sample(specification: tuple[str, str, str, str]) -> dict[str, object]:
    backend, descriptor, baseline, workload = specification
    if backend == "json":
        return measure_json_authority(Path(baseline), Path(descriptor), workload=workload)
    return measure_sqlite_authority(Path(descriptor), workload=workload)


def _median(samples: list[dict[str, object]], member: str) -> float:
    return float(statistics.median(float(cast(float, sample[member])) for sample in samples))


def _summary(samples: list[dict[str, object]]) -> dict[str, object]:
    """Keep backend/workload medians and semantic parity separate."""
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for sample in samples:
        grouped.setdefault((str(sample["backend"]), str(sample["workload"])), []).append(sample)
    result: dict[str, object] = {}
    for backend in sorted({key[0] for key in grouped}):
        workloads: dict[str, object] = {}
        backend_rows = [row for (name, _workload), rows in grouped.items() if name == backend for row in rows]
        for workload in sorted({key[1] for key in grouped if key[0] == backend}):
            rows = grouped[(backend, workload)]
            entry: dict[str, object] = {
                "runs": len(rows),
                "post_import_admission_and_first_median_seconds": _median(
                    rows, "post_import_admission_and_first_seconds"
                ),
                "incremental_authority_rss_median_bytes": _median(rows, "incremental_authority_rss_bytes"),
            }
            if workload in _MODEL_WORKLOADS:
                entry["warm_context_median_seconds"] = _median(rows, "warm_context_median_seconds")
            workloads[workload] = entry
        result[backend] = {"fresh_processes": len(backend_rows), "workloads": workloads}
    paired: dict[str, object] = {}
    for workload in sorted({key[1] for key in grouped}):
        json_rows = grouped.get(("json", workload), [])
        sqlite_rows = grouped.get(("sqlite", workload), [])
        if not json_rows or not sqlite_rows:
            continue
        paired[workload] = {
            "identity_digest_equal": {str(row["identity_digest"]) for row in json_rows}
            == {str(row["identity_digest"]) for row in sqlite_rows},
            "operation_detail_equal": {json.dumps(row["detail"], sort_keys=True) for row in json_rows}
            == {json.dumps(row["detail"], sort_keys=True) for row in sqlite_rows},
        }
    result["paired_semantics"] = paired
    return result


def main() -> None:
    """Print raw samples and independent workload medians."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", required=True, type=Path)
    parser.add_argument(
        "--json-baseline",
        required=True,
        type=Path,
        help="explicit baseline written by dev.registry.eager_authority_baseline",
    )
    parser.add_argument("--backend", choices=("both", "json", "sqlite"), default="both")
    parser.add_argument("--workload", choices=WORKLOADS)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--sample", action="store_true", help="run one sample; otherwise require release count")
    args = parser.parse_args()
    if args.runs < 10 and not args.sample:
        parser.error("release comparison requires at least 10 fresh processes per workload")
    workloads = (args.workload,) if args.workload else WORKLOADS
    backends = ("json", "sqlite") if args.backend == "both" else (args.backend,)
    descriptor = str(args.descriptor.resolve(strict=True))
    baseline = str(args.json_baseline.resolve(strict=True))
    if args.sample:
        if len(workloads) != 1 or len(backends) != 1:
            parser.error("--sample requires exactly one --backend and one --workload")
        print(json.dumps(_measure_sample((backends[0], descriptor, baseline, workloads[0])), sort_keys=True))
        return
    specifications = [
        (backend, descriptor, baseline, workload)
        for workload in workloads
        for backend in backends
        for _ in range(args.runs)
    ]
    with get_context("spawn").Pool(processes=1, maxtasksperchild=1) as workers:
        samples = workers.map(_measure_sample, specifications, chunksize=1)
    print(json.dumps({"samples": samples, "summary": _summary(samples)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
