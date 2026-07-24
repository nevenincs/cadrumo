---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S24'
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
     The S24 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
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
     The Convert the descendiente and repair verbs into deep-link doors into the flow and delete their bespoke prompt loops in the same change and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_descendiente.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Convert the descendiente and repair verbs into deep-link doors into the flow and delete their bespoke prompt loops in the same change

## Scope

- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Build a descendant-only flow definition in `src/cadrumo/application/wizard/_descendant_door.py` adopting the shipped count page, repeating group, and adoption flow-validator — nothing re-authored; strip the count page's entity-type gate because the door hosts no entity-type page and the definition validator rejects gates naming absent pages.
- Seed the door from persisted facts through the inverse projection and `resume_flow` in modify mode with a resume state, driven through the substrate frontends that accept it (the shared wrapper lacks the parameter and was not forked); the capability probe stays the single authority and a non-interactive host refuses instructively.
- Commit through the canonical upsert-plus-clearing composition in one atomic write; checkpoint unavailable in both modes, so an interrupted door walk discards cleanly with no partial descendant state.
- Open the door from the bare `aeat config profile descendiente` invocation — exactly the command the modify-mode advisory notice suggests — while preserving the add, list, and remove flag verbs verbatim as the automation contract.

## Outcome

Landed as `353ea7585a` with the review disposition follow-up in `4df00869d6`. Review verdict: every functional, safety, and architectural axis passed; the one blocking finding — a plan-step identifier embedded in a test docstring, breaching the code-stands-alone boundary — was reworded onto behaviour and landed. Nine real-behaviour tests over real encrypted storage: seed two, edit, count-shrink clears the orphaned index on read-back; adoption refusal live on the door; childless seeds empty; non-descendant facts untouched; the flag verbs survive the callback change. Conformance 501 green.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The plan row's "repair" clause is INAPPLICABLE, verified twice (executor and reviewer): the repair surface is entirely non-interactive diagnostics with no prompt loop and no descendant concern — recorded here rather than silently skipped. Likewise no bespoke prompt loop existed in the descendiente file; the door is additive over the preserved flag grammar.
- Review medium, ledger-bound: the door (like the pre-existing flag verbs) carries no entity-type guard, so a legal-entity profile can open the descendant editor and write facts that are INERT for its modelo set (the mínimo-por-descendientes bindings exist only on the renta-personal snapshot — traced, not assumed). Follow-up: an applicability advisory at the descendiente entry for non-natural-person profiles, door and flag verbs alike.
- Review lows, ledger-bound: the two-line commit-composition restatement and the capability-dispatch restatement are documented drift surfaces (a shared helper would erase both cheaply); the preserved flag-verb path clears one aggregate fewer than the canonical clearing helper (pre-existing divergence — the flag path should adopt the helper); a composed create-edit-reopen door round-trip assertion would lock the re-seed behaviour.
- The reviewer's working-tree scope note alleging an active rename sweep was verified FALSE against the tree (all named files clean, tokens intact) — the commit-anchored findings stand; the hallucinated scope claim is recorded as an instance of the verify-every-finding discipline.
