---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-research]]"
  - "[[2026-04-30-aeat-restructure-step-00-adr-lock-in-exec]]"
---

# 2026-04-30-aeat-restructure step-01 pre-move scan

## status

**COMPLETE** — three sub-passes ran; all findings have a disposition; the override-list candidate set is enumerated and audit-grounded.

Historical execution note: this is a pre-move planning scan. References
to shim-based preservation reflect the planning state at Step 1 and are
superseded by the delivered hard-cutover outcome (no retained root
compatibility shim layer).

## sub-pass 1 — dynamic imports / entry points

### method

`Grep` over `src/aeat/` for `importlib\.(import_module|util)` and `__import__\(`; manual scan of `pyproject.toml` for `aeat.*` script / entry-point / build-target references.

### findings

| # | Site | Pattern | Disposition |
|---|---|---|---|
| 1.1 | `src/aeat/core/errors/test_registry_enforcement.py:24,57` | `importlib.import_module(name)` walking the error-registry module list | **FIX** — rewrite map: registry walks string-named modules at `aeat.<module>._errors`; rebase script must adjust the input module list to the post-move dotted paths |
| 1.2 | `src/aeat/domain/formulas/test_smoke.py:15` | `importlib.import_module("aeat.domain.formulas")` | **FIX** — rewrite map: `aeat.domain.formulas` → `aeat.domain.formulas` post-move the smoke test passes via direct rewrite (rebase script's call). All callers updated in the same change-set as the Step 7 keystone PR |
| 1.3 | `src/aeat/entrypoints/cli/auth/test_auth_cli.py:27` | `__import__("re").compile(...)` | **STRIKE** — non-`aeat` import; defensive `re` access for ANSI stripping. No layout impact. |
| 1.4 | `pyproject.toml:75` — `[project.scripts] aeat = "aeat.entrypoints.cli:app"` | console-script entry point pinning `aeat.entrypoints.cli` import path | **FIX** — preserve via shim: `aeat/entrypoints/cli/__init__.py` retains `app` re-export from `aeat.entrypoints.cli`. No pyproject.toml change required if shim ships in Step 7 keystone PR. (Alternative: update pyproject.toml to `aeat.entrypoints.cli:app` — major bump unless shim covers; defer to shim path per ADR no-override semver rule.) |

Comment-only references (no code impact, no disposition): `pyproject.toml:45` mentions `aeat.status._parsers.expedientes` in a packaging comment — `status/` is one of the 4 empty placeholders flagged for deletion; comment will be obsolete post-Step-7 and is a Step 11 sanitization concern.

## sub-pass 2 — `__init__.py` re-exports across future layered boundaries

### method

Identify the modules that SPLIT across multiple future destination layers per ADR Implementation section + research-doc Tables 1–6 + audit findings 1, 3, 4, 5, 9, 13, 16, 20. For each splitting module, the OLD `__init__.py` re-exports become the source-of-truth for the rebase-script export-mapping work in Step 5; the NEW `__init__.py` files at the post-move locations MUST NOT cross-import siblings that violate the layered contract.

### findings

| Module | OLD `__init__.py` | NEW destinations | Risk pattern |
|---|---|---|---|
| `aeat.application.sync` | exports divergence taxonomy + classifier + repository + dispatchers | `domain/sync/` (taxonomy + classifier) + `application/sync/` (everything else) | new `domain/sync/__init__.py` MUST NOT re-import from `application.sync` |
| `aeat.application.filing` | exports records + builders + validator + reconciliation + repositories + history-repository + use-case orchestrators | `domain/filing/` (records, validator, reconciliation, repositories) + `application/filing/` (orchestrators) + `application/sync/` (history_repository per audit 5 misplacement finding) | new `domain/filing/__init__.py` MUST NOT re-import from `application.*`; all callers at the OLD `aeat/application/filing` path are updated to new canonical destinations in the Step 7 keystone PR |
| `aeat.adapters.outbound.aeat.auth` | exports Google cluster + AEAT cluster + gate + restrict_file_permissions | `adapters/outbound/google/` + `adapters/outbound/aeat/adapters/outbound/aeat/auth/` + `application/auth/` + `core/access_gate/` + `core/file_permissions.py` | already in ADR public-surface table; all callers at OLD `aeat/adapters/outbound/aeat/auth/__init__.py` updated to new canonical destinations in the Step 7 keystone PR; NEW `__init__.py` at each destination scoped to its own surface |
| `aeat.adapters.outbound.aeat.export` | exports lifecycle (engine + preflight + repository) + `_formats/` + LiveSubmitForbiddenError | `domain/submission/` (lifecycle) + `adapters/outbound/aeat/export/` (`_formats/`) + `core/access_gate/_errors.py` (LiveSubmitForbiddenError) | new `domain/submission/__init__.py` MUST NOT re-import from `adapters.outbound.*`; all callers at OLD `aeat/adapters/outbound/aeat/export` path updated to new canonical destinations in the Step 7 keystone PR |
| `aeat.domain.financial` | exports providers + transactions + invoices + categories + vat + aggregation + usage_ratios + attachments | 8-destination split per audit 20 across `adapters/inbound/financial/providers/`, `domain/transactions/`, `application/transactions/`, `domain/invoices/`, `application/invoices/`, `domain/attachments/`, `application/attachments/`, `application/aggregation/`, `domain/categories/`, `domain/vat/`, `domain/usage_ratios/` | each new `__init__.py` scoped to its own layer; all callers at OLD `aeat/domain/financial` path updated to new canonical destinations in the Step 7 keystone PR |
| `aeat.adapters.persistence.storage` | exports SQL + crypto + master-key + envelope + blob-store + secret-store + rotation + classification + redaction + corpus_manifest + locks + path_safety | 7 sub-modules under `adapters/persistence/storage/` + 5 core promotions to `core/` (classification, redaction, corpus_manifest, locks, path_safety) | new `adapters/persistence/storage/__init__.py` re-exports the encrypted-record contract bundle (10 symbols); 5 promoted symbols re-exported from `core/*` â all callers at OLD `aeat.adapters.persistence.storage` path updated to new canonical destinations in the Step 7 keystone PR |
| `aeat.core.errors` | exports infra cluster + 11 domain-specific exceptions | `core/errors/` (infra + firewall types) + `domain/formulas/_errors.py` (8 exceptions) + `entrypoints/mcp/_errors.py` (1) + `domain/testing/_errors.py` (2) | already in ADR public-surface table; all callers at OLD `aeat/core/errors` path updated to new canonical destinations in the Step 7 keystone PR |
| `aeat.domain.schema` | exports IR (models + cache + errors + protocols) + extraction (fetch + boe_extractor) | `domain/schema/` (IR) + `adapters/inbound/schema/` (extraction) | new `domain/schema/__init__.py` MUST NOT re-import from `adapters.inbound.*`; all callers at OLD `aeat/domain/schema` path updated to new canonical destinations in the Step 7 keystone PR |

### disposition

All 8 splitting-module `__init__.py` boundary risks: **FIX** in Step 7's keystone PR. The rebase-script (Step 5) ingests the OLD `__init__.py` export inventories and emits the NEW `__init__.py` files split by layer. The Step 5 `import-linter` contract enforces the layered-boundary rule on the NEW state; CI fails the keystone PR if any new `__init__.py` cross-imports.

The shims at the OLD locations are NOT layered-boundary risks because they live in entrypoint-zone (re-exports for backward-compat are read by callers from anywhere; the shim itself does not import "into" the domain layer in violation of the rule — it imports FROM domain/adapter destinations and the shim itself is ambient).

### residual

Per-module export inventories (which symbols re-export from which sub-module) materialise as part of Step 5 rebase-script construction. This sub-pass establishes the SET of modules requiring careful split at the `__init__.py` level; the per-symbol mapping is downstream tooling work.

## sub-pass 3 — module-level pytestmark axis-B audit

### method

`Grep` over `src/aeat/` for `pytestmark\s*=\s*\[?\s*pytest\.mark\.`. Classify each test file's axis-B marker (`domain_financial_input`, `domain_local_state`, `domain_aeat_remote`, `domain_submission`, `domain_mediation`, `domain_infra`) against the ADR Test-marker realignment table + the destination map per research-doc Tables 1–6. Surface tests where the rule's stated 2-bucket reclassification (`domain_local_state` → `domain_model` OR `domain_persistence`) does NOT cover the destination, plus tests that genuinely cross module boundaries.

### findings — destination-aware reclassification (rule extension)

The ADR's `domain_local_state` reclassification rule covers two destination buckets (`domain/` → `domain_model`; `adapters/persistence/` → `domain_persistence`). Audit found ~37 test files marked `domain_local_state` whose containing modules move to OTHER destinations:

| Cluster | Files | OLD marker | Containing-module destination | NEW marker per ADR table |
|---|---|---|---|---|
| `submission/_formats/*` | ~33 | `domain_local_state` | `adapters/outbound/aeat/export/` (audit 16) | `domain_outbound + domain_export` (sub-marker) |
| `review/test_*.py` | 3 | `domain_local_state` | `application/review/` | `domain_application` |
| `identity/test_documents.py` | 1 | `domain_local_state` | `adapters/inbound/identity/` | `domain_inbound` |

**Disposition: FIX**. The ADR's Migration mechanic / per-test-file rule needs to be extended to cover all 6 destination layers (`domain/`, `adapters/persistence/`, `adapters/inbound/`, `adapters/outbound/`, `application/`, `core/`), not just the 2 stated buckets. The mechanical rewrite is unambiguous given the destination → marker mapping in the ADR Test-marker realignment table; no manual override required for these 37 files. Application: ADR amendment text (rides in Step 2's first PR per no-design-only-PRs rule) extends the rule. The Step 7 keystone PR's marker-rewrite step applies the extended rule mechanically.

### findings — modules with already-correct axis-B markers (no concern)

Spot-checked counts (`domain_financial_input` → `domain_inbound`, `domain_aeat_remote` → `domain_outbound`, `domain_submission` → `domain_outbound + domain_export`, `domain_mediation` → `domain_application`, `domain_infra` → `domain_core`): mechanical 1:1 rename per ADR table; no manual override required.

### findings — manual override list (cross-module boundary-crossing tests)

Per ADR strict definition, "manual override" applies to test files that exercise symbols from multiple original modules whose destinations land in different layers. Audit method: scan for `test_integration_*` filenames and obvious multi-module test files.

| Candidate | Imports / scope | Override required? |
|---|---|---|
| `submission/_formats/test_integration_kent_e2e.py` | full produce → verify → export pipeline | NO — even though e2e in scope, file's containing module is `submission/_formats/` → `adapters/outbound/aeat/export/`. Rule-extension reclassification (above) handles it without manual override. |
| `submission/_formats/test_integration_kent_303_e2e.py` | same | NO — same as above |
| `submission/_formats/test_gap_story_consistency.py` | gap-story coverage | NO — module-scoped despite "gap-story" framing |
| `filing/_test_integration_wave4.py` | filing integration; the `wave4` token in filename is a `[STRIKE]` candidate per Step 11 sanitization rules | NO at this layer (single-module containment); however, the filename itself has a sanitization-rule violation (`wave4`) and is **FILE**'d for Step 11 attention. |

**Manual override list final count: 0** — every test file's destination + marker can be determined mechanically from the destination map + the rule-extension above. This satisfies the ADR Acceptance criterion "manual-override list zero-length OR audit-grounded" with zero entries (audit-grounded by exclusion).

### residual

The ADR rule extension (covering `adapters/inbound/`, `adapters/outbound/`, `application/`, `core/` destinations) is the only ADR amendment surfaced by sub-pass 3. The amendment text rides in Step 2's first PR (no-design-only-PRs rule). The Step 7 keystone PR's rebase-script applies the extended rule.

## aggregate findings ledger

| # | Source | Disposition | Carrier PR |
|---|---|---|---|
| 1.1 | sub-pass 1 — registry-walk dynamic imports | FIX | Step 7 keystone (rebase-script + shim) |
| 1.2 | sub-pass 1 — formulas smoke-test dynamic import | FIX | Step 7 keystone |
| 1.3 | sub-pass 1 — `__import__("re")` defensive pattern | STRIKE | n/a |
| 1.4 | sub-pass 1 — pyproject.toml `aeat.entrypoints.cli:app` entry point | FIX (via shim) | Step 7 keystone |
| 2.1–2.8 | sub-pass 2 — 8 splitting-module `__init__.py` boundaries | FIX | Step 5 (rebase-script construction) → Step 7 keystone (delivery) |
| 3.1 | sub-pass 3 — ADR test-marker rule extension to 6 layers | FIX (ADR amendment) | Step 2's first PR |
| 3.2 | sub-pass 3 — 37 destination-aware test reclassifications | FIX (mechanical rewrite per extended rule) | Step 7 keystone |
| 3.3 | sub-pass 3 — `filing/_test_integration_wave4.py` filename sanitization | FILE | Step 11 sanitization loop (per-module pass over `filing/`) |

**Manual-override list**: zero-length, audit-grounded.

**No "blocker — cannot dispose" findings.**

## artefacts produced by this step

- this exec record (uncommitted; rides into Step 2's first PR alongside Step 0's exec record + ADR amendment)
- ADR amendment text additions (committed in Step 2's first PR):
  - Test-marker realignment / Migration mechanic — per-test-file: extend rule to cover all 6 destination layers per the table in sub-pass 3 findings above.
  - Operational contract / Acceptance criteria: confirm manual-override list is zero-length (audit-grounded).
- No new GitHub issues filed. (`filing/_test_integration_wave4.py` is **FILE**'d for Step 11 sanitization, not for issue tracking.)

## next step

Step 2 — Phase-1 dead-code deletion PRs (one PR per item; PR 1 carries Step 0 exec record + Step 1 exec record + ADR amendment text + migration-helper TODO annotations + first dead-code deletion).
