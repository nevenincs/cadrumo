---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:8ec4eab732aabc7fc4c5d374b2e774edf08562c36bfff37df5fa18a2cb1daaab'
step_id: 'S20'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Decide the profile-create prompted-question inventory contract: fix the exact set and count of questions the wizard surfaces on the payload and record the rationale as an ADR-lite decision note in the plan

## Scope

- `src/cadrumo/application/wizard/_catalogue.py`

## Description

- Enumerate the declared question inventory of the `SETUP_FLOW` wizard flow (the
  flow both `create` and `edit` walk) from `application/wizard/_catalogue.py`.
- Confirm the payload-surfaced set matches production: `create` writes
  `supplied_question_ids = frozenset(question.id for section in flow.sections for
  question in section.questions)` in `application/wizard/_commands.py`.
- Fix the contract at the full declared inventory and record the rationale as a
  decision note in the plan's `P07` phase.

## Outcome

The pinned profile-create prompted-question contract is the full declared inventory
of `SETUP_FLOW`: 76 questions across 11 sections (taxpayer-type 9, profile 9,
taxpayer 7, spouse 9, family 2, iva 8, enrollment 2, obligations 21, residence 5,
capabilities 3, notes 1), every id unique. This is exactly the `supplied_question_ids`
frozenset `create` writes to the payload, so it is the questions the wizard surfaces
on the payload — not a conditional per-answer visible subset (a natural person sees
roughly 44 of the 76; a legal entity a different subset).

Pinning the full declared set rather than a visibility subset makes the gate
deterministic and path-independent: a silent add or drop of any question definition
fails loudly, and asserting the id set alongside the count also catches a same-size
rename swap. Conditional per-answer visibility stays covered by the existing
interactive persisted-fact test. The decision and its rationale are recorded in the
plan `P07` phase prose; the enforcing assertion is implemented under `P07.S21`.

## Notes

Decision-only step; no production code changed. The count is intentionally enforced
by one test (`P07.S21`) rather than duplicated as a literal in the catalogue, so the
catalogue stays the single source of the inventory and a legitimate change updates the
pinned set in exactly one place.
