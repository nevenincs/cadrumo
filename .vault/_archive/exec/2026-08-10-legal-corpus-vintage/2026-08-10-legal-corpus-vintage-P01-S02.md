---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:ebb17bf22180fcaef772af60495aa1f0a5b810a6fd9f39965a3ee1793f1ad2a3'
step_id: 'S02'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---

# Prove the new clause bites and prove it does not over-reach in the same row. The refusal must fire on a document containing a forbidden phrase, and the CONTROL that decides closure is that every one of the 606 existing entries still loads unchanged, with the deliberately vintaged excerpts named explicitly because they legitimately contain text current law does not. Do not close on the refusal firing

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Add a synthetic-fixture test proving the refusal fires when a document still carries the declared forbidden phrase.
- Add a synthetic-fixture test proving the clause does not over-reach: a declared forbidden phrase genuinely absent from the corpus passes cleanly.
- Add a test proving the two clauses' failure messages stay distinct (a missing-required-text refusal never claims "contains forbidden text" and vice versa).
- Add schema-level tests for the new field's own validators (blank entry, duplicate entries, overlap with `required_text`).
- Add the closing CONTROL: load the full committed legal catalogue, assert the five deliberately year-vintaged excerpts (`ley-35-2006:art-23-2021`, `art-52-2015`, `art-52-2021`, `art-66-2021`, `art-68-2018`) remain present and carry no `forbidden_text`, then run `verify_legal_catalogue` over every entry and confirm it still validates unchanged.

## Outcome

Seven new tests, all green: three prove the refusal fires and distinguishes itself from the required-text refusal, three exercise the field's own schema validators, and one is the CONTROL — the full committed legal catalogue (623 entries at time of writing, exceeding the 606 measured in the grounding reference) still loads and validates unchanged with the new optional clause, with the five deliberately vintaged excerpts named explicitly and confirmed to carry no `forbidden_text`. Closure rests on the control, not on the refusal firing.

## Notes

The catalogue population has grown from 606 (grounding-reference measurement time) to 623 by the time this Step ran, from unrelated concurrent registry authoring; the control asserts the property (every entry still validates) rather than an exact count, per the project's prohibition on hardcoded counts as pass conditions.
