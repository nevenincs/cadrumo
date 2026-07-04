---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S21'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace agent-harness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-07-02-agent-harness-plan placeholders are machine-filled by
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
     The status:deferred-gated (blocked on Track-1 per-form surfaces, generally) - author the remaining Tier-B per-modelo completion skills beyond the M130/M303 vertical slice, each authored by diff against the shared lifecycle-spine fragment and ## Scope

- `src/aeat/_data/agent/skills/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# status:deferred-gated (blocked on Track-1 per-form surfaces, generally) - author the remaining Tier-B per-modelo completion skills beyond the M130/M303 vertical slice, each authored by diff against the shared lifecycle-spine fragment

## Scope

- `src/aeat/_data/agent/skills/`

## Description

- Re-assess the D6 Tier-B per-modelo skill deferral gate now that the Track-1 per-form registry surfaces have settled: the obligation-coverage ratchet is complete (`UNMODELED_OBLIGATIONS` residual 0, `FLEET_SIZE` 72), so the per-form surfaces each Tier-B skill cites are grounded.
- Confirm the remaining Tier-B per-modelo completion skills beyond the M130/M303 vertical slice have been authored by diff against the shared lifecycle-spine fragment, and shipped.
- Record that the full Tier-B per-modelo skill matrix was authored and shipped by the sibling `agent-harness-refoundation` campaign (100% complete), not under this retroactive plan's Phase P07.

## Outcome

- The D6 gate is cleared. The per-form registry surfaces the Tier-B skills cite are settled: obligation-coverage P03.S13 closed the UNMODELED ratchet to 0, and each modelo the skill matrix covers has a grounded registry definition.
- The full Tier-B per-modelo completion skill matrix is shipped under `src/aeat/_data/agent/skills/`: seventeen `preparar-modelo-*` skills (100, 111, 115, 130, 131, 180, 190, 193, 200, 202, 303, 309, 322, 349, 353, 369, 390), each carrying its form-specific delta over the shared lifecycle spine and its `applies_when` selection predicate. This is the full Tier-B set beyond the M130/M303 slice the Step scopes.
- This Step is closed as delivered-elsewhere: the deferral it recorded is resolved and no further Tier-B authoring is owed under this plan.

## Notes

- Ownership: the Tier-B per-modelo skill authoring is owned by the `agent-harness-refoundation` L3 plan (100% complete, 90/90 steps), not this retroactive `agent-harness` plan. Representative shipping commits: `8d9cf6fe8d` (author preparar-modelo-100 Tier-B skill), `ece7dde36e` (`applies_when` for preparar-modelo-303, `W05.P10.S55`), `424d42bc3e` (`applies_when` for preparar-modelo-100, `W05.P10.S45`). The parent ADR's ratification section already records D6 as shipped (17 Tier-B per-modelo skills).
- No code was authored in this pass: the Step is a deferral record whose gate cleared and whose deliverable landed under the sibling campaign; the skills directory was not edited, only this exec record and the plan checkbox.
