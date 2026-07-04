---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S20'
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
     The S20 and 2026-07-02-agent-harness-plan placeholders are machine-filled by
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
     The status:deferred-gated (blocked on Track-1 #7 obligation-coverage) - enumerate the Tier-A persona-entry itinerary set once the profile-fact predicates it derives from are settled and ## Scope

- `src/aeat/_data/agent/skills/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# status:deferred-gated (blocked on Track-1 #7 obligation-coverage) - enumerate the Tier-A persona-entry itinerary set once the profile-fact predicates it derives from are settled

## Scope

- `src/aeat/_data/agent/skills/`

## Description

- Re-assess the D5 Tier-A persona-entry itinerary deferral gate now that its named blocker, Track-1 obligation-coverage, has cleared: `UNMODELED_OBLIGATIONS` is empty (residual 0), so the obligation universe the persona-entry itinerary derives from is settled.
- Confirm the profile-fact predicate mechanism the itinerary derives from is in place: each Tier-A persona-entry and life-situation skill now declares its selection predicate in the `applies_when` frontmatter field, derived from profile facts rather than hand-enumerated.
- Record that the Tier-A persona-entry itinerary set the Step describes was authored and shipped in full by the sibling `agent-harness-refoundation` campaign, which is 100% complete (90/90 steps), rather than under this retroactive plan's Phase P07.

## Outcome

- The D5 gate is cleared. Obligation-coverage P03.S13 closed the ratchet (residual `UNMODELED_OBLIGATIONS` 0, `FLEET_SIZE` 72, `validate_registry()` green), settling the profile-fact/obligation surface the itinerary is derived from.
- The Tier-A persona-entry itinerary skills are shipped and live under `src/aeat/_data/agent/skills/`: the life-situation itineraries (`inicio-actividad`, `cese-actividad`, `cierre-trimestre`, `resumen-anual`, `rectificar-declaracion`, `regularizar-atrasos`) authored in refoundation Phase `W05.P11`, and the persona-entry selection predicates lifted into `applies_when` frontmatter in refoundation Phase `W05.P10`. Each derives its selection from profile-fact predicates, satisfying the D5 closure principle.
- This Step is closed as delivered-elsewhere: the deferral it recorded is resolved, and no further Tier-A authoring is owed under this plan.

## Notes

- Ownership: the itinerary authoring is owned by the `agent-harness-refoundation` L3 plan (100% complete), not this retroactive `agent-harness` plan. Representative shipping commits: `151614fa3e` (cese-actividad, `W05.P11.S75`), `ccecfd5e59` (inicio-actividad, `W05.P11.S73`), `c9b7106c57` (rectificar-declaracion, `W05.P11.S71`), `c85655d633` (resumen-anual, `W05.P11.S69`), `651d84c5f5` (cierre-trimestre, `W05.P11.S67`), `8eea7a3747` (regularizar-atrasos, `W05.P11.S65`). The parent ADR's ratification section already records D5 as shipped (6 Tier-A itinerary skills).
- No code was authored in this pass: the Step is a deferral record whose gate cleared and whose deliverable landed under the sibling campaign; the skills directory was not edited, only this exec record and the plan checkbox.
