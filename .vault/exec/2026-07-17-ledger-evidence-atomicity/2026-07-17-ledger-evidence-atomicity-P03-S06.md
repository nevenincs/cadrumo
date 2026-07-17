---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S06'
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
     The S06 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Remove EvidenceBundleService replay, its public export, and backend tests while preserving evidence check and unrelated observability replay facilities and ## Scope

- `src/cadrumo/application/evidence/_service.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove EvidenceBundleService replay, its public export, and backend tests while preserving evidence check and unrelated observability replay facilities

## Scope

- `src/cadrumo/application/evidence/_service.py`

## Description

- Remove `EvidenceBundleService.replay` (a thin wrapper that delegated to `check` — a second, weaker path claiming the same integrity contract) and its module/class docstring references to the replay verb.
- Remove the backend replay test `TestReplay.test_replay_never_mutates_bundle_state`.
- Preserve `check` (the verifier) and the unrelated observability parity-tape replay facility.

## Outcome

- The evidence service now exposes only build/verify/export; there is no duplicate replay authority. Landed together with the CLI command removal (S08) and proof (S10) in one green vertical, commit `87f49c5d2f`. Evidence suite 20 passed.

## Notes

- None.
