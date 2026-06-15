---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S17'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
  - "[[2026-06-15-service-capabilities-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The DEFERRED follow-up: add an llm_vision=off two-mode (scan PDF + image) evidence-refusal regression (honesty review M1) and ## Scope

- `src/aeat/application/ledger/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DEFERRED follow-up: add an llm_vision=off two-mode (scan PDF + image) evidence-refusal regression (honesty review M1)

## Scope

- `src/aeat/application/ledger/tests`

## Description

- Persist a real `UserProfileRecord` carrying `capabilities.llm_vision=false` into the active test bucket (via `UserProfileLifecycleRepository.save`, no mocks), so `resolve_active_capability` reads the opted-out posture.
- Parametrize over both on-host read modes — a scan-only PDF (rasterise path) and an image attachment (direct-bytes path) — and assert `_resolve_evidence` raises `PurchaseInvoiceEvidenceInputError` naming the `llm_vision on` opt-in command.

## Outcome

Closes honesty-review finding M1. The `llm_vision` gate's coverage of every on-host read mode is now pinned by a regression, so a future read mode that lands above or below the gate cannot silently bypass the opt-out. 9 vision-evidence tests pass; ruff + ty clean. Committed as `9803e9dc0`.

## Notes

The `isolated_runtime_profile` fixture provisions a bucket manifest, so `register_minimal_profile` (which refuses on an existing manifest) is the wrong tool here; the record is written directly through the lifecycle repository — the same save path the source-mesh live tests use — and read back via the active-profile resolver.
