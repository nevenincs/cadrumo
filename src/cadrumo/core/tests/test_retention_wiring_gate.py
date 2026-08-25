"""Wiring gate: every RETENTION-classified store must prune from a production path.

A retention lifecycle is only real if the prune fires in production. The
lifecycle gate (``test_settings_lifecycle_gate``) classifies each output dir;
this companion gate asserts that every RETENTION family's prune has a real
production call site (not merely a callable method), by scanning the owning
module source for the invocation. A retention family whose prune is dormant -
defined but never called on a write/finalise path - fails here.

The registry-disk-cache accessor is additionally checked to carry no
``PROJECT_ROOT`` fallback: an opt-in (``None``-default) field whose accessor
silently applied a ``PROJECT_ROOT`` fallback would escape the lifecycle gate's
derivation check.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CADRUMO_ROOT = Path(__file__).resolve().parents[2]

# Each RETENTION-classified family (see test_settings_lifecycle_gate._RETENTION)
# mapped to the production module and the exact prune invocation token that must
# appear as a call (beyond any definition) in that module.
_RETENTION_WIRING: dict[str, tuple[str, str]] = {
    # The three LLM diagnostic stores are swept once per client construction
    # (LLMClient._sweep_retention_stores), not on every append.
    "cadrumo_llm_cache_dir": ("llm/_client.py", "self.cache.prune"),
    "cadrumo_llm_usage_dir": ("llm/_client.py", "self.usage_recorder.prune"),
    "cadrumo_llm_run_telemetry_dir": ("llm/_client.py", "self.run_telemetry_recorder.prune"),
    "cadrumo_runs_dir": ("core/observability/_store.py", "prune_run_traces("),
    "cadrumo_registry_disk_cache_dir": (
        "domain/calculations/registry/_compiled_cache.py",
        "_evict_stale_registry_pickles(",
    ),
    "cadrumo_wallet_diagnostic_dump_dir": (
        "adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
        "prune_wallet_diagnostic_dumps(",
    ),
}


@pytest.mark.parametrize(("field", "wiring"), sorted(_RETENTION_WIRING.items()))
def test_retention_family_has_a_production_prune_call_site(field: str, wiring: tuple[str, str]) -> None:
    relative_path, call_token = wiring
    source = (_CADRUMO_ROOT / relative_path).read_text(encoding="utf-8")
    call_count = source.count(call_token)
    definition_count = source.count("def " + call_token)
    assert call_count - definition_count >= 1, (
        f"{field}: retention prune {call_token!r} has no production call site in "
        f"{relative_path} - a RETENTION-classified store's prune must fire on a "
        "write/finalise path, not merely be callable."
    )


def test_registry_disk_cache_accessor_has_no_project_root_fallback() -> None:
    source = (_CADRUMO_ROOT / "domain/calculations/registry/loader_cache.py").read_text(encoding="utf-8")
    assert "PROJECT_ROOT" not in source, (
        "the registry disk-cache accessor must derive its opt-in fallback from "
        "cadrumo_local_storage_root, never a PROJECT_ROOT literal that resolves "
        "inside site-packages on an installed run"
    )
