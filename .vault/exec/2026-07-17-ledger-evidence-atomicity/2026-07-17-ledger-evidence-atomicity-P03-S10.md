---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Prove modelo audit exposes check without replay, backend replay calls, replay result schemas, or synthetic replay events and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove modelo audit exposes check without replay, backend replay calls, replay result schemas, or synthetic replay events

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`

## Description

- Add `test_audit_replay_command_is_removed` (invoking `modelo audit replay` fails as an unknown command) and `test_audit_replay_result_schema_is_not_registered` (`modelo.audit.replay` absent from `SCHEMA_REGISTRY`).
- Rewrite the end-to-end workflow test to `show -> check -> export` (no replay leg) and drop `replay` from the accepted-vocabulary map and the no-active-profile refusal loop.
- Remove `test_audit_replay_help_disclaims_aeat_contact` (its `replay_help` locale key is gone).

## Outcome

- Proves the audit surface exposes check without a replay command, replay result schema, or replay locale key, while show/check/export stay green. `test_audit_verbs.py`: 11 passed (integration). Commit `87f49c5d2f`.

## Notes

- Real Typer runner against a real EvidenceBundleService and isolated SQLite+filesystem backend; no mocks.
