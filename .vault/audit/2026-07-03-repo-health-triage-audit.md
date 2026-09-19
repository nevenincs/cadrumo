---
tags:
  - '#audit'
  - '#repo-health-triage'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:c7c8d6b953b4d6653db7ce61b7d9d9a6f7a76fbd0d52119d89dd4538ac7ce6f8'
related:
  - "[[2026-06-04-repo-health-triage-plan]]"
  - "[[2026-06-08-repo-health-diagnostics-audit]]"
---

# `repo-health-triage` audit: `2026-07-03 final diagnostic surface`

## Scope

This audit persists the closeout diagnostic evidence for the final phase of the repo-health-triage campaign (W06.P21). It carries two step-scoped finding sets on one 2026-07-03 diagnostic pass, because the live CLI (`vaultspec-core` 0.1.36) mints one audit per feature per date and does not derive a narrative filename infix; both step evidence sets are therefore recorded as distinct step-labeled finding blocks in this single rolling-log audit:

- W06.P21.S83 — the hard-gate suite, recorded as owner-scoped green with every full-tree red distinguished to its owning campaign.
- W06.P21.S84 — the full quality-audit surface, recorded as the final red/amber/green diagnostic matrix.

It reruns the fast static hard-gate surface and the advisory quality-audit surface against committed HEAD in the shared factory worktree. The prior S83 attempt (finding HEALTH-025-S83 in the 2026-06-08 diagnostics audit) left the row open because the shifted worktree was not green; this pass closes the row honestly by distinguishing owner-surface state from peer churn rather than asserting a false full-tree green.

The justfile gate surface was restructured after the plan was authored: the plan Verification prose names retired recipes (`just tooling-doctor`, `just typecheck`, `just lint`, `just test`, `just audit-structure`, `just verify-shims`). The live hard-gate surface is now the `check-*` recipe family plus the `dev.quality.*` wrappers. Each gate below was run directly with `uv run --no-sync` and its full output captured to disk; the FAILED and error lines were extracted from the on-disk logs, never through an upstream head/tail truncation.

The source tree carries no peer working-tree edits (`git status` shows only `.vault/` documents and generated `docs/api/*.rst` stubs dirty), so every gate result reflects committed HEAD, not uncommitted peer WIP.

The repo-health-triage owner surface is the set of files this campaign authored or refactored across W06.P18-P20: `application/wizard/_commands.py`, `entrypoints/cli/_modelo.py`, `entrypoints/cli/_ledger.py`, `domain/calculations/registry/_formula_runtime.py`, `domain/calculations/registry/_formula_initial_values.py`, `domain/renta/_ledger_expenses.py`, the `application/aggregation` package, `justfile`, `pyproject.toml`, and `.semgrepignore`. `domain/filing/_repository.py` (S68) has since been relocated to the adapters layer by the arch-remediation-ports-inversion campaign and no longer exists at that path.

## Findings

### hard-gate-matrix | high | full-tree red is entirely peer-owned; owner surface is green

Full hard-gate matrix (full-tree verdict versus owner-scoped verdict):

- `ruff check .` (check-style): full-tree RED, 14 errors across 8 files. Owner-scoped GREEN. Failing files are `dev/import_centralization_codemod.py`, `adapters/persistence/profile/filing_amendments.py`, `adapters/persistence/profile/filing_drafts.py`, `agent/eval/_live_harness.py`, `application/filing/tests/test_complementaria_repository.py`, `application/modelo/tests/test_bienes_inversion_advisory.py`, `application/state_projection.py`, `tests/test_importlinter_ledger.py`. None is an owner file.
- `ruff format --check .` (check-format): full-tree RED, 5 files would reformat (`packaging/mcpb/tests/test_build.py`, `agent/eval/_live_harness.py`, `application/corpus_search/tests/test_hybrid_real_model_recall.py`, `application/storage/calc_sheets/tests/test_modelo_export_parity.py`, `tests/test_wheel_content_boundary.py`). None is an owner file.
- `lint-imports` (check-imports): full-tree RED, the AEAT layered architecture contract is BROKEN (the other 4 contracts kept). 19 violating edges, primarily tests reaching adapters plus one production module `application/modelo/_review_package_signing`. No owner file appears.
- `dev.quality.relative_imports` (check-relative-imports): full-tree RED, 8 violations across 4 test files (`adapters/inbound/tests/test_extraction_parser_paths_resolve.py`, `application/corpus_search/tests/test_hybrid_real_model_recall.py`, `entrypoints/cli/tests/test_overview_backlog_verb.py`, `entrypoints/cli/tests/test_overview_calendar_degradation.py`). No owner file appears.
- `deptry` (check-dependencies): GREEN. No dependency issues across 1214 scanned files.
- `ty check src` (check-types, ty half): full-tree RED, 912 diagnostics — a full-source debt inventory dominated by `invalid-argument-type` (560) and `unresolved-attribute` (202), swollen by the test-topology relocation pulling more test modules into scan and by a month of peer source growth. This is the same advisory full-tree debt-inventory signal recorded at ~800 in HEALTH-017/019, not a production-readiness gate.
- `semgrep scan --config auto src/aeat` (check-security): exits 0. One blocking-class finding remains: the Python-3.7 `importlib.resources` backward-compat rule on a `from importlib.resources.abc import Traversable` import. The project targets Python 3.13, so this is a framework false positive from the broad `--config auto` ruleset (the `.semgrepignore`-gated `audit-security` lane that S81 drove to zero has been retired from the justfile). No owner file is flagged.

### owner-scoped-green | high | every owner deliverable passes its gate

Owner-scoped reruns on the surviving owner files:

- `ruff check` over the owner Python files: `All checks passed!` (exit 0).
- `ruff format --check` over the owner Python files: all formatted (exit 0).
- `ty check` over the owner production files (`wizard/_commands.py`, `cli/_modelo.py`, `cli/_ledger.py`, `_formula_runtime.py`, `_formula_initial_values.py`, `renta/_ledger_expenses.py`): 1 diagnostic, at `_formula_runtime.py:416` (`Expected Mapping[str, str], found dict[str, object] | None`). Line-scoped blame attributes that line to peer commit `ca639cb4de` (`feat(calc): type unresolved M210 outcomes`, 2026-07-02), which edited the M210 outcomes path after the campaign closed. It is not an owner-authored diagnostic.
- The owner aggregation package ty diagnostics (48 in the full package scan) are concentrated in relocated/added aggregation *test* modules asserting `Expected BindingSourceKind, found str`. That friction is the bindings-interface-hardening enum tightening (ADR `2026-06-14-bindings-interface-hardening-adr`), which post-dates the S67 aggregation zero-error close (2026-06-05) and re-typed `source` as a strict enum where the tests still pass raw strings. It is peer-introduced drift on peer-relocated tests, not an owner residual.

### peer-red-disclosure | medium | every full-tree red distinguished to its owning campaign

Per the full-tree-gate owner-distinction discipline, each red is attributed and disclosed, not absorbed or fixed under this campaign's commit:

- Ruff check/format reds: arch-remediation-ports-inversion (`3476219f28` state_projection relocation, `a43d1b0054` filing_amendments relocation), import-centralization (`3423f51b21` codemod test extension), and the operator-directed bulk WIP landing (`01d74c248f` test_bienes_inversion_advisory).
- Layered-architecture contract break: review-package #421 (`92ec450160` `_review_package_signing` production import of adapters) plus test-side edges from arch-remediation, corpus-search, and overview campaigns. This is the long-standing layered-contract red first recorded in HEALTH-002 and re-confirmed in HEALTH-017/019.
- Relative-import reds: corpus-search (`cc1504bfa4`), overview graceful-degradation (`59317b5b47`), and arch-remediation extraction-parser inversion (`034c9e84e6`).
- Full-tree ty growth: broad peer source and test-relocation drift; the single owner-file line (`_formula_runtime.py:416`) is peer commit `ca639cb4de`.
- Registry-load peer regression: loading the Modelo 131 2025/2026 revisions raises a `semantic_role_cardinality 'intentional_singleton'` duplication error introduced by peer commit `939f3fe010` (#594, 2026-07-03). This errors any test that loads those revisions (5 `_formula_runtime` tests errored on it); the 6 wizard command tests over owner code passed, confirming owner behavior is intact.

None of the disclosed reds is owner-authored, and none was fixed under this campaign's SHA.

### S84-quality-audit-matrix | high | final red/amber/green matrix is peer-red, owner-clean

W06.P21.S84 reran the full quality-audit surface. The retired `just quality-audit` umbrella recipe is now the `audit-*` lane family plus the composed `dev.audit.report` verdict. Final diagnostic matrix (from `audit-health-report`, overall RED):

- shadowing: AMBER. 1 pinned/tolerated multi-facade symbol (`DEFAULT_IVA_GENERAL_RATE_PCT`), grandfathered debt. Not an owner symbol.
- duplication: AMBER. 71 clone clusters, 0.49% duplicated lines. Advisory, tolerant lane (exit 0). The clones cluster in peer-created split CLI modules (`entrypoints/cli/_modelo_work_revision_cli.py`, `_modelo_work_verification_cli.py`) that did not exist during the campaign.
- layering: RED. The AEAT layered architecture import-linter contract is broken (same peer edges as S83's check-imports; see the peer-red-disclosure finding).
- complexity: RED. `dev.audit.complexity` (production lane, now baseline-driven) reports 267 new/regressed hotspots, 210 baselined, 23 resolved. The 267 are overwhelmingly `[NEW]` in peer-created split modules (`_modelo_cli_support.py`, `_review_projection.py`, `_ledger_lifecycle_cli.py`, `_modelo_work_wizard_cli.py`, `_calculation_actions.py`) produced by the arch-remediation and module-decomposition campaigns after this campaign closed.
- dead-code (vulture): 4 findings, all peer (`adapters/outbound/google/_document_link_resolver.py` unused Google API kwargs, `application/storage/calc_sheets/_engine.py` unreachable branch). No owner file.
- dependency drift (deptry): GREEN (0 issues) — the S79 deliverable holds.

Owner complexity deliverables verified still holding under the current tree (the campaign's actual W06.P19 reductions):

- `application/wizard/_commands.py::build_wizard_command` (S73): cognitive 3, PASSED. (`_run_full_flow` in the same file is 31 but is a pre-campaign function last edited 2026-05-20, never an S73 target; S73's deliverable was `build_wizard_command`.)
- `domain/calculations/registry/_formula_initial_values.py::initial_values` (S75): cognitive 2, PASSED; `_initial_values_for_casillas`: 5, PASSED.
- The S75-out-of-scope residual `calculate_registry_snapshot` (documented in HEALTH-019-S75 as a runtime-orchestration hotspot outside the S75 initial-value/M210 scope) has regressed 17→30 via peer edits (`0e5be57869`, CasillaId migration WIP, 2026-06-26); it was never an owner deliverable.

No RED or AMBER dimension of the final matrix is owner-authored.

## Recommendations

Close W06.P21.S83 and W06.P21.S84 as owner-scoped green: the repo-health-triage owner surface passes ruff, ruff-format, production type checks, and its complexity deliverables (`build_wizard_command`, `initial_values`) still hold below threshold; dependency drift stays green. Every full-tree and quality-audit red is peer-owned and disclosed above. Do not write a complexity or ruff baseline to absorb the peer debt under this campaign. The layered-architecture contract, full-tree ty inventory, ruff/format reds, duplication/complexity peer growth, and the M131 registry-load regression are handed to their owning campaigns (arch-remediation-ports-inversion, review-package #421, import-centralization, corpus-search, overview, and the M131 #594 fix) for their own closeout gates.
