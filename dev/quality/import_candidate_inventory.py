"""Import candidate inventory."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from cadrumo.core.storage_environment import resolve_storage_path
from dev._paths import UTF_8
from dev.first_party_source import is_test_module_name

from .import_check_models import Authority, ImportOccurrence
from .import_health_models import (
    RATCHET_SCHEMA_VERSION,
    CandidateInventory,
    CandidateSummary,
    OccurrenceRow,
    OccurrenceSummary,
)


def candidate_inventory(authority: Authority, occurrences: tuple[ImportOccurrence, ...]) -> CandidateInventory:
    """Collect hard and advisory import occurrences into separate inventories."""
    hard = tuple(occurrence for occurrence in occurrences if not occurrence.contract.startswith("advisory:"))
    advisory = tuple(occurrence for occurrence in occurrences if occurrence.contract.startswith("advisory:"))
    rows, summary = occurrence_inventory(authority, hard)
    advisory_rows, advisory_summary = occurrence_inventory(authority, advisory)
    advisory_lane_pairs: Counter[str] = Counter()
    for row in advisory_rows:
        source_lane = adapter_top_level(str(row["source_module"]))
        target_lane = adapter_top_level(str(row["target_module"]))
        if source_lane is not None and target_lane is not None:
            advisory_lane_pairs[f"{source_lane} -> {target_lane}"] += int(row["multiplicity"])
    candidate_summary: CandidateSummary = {
        "contract_occurrences": summary["contract_occurrences"],
        "by_contract": summary["by_contract"],
        "by_import_form": summary["by_import_form"],
        "non_test_scoped_occurrences": summary["non_test_scoped_occurrences"],
        "test_scoped_occurrences": summary["test_scoped_occurrences"],
        "inventory_digest": summary["inventory_digest"],
        "unique_contract_occurrences": summary["unique_contract_occurrences"],
        "unique_import_occurrences": summary["unique_import_occurrences"],
        "advisory_by_contract": advisory_summary["by_contract"],
        "advisory_by_lane_pair": dict(sorted(advisory_lane_pairs.items())),
        "advisory_non_test_scoped_occurrences": advisory_summary["non_test_scoped_occurrences"],
        "advisory_occurrences": advisory_summary["contract_occurrences"],
        "advisory_test_scoped_occurrences": advisory_summary["test_scoped_occurrences"],
        "advisory_unique_occurrences": advisory_summary["unique_contract_occurrences"],
    }
    return {
        "advisory_occurrences": advisory_rows,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "occurrences": rows,
        "schema_version": RATCHET_SCHEMA_VERSION,
        "summary": candidate_summary,
    }


def occurrence_inventory(
    authority: Authority, occurrences: tuple[ImportOccurrence, ...]
) -> tuple[list[OccurrenceRow], OccurrenceSummary]:
    """Normalize one hard or advisory occurrence class without conflating them."""
    grouped: defaultdict[str, list[ImportOccurrence]] = defaultdict(list)
    for occurrence in occurrences:
        grouped[occurrence.fingerprint].append(occurrence)
    rows: list[OccurrenceRow] = []
    unique_import_identities: set[tuple[str, str, tuple[str, ...], str, str]] = set()
    production = 0
    test = 0
    by_contract: Counter[str] = Counter()
    by_import_form: Counter[str] = Counter()
    for fingerprint, group in sorted(grouped.items()):
        first = group[0]
        evidence = sorted(
            {
                (
                    occurrence.path.relative_to(authority.repository).as_posix(),
                    occurrence.lineno,
                )
                for occurrence in group
            }
        )
        test_scoped = module_is_test_scoped(first.source_module)
        if test_scoped:
            test += len(group)
        else:
            production += len(group)
        by_contract[first.contract] += len(group)
        by_import_form[first.import_form] += len(group)
        identity = (
            first.source_module,
            first.target_module,
            first.imported_symbols,
            first.import_form,
            first.lexical_scope,
        )
        unique_import_identities.add(identity)
        rows.append(
            {
                "contract": first.contract,
                "evidence": [{"line": line, "path": path} for path, line in evidence],
                "fingerprint": fingerprint,
                "import_form": first.import_form,
                "imported_symbols": list(first.imported_symbols),
                "lexical_scope": first.lexical_scope,
                "multiplicity": len(group),
                "source_module": first.source_module,
                "target_module": first.target_module,
                "test_scoped": test_scoped,
            }
        )
    inventory_digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode(UTF_8)).hexdigest()
    return rows, {
        "contract_occurrences": sum(len(group) for group in grouped.values()),
        "by_contract": dict(sorted(by_contract.items())),
        "by_import_form": dict(sorted(by_import_form.items())),
        "non_test_scoped_occurrences": production,
        "test_scoped_occurrences": test,
        "inventory_digest": inventory_digest,
        "unique_contract_occurrences": len(rows),
        "unique_import_occurrences": len(unique_import_identities),
    }


def write_candidate_artifact(repository: Path, candidate: CandidateInventory) -> Path | None:
    """Write the candidate evidence to the explicitly configured artifact directory."""
    raw_artifacts = os.environ.get("CADRUMO_DEV_ARTIFACTS_DIR")
    if not raw_artifacts:
        return None
    artifacts = resolve_storage_path(raw_artifacts)
    path = artifacts / "import-boundary-candidate.json"
    path.write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n",
        encoding=UTF_8,
        newline="\n",
    )
    return path


def module_is_test_scoped(module: str) -> bool:
    """Recognize test modules through the shared test scope policy."""
    return is_test_module_name(module) or any(
        part.startswith("test_") or part.endswith("_test") for part in module.split(".")
    )


def adapter_top_level(module: str) -> str | None:
    """Return the top-level adapter namespace for advisory grouping."""
    prefix = "cadrumo.adapters."
    if not module.startswith(prefix):
        return None
    return module.removeprefix(prefix).partition(".")[0] or None
