"""Import ratchet."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Final, cast

from dev._paths import UTF_8

from .import_check_models import Authority
from .import_health_models import (
    RATCHET_SCHEMA_VERSION,
    CandidateInventory,
    OccurrenceRow,
    RatchetCounts,
    RatchetEntry,
    RatchetReport,
)
from .import_ratchet_validation import validate_ratchet_entry
from .import_retirement_evidence import is_source_module_removal, valid_retirement
from .import_root_boundaries import crosses_root_boundary, source_module_exists

RATCHET_RELATIVE_PATH: Final[Path] = Path("dev/quality/metadata/import_boundary_ratchet.json")


def reconcile_ratchet(
    authority: Authority,
    candidate: CandidateInventory,
    root_boundaries: frozenset[tuple[str, str]],
) -> RatchetReport:
    """Account for current occurrences, approved debt, and evidenced retirements."""
    repository = authority.repository
    path = repository / RATCHET_RELATIVE_PATH
    rows = candidate["occurrences"]
    current, boundary_rows, details = _partition_boundary_occurrences(rows, root_boundaries)
    counts: Counter[str] = Counter(
        {
            "approved_active": 0,
            "root_boundary": sum(int(row["multiplicity"]) for row in boundary_rows),
            "new_unapproved": 0,
            "expanded_existing": 0,
            "expired": 0,
            "malformed": 0,
            "regressed_retired": 0,
            "retirement_candidates": 0,
            "retirement_ready": 0,
            "retired_verified": 0,
            "retired_source_removed": 0,
        }
    )
    if not path.is_file():
        counts["new_unapproved"] = sum(int(row["multiplicity"]) for row in current.values())
        baseline_status = "not_required" if not current else "unestablished"
        details["new_unapproved"].extend(current)
        return {
            "baseline_status": baseline_status,
            "counts": ratchet_counts(counts),
            "detail_counts": {key: len(values) for key, values in sorted(details.items())},
            "details": {key: sorted(values)[:20] for key, values in sorted(details.items())},
            "path": str(path),
            "schema_version": RATCHET_SCHEMA_VERSION,
        }

    entries = _read_ratchet_entries(path, counts)
    if isinstance(entries, dict):
        return entries

    approved: dict[str, RatchetEntry] = {}
    today = date.today()
    for index, raw in enumerate(entries):
        _account_ratchet_entry(
            authority, repository, index, raw, root_boundaries, approved, current, today, counts, details
        )

    _account_unapproved_occurrences(current, approved, counts, details)
    return _ratchet_report(path, counts, details)


def ratchet_counts(counts: Counter[str]) -> RatchetCounts:
    """Materialize the closed ratchet-count schema from its mutable counter."""
    return {
        "approved_active": counts["approved_active"],
        "root_boundary": counts["root_boundary"],
        "new_unapproved": counts["new_unapproved"],
        "expanded_existing": counts["expanded_existing"],
        "expired": counts["expired"],
        "malformed": counts["malformed"],
        "regressed_retired": counts["regressed_retired"],
        "retirement_candidates": counts["retirement_candidates"],
        "retirement_ready": counts["retirement_ready"],
        "retired_verified": counts["retired_verified"],
        "retired_source_removed": counts["retired_source_removed"],
    }


def _account_ratchet_entry(
    authority: Authority,
    repository: Path,
    index: int,
    raw: object,
    root_boundaries: frozenset[tuple[str, str]],
    approved: dict[str, RatchetEntry],
    current: dict[str, OccurrenceRow],
    today: date,
    counts: Counter[str],
    details: defaultdict[str, list[str]],
) -> None:
    """Account ratchet entry."""
    if not isinstance(raw, dict):
        counts["malformed"] += 1
        details["malformed"].append(f"entry {index} is not an object")
        return
    raw = cast("dict[str, object]", raw)
    fingerprint = str(raw.get("fingerprint", ""))
    if not fingerprint or fingerprint in approved:
        counts["malformed"] += 1
        details["malformed"].append(f"entry {index} has missing or duplicate fingerprint")
        return
    validated = validate_ratchet_entry(raw)
    if isinstance(validated, str):
        counts["malformed"] += 1
        details["malformed"].append(f"{fingerprint}: {validated}")
        return
    if crosses_root_boundary(validated["source_module"], validated["target_module"], root_boundaries):
        counts["malformed"] += 1
        details["malformed"].append(f"{fingerprint}: a shipped root reaching a repository-only root is not debt")
        return
    approved[fingerprint] = validated
    allowed = validated["multiplicity"]
    observed = _observed_multiplicity(current.get(fingerprint))
    status = validated["status"]
    expires = date.fromisoformat(validated["expires_on"])
    if status == "retired":
        _account_retired_entry(authority, repository, raw, validated, fingerprint, allowed, observed, counts, details)
        return
    _account_active_entry(
        authority, repository, raw, validated, fingerprint, allowed, observed, expires, today, counts, details
    )


def _account_retired_entry(
    authority: Authority,
    repository: Path,
    raw: dict[str, object],
    validated: RatchetEntry,
    fingerprint: str,
    allowed: int,
    observed: int,
    counts: Counter[str],
    details: defaultdict[str, list[str]],
) -> None:
    """Account retired entry."""
    if observed:
        counts["regressed_retired"] += observed
        details["regressed_retired"].append(fingerprint)
    elif is_source_module_removal(raw.get("retirement")):
        source_module = validated["source_module"]
        if source_module_exists(authority, source_module):
            counts["malformed"] += allowed
            details["malformed"].append(
                f"{fingerprint}: retirement claims {source_module} was removed, but it still exists"
            )
        else:
            counts["retired_source_removed"] += allowed
            details["retired_source_removed"].append(fingerprint)
    elif valid_retirement(raw.get("retirement"), repository, validated["capability"]):
        counts["retired_verified"] += allowed
    else:
        counts["malformed"] += allowed
        details["malformed"].append(f"{fingerprint}: retired entry lacks valid composition evidence")
    return


def _account_active_entry(
    authority: Authority,
    repository: Path,
    raw: dict[str, object],
    validated: RatchetEntry,
    fingerprint: str,
    allowed: int,
    observed: int,
    expires: date,
    today: date,
    counts: Counter[str],
    details: defaultdict[str, list[str]],
) -> None:
    """Account active entry."""
    if expires < today:
        counts["expired"] += max(allowed, observed)
        details["expired"].append(fingerprint)
    counts["approved_active"] += min(allowed, observed)
    if observed > allowed:
        counts["expanded_existing"] += observed - allowed
        details["expanded_existing"].append(fingerprint)
    elif observed < allowed:
        missing = allowed - observed
        if valid_retirement(raw.get("retirement"), repository, validated["capability"]):
            counts["retirement_ready"] += missing
            details["retirement_ready"].append(fingerprint)
        else:
            counts["retirement_candidates"] += missing
            details["retirement_candidates"].append(fingerprint)
            if not observed and not source_module_exists(authority, validated["source_module"]):
                details["source_module_removed"].append(fingerprint)


def _partition_boundary_occurrences(
    rows: list[OccurrenceRow], root_boundaries: frozenset[tuple[str, str]]
) -> tuple[dict[str, OccurrenceRow], list[OccurrenceRow], defaultdict[str, list[str]]]:
    """Partition boundary occurrences."""
    current = {
        row["fingerprint"]: row
        for row in rows
        if not crosses_root_boundary(row["source_module"], row["target_module"], root_boundaries)
    }
    boundary_rows = [row for row in rows if row["fingerprint"] not in current]
    details: defaultdict[str, list[str]] = defaultdict(list)
    for row in boundary_rows:
        evidence = row["evidence"][0] if row["evidence"] else None
        location = f"{evidence['path']}:{evidence['line']}" if evidence is not None else row["source_module"]
        details["root_boundary"].append(f"{location} imports {row['target_module']}")
    return current, boundary_rows, details


def _read_ratchet_entries(path: Path, counts: Counter[str]) -> list[object] | RatchetReport:
    """Read ratchet entries."""
    try:
        payload = json.loads(path.read_text(encoding=UTF_8))
        if payload.get("schema_version") != RATCHET_SCHEMA_VERSION:
            raise ValueError("unsupported ratchet schema")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise ValueError("ratchet entries must be a list")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        counts["malformed"] += 1
        return {
            "baseline_status": "malformed",
            "counts": ratchet_counts(counts),
            "detail_counts": {"malformed": 1},
            "details": {"malformed": [str(exc)]},
            "path": str(path),
            "schema_version": RATCHET_SCHEMA_VERSION,
        }
    return cast("list[object]", entries)


def _ratchet_report(path: Path, counts: Counter[str], details: defaultdict[str, list[str]]) -> RatchetReport:
    """Ratchet report."""
    return {
        "baseline_status": "approved" if not counts["malformed"] else "malformed",
        "counts": ratchet_counts(counts),
        "detail_counts": {key: len(values) for key, values in sorted(details.items())},
        "details": {key: sorted(values)[:20] for key, values in sorted(details.items())},
        "path": str(path),
        "schema_version": RATCHET_SCHEMA_VERSION,
    }


def _observed_multiplicity(row: OccurrenceRow | None) -> int:
    """Read the current multiplicity or the unchanged absent-row default."""
    return 0 if row is None else row.get("multiplicity", 0)


def _account_unapproved_occurrences(
    current: dict[str, OccurrenceRow],
    approved: dict[str, RatchetEntry],
    counts: Counter[str],
    details: defaultdict[str, list[str]],
) -> None:
    """Account unapproved occurrences."""
    for fingerprint, row in current.items():
        if fingerprint not in approved:
            counts["new_unapproved"] += row["multiplicity"]
            details["new_unapproved"].append(fingerprint)
