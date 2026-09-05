---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:40bb4dda45cc94340ae18fd6c6f2200f515c2b20395a040ce89dcb206fb431a7'
step_id: 'S434'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Read the casilla label pins from the compiled adjudication authorities instead of their TOML. The unique cohort's ledger does not serialise official_label_sha256 at all -- its compiler derives the digest from the record-design intermediate and the semantic map at compile time -- so a gate parsing raw TOML found nothing to assert for that whole cohort and reported itself green. Reading the compiled authority is what the registry authority flow requires and is what makes the assertion cover those casillas.

## Scope

- `dev/locales/tests/test_casilla_label_matches_pinned_official_text.py`

## Changes

Task A was going to be "write 66 adjudication entries". It turned out most of
that work already existed and my own gate could not see it.

The unique-cohort compiler already computes official_label_sha256 for all 36 of
its members, from the record-design intermediate and the semantic map. It simply
never serialises the field, and its TOML carries casilla_id, export_field_id,
profile and column only. My gate parsed that TOML, so for that entire cohort it
found no pin, skipped every row, and still reported itself green -- the exact
shape the registry authority flow warns about: raw TOML inspection diagnoses a
declaration, it does not establish compiled behaviour.

Reading the compiled authorities instead took the gate from 117 covered
casillas to 143, with no ledger written and no new entry authored.

The result that matters more is what those pins say. For all 26 unique-cohort
casillas that carry a shipped label, the compiler's independently computed pin
equals the label -- 26 of 26, zero differences. That is corroboration of the
S431 work from a path that shares nothing with it: I derived those labels by
unique occurrence in the design, while the compiler resolves them through the
export field id, the semantic map and the design IR. Two unrelated routes to the
same string is better evidence than either alone.

Teeth on a casilla only the rewrite can see: 00814's label changed from "Gastos
de investigacion y desarrollo del periodo impositivo" to "Gastos de innovacion
tecnologica del periodo impositivo" -- the sibling column of the same official
row, and a casilla the previous TOML-reading gate had no pin for at all. The
gate failed. Restored by copy; 6 passed including the cohort's own compiler
tests.

## Notes

156 pins are now available and 143 are asserted; the 13 unasserted ones are
pinned casillas that are still unlabelled, and they sit inside the 16 the next
tasks address.

STILL OUTSTANDING for Task A: the 38 casillas grounded in S432 and 2 from S431
belong to no adjudication cohort at all, so nothing pins them. Those need a new
cohort compiler in the established pattern rather than an appended entry, which
is the next unit of this task.
