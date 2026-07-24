---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S06'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
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
     The Delete CENSO_REFRESHED and reconcile every CENSO_APPLIED consumer per the retired-enum-member discipline and ## Scope

- `src/cadrumo/domain/buckets/_event.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete CENSO_REFRESHED and reconcile every CENSO_APPLIED consumer per the retired-enum-member discipline

## Scope

- `src/cadrumo/domain/buckets/_event.py`

## Description

- Enumerate every consumer of the retired `CENSO_REFRESHED` bucket-event member across production, tests, and documentation.
- Delete the `CENSO_REFRESHED` member from the closed `BucketEventType` catalogue and rewrite its heading comment to describe only the retained dormant `CENSO_APPLIED` member.
- Update the `CENSO_DECLARATION_*` heading comment so it references the `profile.censo.applied` cotejo mirror event instead of the deleted refresh event.
- Update the catalogue-test docstring that cited the retired `profile.censo.refreshed/applied` mirror pair to name only `profile.censo.applied`.
- Leave `CENSO_APPLIED`, `CENSO_DEPENDENT_STAMPED_STALE`, and the three `CENSO_DECLARATION_*` members untouched.

## Outcome

The consumer inventory at HEAD resolved to two source consumers plus documentation citations. Production carried a single reference — the enum declaration in `src/cadrumo/domain/buckets/_event.py` — whose live-refresh precondition is permanently false: the live censo scrape and its `CensoSnapshot` snapshot substrate were retired and deleted, so no code path can ever satisfy the refresh emission. The only test consumer was a docstring narrative in `src/cadrumo/domain/buckets/tests/test_event_catalogue.py`; it asserted nothing on the member, so its reference was reconciled to name the retained cotejo event. The setup-event emission-contract gate is a required-member whitelist, not a full-catalogue iteration, so deleting a dormant member raised no emission-site demand, and the retained `CENSO_APPLIED` (dormant today, re-enrolled with a live emission site at the cotejo artefact-apply reconciliation) needs no invented emission site now.

Real-behavior gates: `src/cadrumo/domain/buckets/tests/` plus the setup emission-contract gate ran 21 passed. Full domain-plus-application collection reported 9330/9403 tests collected (73 deselected) with zero collection errors. Ruff lint and format both clean on the two touched files. A residual sweep confirmed no `CENSO_REFRESHED` or `censo.refreshed` reference remains anywhere under `src/cadrumo`.

## Notes

- Documentation citations of `BucketEventType.CENSO_REFRESHED` survive in the `aeat-spanish-stem-naming` governance rule (source under `.vaultspec/rules/` plus its generated provider copies and `GEMINI.md`). These are historical naming-convention examples, not code consumers, and do not break on the member's deletion; the generated copies must never be hand-edited (a sync would revert them), so they were left as-is and reported to the coordinator rather than swept in this code-reconciliation step.
- The mandatory `vaultspec-rag` code-index search could not complete: the code index was mid-reindex and its update job was stalled with no progress for 17+ minutes. Per standing direction the RAG service was not restarted. The vault decision-corpus semantic search did complete and surfaced the governing ADR; the exact-name consumer inventory was carried by grep, which is the complete site set for a named-string enum member.
