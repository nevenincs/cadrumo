---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:903a39e3b54bc7666e13b1a0197570a76dd06045686941b51516be28833f4f06'
step_id: 'S13'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Re-sequence SETUP_FLOW sections into the eight-phase spine order with stable question ids, keeping both core registration slots fed and visible_when targets resolving to earlier questions

## Scope

- `src/cadrumo/application/wizard/_catalogue.py`

## Description

- Re-sequence `SETUP_FLOW` from eleven sections into the eight-phase
  spine order: identidad, residence, actividad, iva, enrollment,
  familia, obligations, preferencias - every question literal, id,
  profile key, gate, and translation key byte-stable (surgical
  extraction and regrouping).
- Seat `taxation-type` at the head of familia: the spouse block's
  visibility gates on it, so the ADR's original preferencias placement
  would have broken the earlier-question invariant (ADR amended in
  place with the rationale).
- Add four new section title keys in all four catalogues via the
  locales CLI (`scaffold` then `set`); old question-key namespaces stay
  live because the tr keys were deliberately kept stable.
- Re-sequence the two scripted runtime answer deques (individual +
  joint) to the new order.

## Outcome

Committed as `f7a80af114` (explicit pathspec). Wizard suite 233/233,
documented-command conformance 348/348, setup-answers 16/16, repo-wide
locale parity 33/33 (green again: the scaffold pass aligned the
substrate's flows.* keys as placeholders).

## Notes

The flows.* placeholder values await real translations from the
coordinator's locale executor; three flows.* placeholder-mismatch
warnings in scaffold --check are that stream's to clear. The flow
constructs at import, which re-proves every visible_when target
resolves to an earlier question under the new order.
