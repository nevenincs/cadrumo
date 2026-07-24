"""Codebase-wide module and callable size ratchets."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ._inventory import package_ast_items, package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEFAULT_MODULE_LINE_LIMIT = 1250
_DEFAULT_CALLABLE_LINE_LIMIT = 180
_MODULE_LINE_LIMIT_OVERRIDES = {
    "src/cadrumo/application/modelo/tests/test_export.py": 1585,  # SPLIT-CANDIDATE
    # SPLIT-CANDIDATE
    "src/cadrumo/domain/calculations/registry/tests/test_loader_directory_mode.py": 1380,
    "src/cadrumo/domain/calculations/registry/_workbook_parity.py": 1298,  # SPLIT-CANDIDATE (+6: sys.platform guard so ty resolves winreg only on win32)
    # Extracted the IRNR/M210 formula-op evaluator family to the sibling
    # `_formula_runtime_irnr.py` module and the shared error types + numeric
    # accessor to `_formula_runtime_ops.py` (registry-resolver-family-extraction),
    # bringing the module from 2069 down to its present size to hold the ceiling.
    # SPLIT-CANDIDATE: further formula-op families can still be extracted.
    "src/cadrumo/domain/calculations/registry/_formula_runtime.py": 1835,  # SPLIT-CANDIDATE
    # M131 EO-modulos engine test carries per-activity coefficient-dataset
    # tables verified against the AEAT manual worked examples; data-shaped
    # growth. SPLIT-CANDIDATE: split the per-activity dataset fixtures out.
    "src/cadrumo/domain/calculations/registry/tests/test_modelo_131_modulos_engine.py": 1517,  # SPLIT-CANDIDATE
    "src/cadrumo/application/filing/tests/test_export.py": 1270,  # SPLIT-CANDIDATE
    "src/cadrumo/entrypoints/cli/_modelo.py": 1320,  # SPLIT-CANDIDATE (recovered growth)
    # Oversize modules pinned to their present size so future work must split
    # before growing them further. Entries marked SPLIT-CANDIDATE grew past a
    # prior pin under concurrent feature work and are re-pinned to hold the new
    # ceiling; their owners should extract submodules during their next pass.
    "src/cadrumo/application/calculations/_cross_period_clean_state.py": 1535,  # SPLIT-CANDIDATE
    "src/cadrumo/application/calculations/tests/test_cross_period_clean_state.py": 1645,  # SPLIT-CANDIDATE
    "src/cadrumo/application/ledger/_llm_classification.py": 1664,  # SPLIT-CANDIDATE (active LLM-ledger growth)
    # Manual ledger-action surface grew to 1278 under concurrent ledger feature
    # work; first override, pinned with small headroom per the ship-authorised
    # rebaseline. SPLIT-CANDIDATE: extract manual-command helpers on the next pass.
    "src/cadrumo/application/ledger/_actions_manual.py": 1305,  # SPLIT-CANDIDATE
    "src/cadrumo/application/modelo/_verification_actions.py": 1750,  # SPLIT-CANDIDATE
    # Grew with the state-root derivation table and the per-family growth-lifecycle
    # settings (log rotation cap/backup, LLM cache/usage/run-telemetry retention,
    # run-trace + wallet-dump + corpus-cache retention/derivation); re-pinned to
    # present size. SPLIT-CANDIDATE: the settings model is a split-by-mixin target.
    "src/cadrumo/core/config.py": 1400,  # SPLIT-CANDIDATE
    # Active live-censo calendar reconciliation is landing in this shared tree;
    # keep a bounded ceiling so unrelated closeout sweeps can proceed while it settles.
    # Live-censo calendar reconciliation is actively landing and growing; bounded
    # settling ceiling (present size + margin) per the rationale below.
    "src/cadrumo/application/overview/_calendar.py": 1667,  # SPLIT-CANDIDATE
    "src/cadrumo/application/overview/tests/test_calendar.py": 1396,
    "src/cadrumo/application/overview/tests/test_calendar_filing_evidence.py": 1530,  # SPLIT-CANDIDATE
    # secure_objects.py: extracted the raw-row decode/fault-isolation codec
    # (_list_item_from_raw_row) to the sibling _secure_object_row_codec.py
    # module alongside the existing secure_object_record_from_row extraction;
    # that split put it back under the default budget. The WP10 core-complexity
    # decomposition (1110a630d1) then split its remaining hotspot callables into
    # named helpers, taking it 1219 -> 1277: the added lines are helper
    # signatures and docstrings, and radon reports no callable above C. Pinned
    # at the post-decomposition size.
    "src/cadrumo/adapters/persistence/storage/sql/secure_objects.py": 1277,  # SPLIT-CANDIDATE
    # M143/M156/M185/M186/M490/M604/M763/M848 applicability-rule enrollment
    # (data-shaped dict literal growth); SPLIT-CANDIDATE: extract the rule
    # table into per-family submodules during the next applicability pass.
    "src/cadrumo/domain/calculations/registry/_applicability.py": 2156,  # SPLIT-CANDIDATE
    "src/cadrumo/domain/calculations/registry/_schema.py": 1490,  # SPLIT-CANDIDATE
    "src/cadrumo/entrypoints/cli/tests/test_registry_cli.py": 1360,  # SPLIT-CANDIDATE (Period construction verbosity)
    # Regrew to 1296 under concurrent live-command feature work plus
    # feature/profile branch growth; re-pinned with small headroom per the
    # ship-authorised rebaseline (mirrors the sibling override in
    # test_cli_module_size.py).
    "src/cadrumo/entrypoints/cli/_app_live.py": 1320,  # SPLIT-CANDIDATE
    # _ledger_payloads.py: extracted the invoice/inventory/evidence sub-app
    # payload families to the sibling `_ledger_business_payloads.py` module
    # (registry-resolver-family-extraction, following the module's own
    # documented split pattern); back under the default budget, override
    # removed.
    # _modelo_payloads.py: extracted the `bindings list`/`bindings resolve`
    # payload family to the sibling `_modelo_bindings_payloads.py` module,
    # following the split pattern already established by
    # `_modelo_aux_payloads.py` / `_modelo_revision_payload_parts.py`;
    # re-pinned to the smaller post-split size.
    "src/cadrumo/entrypoints/cli/_modelo_payloads.py": 1341,  # SPLIT-CANDIDATE
    # New peer-introduced modules discovered by the size-budget gate;
    # pinned at present size pending an owner split pass.
    "src/cadrumo/adapters/outbound/google/_calc_sheets_apply.py": 1272,  # SPLIT-CANDIDATE (+13: call-time vault-folder Settings deferral, 1d026764cc)
    "src/cadrumo/adapters/outbound/google/_calc_sheets_pull.py": 1316,  # SPLIT-CANDIDATE (regrew past prior pin)
    # Extracting caller-override reconciliation out of the calculate-diagnostics
    # entry (e3caca846b) took this module 1367 -> 1452. Pinned at the
    # post-decomposition size.
    "src/cadrumo/application/modelo/_calculation_actions.py": 1452,  # SPLIT-CANDIDATE (regrew past prior pin)
    "src/cadrumo/application/aggregation/_iva_ledger.py": 1617,  # SPLIT-CANDIDATE
    # feature/profile branch growth; re-pinned past prior ceiling.
    "src/cadrumo/application/wizard/_commands.py": 2117,  # SPLIT-CANDIDATE
    # _loader.py: extracted the locale-translation load/merge/inject pipeline
    # to the sibling `_loader_locales.py` module (registry-resolver-family-
    # extraction); was back under the default budget with the override removed,
    # then regrew past the ceiling from the disk-cache hardening/perf commits
    # (`21f3875c90`, `17919422a6`, `1f848d087c`). Load-bearing registry compiler;
    # re-pinned to present size pending an owner split pass rather than a
    # same-pass extraction.
    # Regrew again from the fingerprint-count disk-cache eviction helper.
    "src/cadrumo/domain/calculations/registry/_loader.py": 1445,  # SPLIT-CANDIDATE
    "src/cadrumo/domain/calculations/registry/_queries.py": 1331,  # SPLIT-CANDIDATE
    "src/cadrumo/domain/calculations/registry/_ledger_bindings.py": 1440,  # SPLIT-CANDIDATE
    "src/cadrumo/domain/calculations/registry/tests/test_modelo_100_registry_roles.py": 1373,  # SPLIT-CANDIDATE
    "src/cadrumo/domain/transactions/_models.py": 1419,  # SPLIT-CANDIDATE
    "src/cadrumo/entrypoints/cli/_config/__init__.py": 1261,  # SPLIT-CANDIDATE
    # Authentication lifecycle responsibilities keep this module above the
    # default budget. The WP2 auth decomposition (d6e1dbf7a3, plus the
    # signature-typing follow-up e03b9674b8) split its complexity hotspots into
    # named private helpers, taking it 1436 -> 1575; radon now reports no callable
    # above C here. Pinned at the post-decomposition size.
    "src/cadrumo/application/auth/_operator.py": 1575,  # SPLIT-CANDIDATE
    # The _delete_locked decomposition into named private helpers (f764cc53de)
    # took this module 1219 -> 1295, its first override. The only callable radon
    # still rates C is import_ (11). Pinned at the post-decomposition size.
    "src/cadrumo/application/bucket_maintenance/_service.py": 1295,  # SPLIT-CANDIDATE
    # The WP11 workflow decomposition (d5a365ae08) took this module from exactly
    # the default budget (1250) to 1292, its first override, by extracting the
    # engine's stage helpers. Pinned at the post-decomposition size.
    "src/cadrumo/application/workflow/_engine.py": 1292,  # SPLIT-CANDIDATE
}
_CALLABLE_LINE_LIMIT_OVERRIDES = {
    ("src/cadrumo/application/modelo/_revision_persistence.py", "persist_filed_revision"): 192,  # SPLIT-CANDIDATE
    ("src/cadrumo/application/modelo/_filing_actions.py", "file_modelo_revision"): 206,  # SPLIT-CANDIDATE
    # Recovered-feature growth (stash recovery); SPLIT-CANDIDATE: owners extract helpers.
    ("src/cadrumo/application/filing/__init__.py", "build_draft"): 208,  # SPLIT-CANDIDATE
    ("src/cadrumo/application/ledger/_actions_classification.py", "bulk_classify_from_csv"): 185,  # SPLIT-CANDIDATE
    ("src/cadrumo/application/modelo/_export.py", "export_modelo_revision"): 215,  # SPLIT-CANDIDATE
    ("src/cadrumo/application/modelo/_projection.py", "project_modelo_100_from_m130"): 290,  # SPLIT-CANDIDATE
    # Oversize callables pinned to their present size so future edits must split
    # before growing them. The calculate-with-diagnostics entry grew under the
    # source-mesh/diagnostics work and is re-pinned (SPLIT-CANDIDATE: extract the
    # diagnostic-collection helpers).
    (
        "src/cadrumo/application/modelo/_calculation_actions.py",
        "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
    ): 234,  # SPLIT-CANDIDATE (regrew past prior pin)
    # New peer-introduced trusted-mesh-sources entry function; pinned at
    # present size pending an owner split pass.
    (
        "src/cadrumo/application/modelo/_calculation_actions.py",
        "_calculate_modelo_revision_with_trusted_mesh_sources",
    ): 184,  # SPLIT-CANDIDATE
    (
        "src/cadrumo/domain/calculations/registry/_formula_runtime.py",
        "calculate_registry_snapshot",
    ): 228,  # SPLIT-CANDIDATE
    ("src/cadrumo/entrypoints/cli/_ledger.py", "ledger_classify"): 234,  # SPLIT-CANDIDATE
    # Extracted LLM ledger CLI verb; SPLIT-CANDIDATE.
    ("src/cadrumo/entrypoints/cli/_ledger_llm_cli.py", "ledger_saturate_llm"): 187,
    ("src/cadrumo/application/modelo/_quickfile.py", "run_modelo_quickfile"): 216,  # SPLIT-CANDIDATE
    (
        "src/cadrumo/application/modelo/_verification_actions.py",
        "verify_modelo_revision",
    ): 231,  # SPLIT-CANDIDATE (regrew past prior pin)
    ("src/cadrumo/application/overview/_calendar.py", "build_overview_calendar"): 192,  # SPLIT-CANDIDATE
    ("src/cadrumo/application/user_profile/_custody_carry.py", "_natural_key_resolvers"): 310,  # SPLIT-CANDIDATE
    ("src/cadrumo/core/observability/_context.py", "run_context"): 195,  # SPLIT-CANDIDATE
    ("src/cadrumo/entrypoints/cli/_ledger.py", "ledger_add"): 250,  # SPLIT-CANDIDATE (regrew to 245; small-headroom rebaseline)
    ("src/cadrumo/application/user_profile/_profile_repository.py", "create"): 188,  # SPLIT-CANDIDATE
    ("src/cadrumo/application/aggregation/_iva_ledger.py", "_classify_iva_transaction"): 208,  # SPLIT-CANDIDATE
    ("src/cadrumo/application/modelo/_calculation_actions.py", "_resolve_bucket_source_mesh"): 200,  # SPLIT-CANDIDATE
    # +1 line from a Drive-folder-help docstring wording tweak; re-pinned to
    # the present size.
    ("src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py", "ledger_pull_folder"): 181,
    # MCP SDK handler-registration factory: every `@server.list_tools()` /
    # `@server.call_tool()` / etc. handler must close over `server`, `window`,
    # and the persona/telemetry gates built earlier in the function, so the
    # handlers cannot be hoisted to module level without threading that state
    # through explicit parameters on every handler. SPLIT-CANDIDATE: extract
    # the per-capability handler-builder closures (tools/prompts/resources)
    # into factory helpers that take the shared state as arguments.
    ("src/cadrumo/entrypoints/mcp/_server.py", "build_server"): 577,  # SPLIT-CANDIDATE (regrew past prior pin)
    (
        "src/cadrumo/entrypoints/mcp/_server.py",
        "_call_tool",
    ): 218,  # SPLIT-CANDIDATE (+1: telemetry-refusal startup guard, 02b3656095)
    # New peer-introduced running-preflight recorder; pinned at present size
    # pending an owner split pass.
    ("src/cadrumo/application/workflow/_engine.py", "_stage_running_preflight"): 184,  # SPLIT-CANDIDATE
}


def _aeat_python_files() -> tuple[Path, ...]:
    return package_python_files(include_data=True)


def _relative(path: Path) -> str:
    return repo_relative(path)


def test_tracked_python_modules_do_not_exceed_line_budgets() -> None:
    offenders: list[str] = []
    for path in _aeat_python_files():
        relative = _relative(path)
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        budget = _MODULE_LINE_LIMIT_OVERRIDES.get(relative, _DEFAULT_MODULE_LINE_LIMIT)
        if line_count > budget:
            offenders.append(f"{relative}: {line_count} lines > budget {budget}")

    assert offenders == [], "Python module size budget exceeded:\n  " + "\n  ".join(offenders)


def test_tracked_production_callables_do_not_exceed_line_budgets() -> None:
    offenders: list[str] = []
    for path, tree in package_ast_items(include_data=True):
        relative = _relative(path)
        if "/tests/" in relative:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.end_lineno is None:
                continue
            line_count = node.end_lineno - node.lineno + 1
            budget = _CALLABLE_LINE_LIMIT_OVERRIDES.get((relative, node.name), _DEFAULT_CALLABLE_LINE_LIMIT)
            if line_count > budget:
                offenders.append(f"{relative}:{node.name}: {line_count} lines > budget {budget}")

    assert offenders == [], "Python callable size budget exceeded:\n  " + "\n  ".join(offenders)
