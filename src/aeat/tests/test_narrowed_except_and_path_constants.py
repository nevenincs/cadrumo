"""Narrowed-except clauses, rationale markers, and Final path constants.

Asserts:

- _plazo.py uses bare ``except RegistryError:`` (no redundant Exception catch).
- _xlsx.py carries the BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN marker at both
  teardown sites (ingest + validate_source).
- _sink.py carries LOGGING-STDLIB-RATIONALE-SINK-HANDLER on the stdlib
  logging import (justified by the logging.Handler subclass contract).
- _ledger.py carries MACHINE-FORMAT-RATIONALE-LEDGER-BULK-CLASSIFY-FAILURE
  on the tab-separated failure line.
- _cache.py carries JSON-LOADS-RATIONALE-LLM-CACHE-SECURE-OBJECT on the
  _entry_from_payload json.loads line.
- _schedules.py declares _IVA_REGIME_PATH and _TAXPAYER_ENTITY_TYPE_PATH
  as module-level Final constants and uses them in _resolve_profile_fact.

No mocks, no skips, no tautological assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).parent.parent  # src/aeat/


def _src(rel: str) -> Path:
    p = _SRC / rel
    assert p.exists(), f"Expected source file missing: {p}"
    return p


def _read(rel: str) -> str:
    return _src(rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# _plazo.py: narrow except
# ---------------------------------------------------------------------------


def test_plazo_exception_narrowed() -> None:
    """_plazo.py must use bare ``except RegistryError:``; the redundant ``Exception`` catch is gone."""
    src = _read("domain/deadlines/_plazo.py")
    assert "except RegistryError:" in src, "domain/deadlines/_plazo.py: missing ``except RegistryError:`` narrowing"
    assert "except (RegistryError, Exception)" not in src, (
        "domain/deadlines/_plazo.py: redundant ``except (RegistryError, Exception)`` still present"
    )


# ---------------------------------------------------------------------------
# _xlsx.py: BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN at validate_source teardown
# ---------------------------------------------------------------------------

_XLSX_TOKEN = "BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN"


def test_xlsx_teardown_both_sites_carry_rationale() -> None:
    """_xlsx.py must carry BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN at both teardown sites."""
    src = _read("adapters/inbound/financial/providers/_xlsx.py")
    occurrences = src.count(_XLSX_TOKEN)
    assert occurrences >= 2, (
        f"adapters/inbound/financial/providers/_xlsx.py: expected >=2 occurrences of "
        f"{_XLSX_TOKEN!r}, found {occurrences} — second-site marker not applied"
    )


# ---------------------------------------------------------------------------
# _sink.py: LOGGING-STDLIB-RATIONALE-SINK-HANDLER marker
# ---------------------------------------------------------------------------

_SINK_TOKEN = "LOGGING-STDLIB-RATIONALE-SINK-HANDLER"


def test_sink_logging_rationale_present() -> None:
    """_sink.py must carry LOGGING-STDLIB-RATIONALE-SINK-HANDLER on the stdlib logging import."""
    src = _read("core/observability/_sink.py")
    assert _SINK_TOKEN in src, f"core/observability/_sink.py: missing {_SINK_TOKEN!r}"
    # Verify it is on the import logging line specifically.
    lines_with_token = [ln for ln in src.splitlines() if _SINK_TOKEN in ln]
    assert lines_with_token, f"{_SINK_TOKEN!r} present in source but no matching line found"
    assert any("import logging" in ln for ln in lines_with_token), (
        f"core/observability/_sink.py: {_SINK_TOKEN!r} found but not on the ``import logging`` line"
    )


# ---------------------------------------------------------------------------
# _ledger.py: MACHINE-FORMAT-RATIONALE-LEDGER-BULK-CLASSIFY-FAILURE
# ---------------------------------------------------------------------------

_LEDGER_TOKEN = "MACHINE-FORMAT-RATIONALE-LEDGER-BULK-CLASSIFY-FAILURE"


def test_ledger_bulk_classify_failure_machine_format_rationale() -> None:
    """The bulk-classify failure line must carry the machine-format rationale marker."""
    src = _read("entrypoints/cli/_ledger_classify_cli.py")
    assert _LEDGER_TOKEN in src, f"entrypoints/cli/_ledger_classify_cli.py: missing {_LEDGER_TOKEN!r}"
    lines_with_token = [ln for ln in src.splitlines() if _LEDGER_TOKEN in ln]
    assert any("transaction_id" in ln or "reason" in ln for ln in lines_with_token), (
        f"entrypoints/cli/_ledger.py: {_LEDGER_TOKEN!r} found but not on the tab-separated failure line"
    )


# ---------------------------------------------------------------------------
# _cache.py: JSON-LOADS-RATIONALE-LLM-CACHE-SECURE-OBJECT
# ---------------------------------------------------------------------------

_CACHE_TOKEN = "JSON-LOADS-RATIONALE-LLM-CACHE-SECURE-OBJECT"


def test_llm_cache_json_loads_rationale_present() -> None:
    """_cache.py _entry_from_payload must carry JSON-LOADS-RATIONALE-LLM-CACHE-SECURE-OBJECT."""
    src = _read("adapters/outbound/llm/_cache.py")
    assert _CACHE_TOKEN in src, f"adapters/outbound/llm/_cache.py: missing {_CACHE_TOKEN!r}"
    # Confirm it is on the _entry_from_payload json.loads line specifically.
    lines = src.splitlines()
    token_lines = [ln for ln in lines if _CACHE_TOKEN in ln]
    assert any("json.loads" in ln for ln in token_lines), (
        f"adapters/outbound/llm/_cache.py: {_CACHE_TOKEN!r} present but not on a json.loads line"
    )


# ---------------------------------------------------------------------------
# _schedules.py: Final path constants
# ---------------------------------------------------------------------------


def test_schedules_final_path_constants() -> None:
    """_schedules.py must declare _IVA_REGIME_PATH and _TAXPAYER_ENTITY_TYPE_PATH as Final constants."""
    src = _read("domain/calculations/registry/_schedules.py")
    assert '_IVA_REGIME_PATH: Final[str] = "iva.regime"' in src, (
        "domain/calculations/registry/_schedules.py: missing _IVA_REGIME_PATH Final constant"
    )
    assert '_TAXPAYER_ENTITY_TYPE_PATH: Final[str] = "taxpayer.entity_type"' in src, (
        "domain/calculations/registry/_schedules.py: missing _TAXPAYER_ENTITY_TYPE_PATH Final constant"
    )


# ---------------------------------------------------------------------------
# _schedules.py uses constants in _resolve_profile_fact body
# ---------------------------------------------------------------------------


def test_schedules_uses_constants_in_resolver() -> None:
    """_resolve_profile_fact must reference the Final constants, not bare string literals."""
    src = _read("domain/calculations/registry/_schedules.py")
    # Find the _resolve_profile_fact function body.
    assert "def _resolve_profile_fact" in src, (
        "domain/calculations/registry/_schedules.py: _resolve_profile_fact not found"
    )
    func_start = src.index("def _resolve_profile_fact")
    func_body = src[func_start:]
    # The constants must appear in the function body.
    assert "_IVA_REGIME_PATH" in func_body, (
        "domain/calculations/registry/_schedules.py: _IVA_REGIME_PATH constant not used in _resolve_profile_fact"
    )
    assert "_TAXPAYER_ENTITY_TYPE_PATH" in func_body, (
        "domain/calculations/registry/_schedules.py: "
        "_TAXPAYER_ENTITY_TYPE_PATH constant not used in _resolve_profile_fact"
    )


# ---------------------------------------------------------------------------
# Sibling ratchet must still enumerate _xlsx.py teardown rationale
# ---------------------------------------------------------------------------


def test_broad_except_ratchet_still_covers_xlsx() -> None:
    """The broad-except rationale inventory must still list _xlsx.py."""
    ratchet = _read("tests/test_broad_except_and_any_return_rationale.py")
    assert "_xlsx.py" in ratchet, (
        "test_broad_except_and_any_return_rationale.py: _xlsx.py no longer listed — ratchet coverage broken"
    )
    assert "BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN" in ratchet, (
        "test_broad_except_and_any_return_rationale.py: BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN token not in ratchet"
    )


# ---------------------------------------------------------------------------
# _sink.py is a logging-regression: stdlib logging import is justified
# ---------------------------------------------------------------------------


def test_sink_is_logging_handler_subclass() -> None:
    """_sink.py must define JsonlRunSink as a subclass of logging.Handler."""
    src = _read("core/observability/_sink.py")
    assert "class JsonlRunSink(logging.Handler)" in src, (
        "core/observability/_sink.py: JsonlRunSink(logging.Handler) class definition not found — "
        "ABC contract requiring stdlib logging import may have changed"
    )
