---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S06'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cpdefix-followup-allgreen with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-05-cpdefix-followup-allgreen-plan placeholders are machine-filled by
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
     The Audit current deferred and reserved source-kind partitions for registry-declared but unenrolled sources and ## Scope

- `src/aeat/application/aggregation/_source_mesh.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Audit current deferred and reserved source-kind partitions for registry-declared but unenrolled sources

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Run RAG code discovery for deferred and reserved source-kind partitions.
- Read the application mesh parity, live missing-source, and registry source-enrollment gates.
- Run the focused source-partition gate suite.
- Extract the current committed-registry source inventory and compare it against live dispositions.

## Outcome

The current source-kind partition is healthy:

- Declared source kinds are all classified as `ENROLLED` or `DEFERRED` under the live mesh.
- No `RESERVED_SOURCE_KINDS` member is declared by the committed registry.
- Current reserved set: `ledger_transaction`, `purchase_invoice_evidence`.
- Current deferred set: `atribucion_member`, `bienes_inversion_regularizacion`, `donativo_donor`, `prorrata_regularizacion`, `refund_operation`, `related_party_operation`.

Verification passed:

`uv run --no-sync pytest -q -n 0 src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py src/aeat/application/modelo/tests/test_source_mesh_missing_sources.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py --tb=short`

Result: 25 passed.

The computed inventory reported:

- `declared_not_enrolled_or_deferred=` empty.
- `reserved_declared=` empty.

No code changes were required.

## Notes

This confirms the current allgreen campaign should not dispatch a source-enrollment fixer until a current deferred trigger or reserved-source promotion trigger fires.
