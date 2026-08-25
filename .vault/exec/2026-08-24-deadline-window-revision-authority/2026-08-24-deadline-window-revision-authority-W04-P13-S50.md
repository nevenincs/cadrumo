---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9fbc3e9cec6f36eb1111750df736cc6e19bfe949f32b582d2f26b1282df0a807'
step_id: 'S50'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S50 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Restore real CLI calendar parity for canonical filing evidence and locked-profile rendering after concurrent projection changes, keeping the CLI a thin consumer of overview and registry deadline authority and ## Scope

- `src/cadrumo/entrypoints/cli/`
- `src/cadrumo/application/overview/`
- `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Restore real CLI calendar parity for canonical filing evidence and locked-profile rendering after concurrent projection changes, keeping the CLI a thin consumer of overview and registry deadline authority

## Scope

- `src/cadrumo/entrypoints/cli/`
- `src/cadrumo/application/overview/`
- `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py`

## Description

- Reproduce the six real CLI parity failures under the integration marker.
- Trace each missing field to the compact transport projection rather than the canonical overview builder.
- Replace lossy entry and event summaries with the existing complete typed payloads.
- Resolve warning remedies through the existing command-catalogue resolver and reuse the result in JSON.
- Render the common profile header for locked profiles while retaining the explicit locked-state row.
- Confirm by exact-symbol search that no deadline, evidence, status, cadence, selector, or action resolver was redeclared.

## Outcome

The real calendar JSON now preserves canonical deadline shift metadata, complete filing evidence, AEAT submission timestamps, and schema-resolved warning remedies. All-profile text includes a common profile header for locked profiles. The CLI remains a transport adapter over application-owned calendar state.

## Notes

The initial integration run established exactly six failures and 16 passes. Ruff check and format check pass for all three changed CLI files. Formal re-review accepted the final diff after the resolved warning action was explicitly serialized in JSON mode. A post-fix pytest rerun could not collect because a concurrent, out-of-scope persistence-storage change temporarily removed the public `create_profile_custody_sentinel` export; this blocker occurs before the S50 modules load and was not modified here.
