"""Audit gate: persistence-boundary roundtrip coverage.

Tracks the persistence boundaries the codebase exposes; each has at
least one roundtrip test (per aeat-quality-gates.md).

  Boundary -> roundtrip test file:
  - SecureObjectRepository (SQL encrypted storage)
      -> src/cadrumo/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py
      -> src/cadrumo/adapters/persistence/storage/envelope/test_secure_bound_repository.py
      -> src/cadrumo/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py
  - JsonlRunSink (observability JSONL)
      -> src/cadrumo/core/observability/test_sink_redaction.py
      -> src/cadrumo/core/observability/test_sink.py
  - AEAT fichero-BOE export bytes
      -> src/cadrumo/application/filing/tests/test_fixed_width_codec_conformance.py
  - Session store (AEAT auth)
      -> src/cadrumo/adapters/outbound/aeat/auth/test_session_store_roundtrip.py
  - Google session store
      -> src/cadrumo/adapters/outbound/google/test_session_store_roundtrip.py
  - Google worksheet export/pull
      -> src/cadrumo/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py
  - Observation store (AEAT sede)
      -> src/cadrumo/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py
  - Corpus sidecar (justificante inbound)
      -> src/cadrumo/adapters/inbound/justificante/test_corpus_sidecar_roundtrip.py
  - Sanitizer pipeline (fixture-preparation tooling)
      -> dev/sanitizer/tests/test_round_trip.py
  - RunTrace persistence
      -> src/cadrumo/application/workflow/test_run_persistence_roundtrip.py
  - Filing history repository
      -> src/cadrumo/application/filing/test_history_repository_roundtrip.py
  - Domain filing secure storage
      -> src/cadrumo/domain/filing/test_secure_storage_roundtrip.py
  - Domain modelos secure storage
      -> src/cadrumo/domain/modelos/test_secure_storage_roundtrip.py
  - Registry corpus round-trip gate
      -> src/cadrumo/domain/calculations/registry/test_corpus_round_trip_gate.py

This file provides the real-behavior test that asserts every
declared boundary has its roundtrip test file present on disk.  New
boundaries must be registered here alongside a roundtrip test or the
gate will fail.
"""

from __future__ import annotations

import pytest

from cadrumo.tests._inventory import repo_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Canonical inventory: (boundary_label, roundtrip_test_path_relative_to_repo_root)
# Each entry represents one persistence boundary and its roundtrip test file.
# Multiple entries for the same boundary are allowed when multiple roundtrip
# tests cover different aspects.
_BOUNDARY_ROUNDTRIP_INVENTORY: tuple[tuple[str, str], ...] = (
    (
        "SecureObjectRepository SQL encrypted storage",
        "src/cadrumo/adapters/persistence/storage/sql/tests/test_archive_bundle_roundtrip.py",
    ),
    (
        "SecureObjectRepository envelope contract",
        "src/cadrumo/adapters/persistence/storage/envelope/tests/test_secure_bound_repository.py",
    ),
    (
        "SecureObjectRepository envelope boundary contract",
        "src/cadrumo/adapters/persistence/storage/envelope/tests/test_secure_bound_repository_contract.py",
    ),
    (
        "JsonlRunSink redaction",
        "src/cadrumo/core/observability/tests/test_sink_redaction.py",
    ),
    (
        "JsonlRunSink emit",
        "src/cadrumo/core/observability/tests/test_sink.py",
    ),
    (
        "AEAT fichero-BOE export bytes",
        "src/cadrumo/application/filing/tests/test_fixed_width_codec_conformance.py",
    ),
    (
        "AEAT auth session store",
        "src/cadrumo/adapters/outbound/aeat/auth/tests/test_session_store_roundtrip.py",
    ),
    (
        "Google session store",
        "src/cadrumo/adapters/outbound/google/tests/test_session_store_roundtrip.py",
    ),
    (
        "Google worksheet export/pull",
        "src/cadrumo/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py",
    ),
    (
        "AEAT sede observation store",
        "src/cadrumo/adapters/outbound/aeat/sede/tests/test_observation_store_roundtrip.py",
    ),
    (
        "Corpus sidecar justificante inbound",
        "src/cadrumo/adapters/inbound/justificante/tests/test_corpus_sidecar_roundtrip.py",
    ),
    (
        "Sanitizer pipeline fixture-preparation tooling",
        "dev/sanitizer/tests/test_round_trip.py",
    ),
    (
        "RunTrace persistence",
        "src/cadrumo/application/workflow/tests/test_run_persistence_roundtrip.py",
    ),
    (
        "Filing history repository",
        "src/cadrumo/application/filing/tests/test_history_repository_roundtrip.py",
    ),
    (
        "Domain filing secure storage",
        "src/cadrumo/domain/filing/tests/test_secure_storage_roundtrip.py",
    ),
    (
        "Domain modelos secure storage",
        "src/cadrumo/domain/modelos/tests/test_secure_storage_roundtrip.py",
    ),
    (
        "Registry corpus round-trip gate",
        "src/cadrumo/domain/calculations/registry/tests/test_corpus_round_trip_gate.py",
    ),
    (
        "Attachment store",
        "src/cadrumo/adapters/persistence/storage/tests/test_attachment_store_roundtrip.py",
    ),
    (
        "Domain invoices secure storage",
        "src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py",
    ),
    (
        "Domain submission secure storage",
        "src/cadrumo/domain/submission/tests/test_secure_storage_roundtrip.py",
    ),
    (
        "Registry cross-boundary roundtrip",
        "src/cadrumo/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py",
    ),
    (
        "Observations repository",
        "src/cadrumo/application/calculations/tests/test_observations_repository_roundtrip.py",
    ),
    (
        "LLM cache roundtrip",
        "src/cadrumo/adapters/outbound/llm/tests/test_cache_roundtrip.py",
    ),
    (
        "Profile assets roundtrip",
        "src/cadrumo/adapters/persistence/profile/tests/test_assets_roundtrip.py",
    ),
    (
        "Profile inventory roundtrip",
        "src/cadrumo/adapters/persistence/profile/tests/test_inventory_roundtrip.py",
    ),
    (
        "Bucket manifest roundtrip",
        "src/cadrumo/adapters/persistence/storage/bucket/tests/test_manifest_roundtrip.py",
    ),
)


def test_persistence_boundary_roundtrip_tests_exist() -> None:
    """Every declared persistence boundary must have a roundtrip test on disk.

    Verifies behavior contract: the inventory above is the canonical record of
    boundaries touched by ratchet history.  Each entry must have an existing
    test file.  Missing files indicate a boundary was declared without a
    roundtrip test — a roundtrip-discipline violation.
    """
    assert _BOUNDARY_ROUNDTRIP_INVENTORY, (
        "the persistence-boundary inventory is empty; this gate would assert coverage over nothing"
    )
    missing: list[str] = []
    for boundary_label, rel_path in _BOUNDARY_ROUNDTRIP_INVENTORY:
        full_path = repo_path(rel_path)
        if not full_path.exists():
            missing.append(f"{boundary_label!r} -> {rel_path}")

    assert not missing, (
        "Persistence boundaries declared in the roundtrip inventory are missing "
        "their roundtrip test files (per aeat-quality-gates.md):\n\n" + "\n".join(f"  - {m}" for m in missing)
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
            duplicates.append(f"{rel_path!r} appears as both {seen_paths[rel_path]!r} and {label!r}")
        else:
            seen_paths[rel_path] = label

    assert not duplicates, "Duplicate paths in _BOUNDARY_ROUNDTRIP_INVENTORY:\n" + "\n".join(
        f"  - {d}" for d in duplicates
    )
