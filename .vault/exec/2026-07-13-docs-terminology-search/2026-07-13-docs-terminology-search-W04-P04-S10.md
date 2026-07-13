---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S10'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-terminology-search with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-07-13-docs-terminology-search-plan placeholders are machine-filled by
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
     The Re-run the held-out miss-rate over the widened mapping, commit the measurement, and apply the ADR D3 gate: implement rung 2 only above the ten-percent top-five miss line, else record the standing baseline and ## Scope

- `dev/docs/terminology/`
- `.vault/audit/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-run the held-out miss-rate over the widened mapping, commit the measurement, and apply the ADR D3 gate: implement rung 2 only above the ten-percent top-five miss line, else record the standing baseline

## Scope

- `dev/docs/terminology/`
- `.vault/audit/`

## Description

- Grow the held-out set 5 -> 20 cases: one per promoted concept sample,
  expectations curated from the concept's own card and its registry-grounded
  primary legal ref, independent of sweep output.
- Re-run the held-out miss-rate over the widened mapping and apply the ADR
  D3 gate at threshold 0.10.
- Retarget the golden-query and index-coverage gates from the sidecar-era
  contract to the post-cutover source-path contract, and drop the dead
  pre-rename raw-html exclusion from the ignore file.

## Outcome

GATE DECISION (amended after the close honesty review): the initial
20/20-hit, 0.0-miss measurement was tautological (all-vocabulary cases
seeded with their own concept cards; audit SHARP-1). After remediation -
out-of-sample case class, ratified 0.10 threshold, top-five bound, and a
committed report writer - the honest measurement reads 32 cases, 26 hits,
miss-rate 0.1875: the gate FIRES IMPLEMENT-RUNG-2
(miss-rate-post-widening.json). Rung 2 is formally deferred into its own
follow-up pipeline per ADR Update 2. The retargeted sidecar-exclusion
coverage gate passes; the dedup and staleness machinery is validated
against the post-cutover contract.

## Notes

Two verifications are service-pending, not failed: the golden-query live
suite and one incremental reindex red at close because the shared RAG
service was taken down for team maintenance mid-run (port_unreachable);
the sole staleness miss is the S10 report itself, written after the last
completed reindex. Both are integration-lane, dev-box-only checks; every
deterministic artifact (mapping, coverage, miss-rate) was captured while
the service was up. Re-run `pytest dev/docs/preprocess/tests -m
integration` after `vaultspec-rag index --type code --port 8766` when the
service returns.
