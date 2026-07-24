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

# Convert the descendiente and repair verbs into deep-link doors into the flow and delete their bespoke prompt loops in the same change

## Scope

- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

## Description

- Build a descendant-only flow definition in `src/cadrumo/application/wizard/_descendant_door.py` adopting the shipped count page, repeating group, and adoption flow-validator — nothing re-authored; strip the count page's entity-type gate because the door hosts no entity-type page and the definition validator rejects gates naming absent pages.
- Seed the door from persisted facts through the inverse projection and `resume_flow` in modify mode with a resume state, driven through the substrate frontends that accept it (the shared wrapper lacks the parameter and was not forked); the capability probe stays the single authority and a non-interactive host refuses instructively.
- Commit through the canonical upsert-plus-clearing composition in one atomic write; checkpoint unavailable in both modes, so an interrupted door walk discards cleanly with no partial descendant state.
- Open the door from the bare `aeat config profile descendiente` invocation — exactly the command the modify-mode advisory notice suggests — while preserving the add, list, and remove flag verbs verbatim as the automation contract.

## Outcome

Landed as `353ea7585a` with the review disposition follow-up in `4df00869d6`. Review verdict: every functional, safety, and architectural axis passed; the one blocking finding — a plan-step identifier embedded in a test docstring, breaching the code-stands-alone boundary — was reworded onto behaviour and landed. Nine real-behaviour tests over real encrypted storage: seed two, edit, count-shrink clears the orphaned index on read-back; adoption refusal live on the door; childless seeds empty; non-descendant facts untouched; the flag verbs survive the callback change. Conformance 501 green.

## Notes

- The plan row's "repair" clause is INAPPLICABLE, verified twice (executor and reviewer): the repair surface is entirely non-interactive diagnostics with no prompt loop and no descendant concern — recorded here rather than silently skipped. Likewise no bespoke prompt loop existed in the descendiente file; the door is additive over the preserved flag grammar.
- Review medium, ledger-bound: the door (like the pre-existing flag verbs) carries no entity-type guard, so a legal-entity profile can open the descendant editor and write facts that are INERT for its modelo set (the mínimo-por-descendientes bindings exist only on the renta-personal snapshot — traced, not assumed). Follow-up: an applicability advisory at the descendiente entry for non-natural-person profiles, door and flag verbs alike.
- Review lows, ledger-bound: the two-line commit-composition restatement and the capability-dispatch restatement are documented drift surfaces (a shared helper would erase both cheaply); the preserved flag-verb path clears one aggregate fewer than the canonical clearing helper (pre-existing divergence — the flag path should adopt the helper); a composed create-edit-reopen door round-trip assertion would lock the re-seed behaviour.
- The reviewer's working-tree scope note alleging an active rename sweep was verified FALSE against the tree (all named files clean, tokens intact) — the commit-anchored findings stand; the hallucinated scope claim is recorded as an instance of the verify-every-finding discipline.
