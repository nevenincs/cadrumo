"""Audit gate: persistence-boundary roundtrip coverage.

S217 enumeration — persistence boundaries touched by W01.P01..P08 fix Steps:
  The following boundaries were identified as touched by P01-P08 execution
  and each has at least one roundtrip test (per aeat-roundtrip-discipline.md).

  Boundary -> roundtrip test file:
  - SecureObjectRepository (SQL encrypted storage)
      -> src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py
      -> src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py
      -> src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py
  - JsonlRunSink (observability JSONL)
      -> src/aeat/core/observability/test_sink_redaction.py
      -> src/aeat/core/observability/test_sink.py
  - AEAT fichero-BOE export bytes
      -> src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py
  - Session store (AEAT auth)
      -> src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py
  - Google session store
      -> src/aeat/adapters/outbound/google/test_session_store_roundtrip.py
  - Google worksheet export/pull
      -> src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py
  - Observation store (AEAT sede)
      -> src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py
  - Corpus sidecar (justificante inbound)
      -> src/aeat/adapters/inbound/justificante/test_corpus_sidecar_roundtrip.py
  - Sanitizer pipeline (inbound)
      -> src/aeat/adapters/inbound/sanitizer/test_round_trip.py
  - RunTrace persistence
      -> src/aeat/application/workflow/test_run_persistence_roundtrip.py
  - Filing history repository
      -> src/aeat/application/filing/test_history_repository_roundtrip.py
  - Domain filing secure storage
      -> src/aeat/domain/filing/test_secure_storage_roundtrip.py
  - Domain modelos secure storage
      -> src/aeat/domain/modelos/test_secure_storage_roundtrip.py
  - Registry corpus round-trip gate
      -> src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py

S218 assertion — this file provides the real-behavior test that asserts every
  declared boundary has its roundtrip test file present on disk.  New boundaries
  added by future Steps must be registered here alongside a roundtrip test or
  the gate will fail.

No Wave 2 follow-up Steps were generated from the S217 enumeration pass:
  all known P01-P08 boundaries have at least one roundtrip test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

# Canonical inventory: (boundary_label, roundtrip_test_path_relative_to_PROJECT_ROOT)
# Each entry represents one persistence boundary and its roundtrip test file.
# Multiple entries for the same boundary are allowed when multiple roundtrip
# tests cover different aspects.
_BOUNDARY_ROUNDTRIP_INVENTORY: tuple[tuple[str, str], ...] = (
    (
        "SecureObjectRepository SQL encrypted storage",
        "src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py",
    ),
    (
        "SecureObjectRepository envelope contract",
        "src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py",
    ),
    (
        "SecureObjectRepository envelope boundary contract",
        "src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py",
    ),
    (
        "JsonlRunSink redaction",
        "src/aeat/core/observability/test_sink_redaction.py",
    ),
    (
        "JsonlRunSink emit",
        "src/aeat/core/observability/test_sink.py",
    ),
    (
        "AEAT fichero-BOE export bytes",
        "src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py",
    ),
    (
        "AEAT auth session store",
        "src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py",
    ),
    (
        "Google session store",
        "src/aeat/adapters/outbound/google/test_session_store_roundtrip.py",
    ),
    (
        "Google worksheet export/pull",
        "src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py",
    ),
    (
        "AEAT sede observation store",
        "src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py",
    ),
    (
        "Corpus sidecar justificante inbound",
        "src/aeat/adapters/inbound/justificante/test_corpus_sidecar_roundtrip.py",
    ),
    (
        "Sanitizer pipeline inbound",
        "src/aeat/adapters/inbound/sanitizer/test_round_trip.py",
    ),
    (
        "RunTrace persistence",
        "src/aeat/application/workflow/test_run_persistence_roundtrip.py",
    ),
    (
        "Filing history repository",
        "src/aeat/application/filing/test_history_repository_roundtrip.py",
    ),
    (
        "Domain filing secure storage",
        "src/aeat/domain/filing/test_secure_storage_roundtrip.py",
    ),
    (
        "Domain modelos secure storage",
        "src/aeat/domain/modelos/test_secure_storage_roundtrip.py",
    ),
    (
        "Registry corpus round-trip gate",
        "src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py",
    ),
    (
        "Attachment store",
        "src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py",
    ),
    (
        "Domain invoices secure storage",
        "src/aeat/domain/invoices/test_secure_storage_roundtrip.py",
    ),
    (
        "Domain submission secure storage",
        "src/aeat/domain/submission/test_secure_storage_roundtrip.py",
    ),
    (
        "Registry cross-boundary roundtrip",
        "src/aeat/domain/calculations/registry/test_cross_boundary_roundtrip.py",
    ),
    (
        "Observations repository",
        "src/aeat/application/calculations/test_observations_repository_roundtrip.py",
    ),
    (
        "LLM cache roundtrip",
        "src/aeat/adapters/outbound/llm/test_cache_roundtrip.py",
    ),
    (
        "Profile assets roundtrip",
        "src/aeat/adapters/persistence/profile/test_assets_roundtrip.py",
    ),
    (
        "Profile inventory roundtrip",
        "src/aeat/adapters/persistence/profile/test_inventory_roundtrip.py",
    ),
    (
        "Bucket manifest roundtrip",
        "src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py",
    ),
)


def test_persistence_boundary_roundtrip_tests_exist() -> None:
    """Every declared persistence boundary must have a roundtrip test on disk.

    Verifies S217/S218: the inventory above is the canonical record of
    boundaries touched by W01.P01-P08.  Each entry must have an existing
    test file.  Missing files indicate a boundary was declared without a
    roundtrip test — a roundtrip-discipline violation.
    """
    missing: list[str] = []
    for boundary_label, rel_path in _BOUNDARY_ROUNDTRIP_INVENTORY:
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            missing.append(f"{boundary_label!r} -> {rel_path}")

    assert not missing, (
        "Persistence boundaries declared in the roundtrip inventory are missing "
        "their roundtrip test files (per aeat-roundtrip-discipline.md):\n\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


def test_roundtrip_inventory_has_no_duplicate_paths() -> None:
    """The inventory must not declare the same test path twice with different labels.

    Duplicates suggest copy-paste errors in the inventory; each test file
    should appear at most once (covering exactly the boundary it names).
    """
    seen_paths: dict[str, str] = {}
    duplicates: list[str] = []
    for label, rel_path in _BOUNDARY_ROUNDTRIP_INVENTORY:
        if rel_path in seen_paths:
            duplicates.append(
                f"{rel_path!r} appears as both {seen_paths[rel_path]!r} and {label!r}"
            )
        else:
            seen_paths[rel_path] = label

    assert not duplicates, (
        "Duplicate paths in _BOUNDARY_ROUNDTRIP_INVENTORY:\n"
        + "\n".join(f"  - {d}" for d in duplicates)
    )
