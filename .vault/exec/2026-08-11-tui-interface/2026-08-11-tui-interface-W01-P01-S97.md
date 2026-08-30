---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:00aa815f5cd9c4fd1c407b7bb7c7cd91e8f7b99a245a8197cc08d58f4a2a2ca9'
step_id: 'S97'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Flip the two step-notation scan patterns to production scope and extend the production scan from docstrings to comments, in the gate that already owns this rule rather than building a second detector. The pattern table production-scopes only the vault-path and dated-stem cases; the W##.P##.S## and P##.S## cases stay test-scoped, and the production scan builds docstring ranges only, which is why a comment carrying a full plan address survives with the gate green. Measurement backing the flip: W##.P##.S## hits exactly ONE production module across 1953, zero false positives, and the shipped 'the W3C standard' near-miss control already discriminates. Do NOT flip bare S-digit in the same change: it hits 68 files of which 55 are the file-level '# ruff: noqa: S106' form the stripper misses because its pattern requires noqa to follow the hash directly. Fix that form, re-measure, flip separately. Mutation-prove each flip by adding an identifier to a production module and confirming the gate reds

## Scope

- `dev/tests/_marker_metadata_patterns.py and dev/tests/test_marker_integrity.py`

## Changes

- `M` `dev/tests/_marker_metadata_patterns.py`
- `M` `dev/tests/test_marker_integrity.py`
- `verify:` `pytest dev/tests/test_marker_integrity.py::test_production_source_does_not_cite_dated_vault_documents -n0` -> `1 passed`

## Notes

Both halves delivered. The step-notation cases are production-scoped in the
pattern table, and the single scan mechanism inspects
`token.type == tokenize.COMMENT` as well as strings inside docstring ranges,
so a comment carrying a plan address is now caught in production source. No
second detector was built: the production-scoped subset is DERIVED from the
one table at `_marker_metadata_patterns.py:229`.

A STALE DOCSTRING WAS FOUND AND FIXED IN THE SAME CHANGE. The production
gate's docstring still read "every other pattern in the table stays
test-scoped; this check is the dated-document-stem family only", which the
flip had made false. It was worse than the two patterns this Step flipped:
FOUR entries carry production scope (`:80`, `:88`, `:162`, `:189`), all
flowing through the same derivation.

The replacement states that the gate enforces every family the table marks
production-scoped, names the step-notation families as having joined once
their sweep completed, and records that the set is DERIVED from the table so
a family added there is enforced without touching the test. That last clause
is what stops it going stale again: the previous docstring restated a set the
code derives, so it could only ever drift out of agreement with it.

A gate whose prose understates its own reach is not a cosmetic defect -- a
reader deciding whether a pattern is enforced would have consulted the
docstring and got the wrong answer while the gate was green.
