---
tags:
  - '#exec'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-07-26'
body_hash: 'sha256:5ddae766d1d45959b961c051b0a9903e978d1ca0d0dadd24e8f09f35b5901651'
step_id: 'S03'
related:
  - "[[2026-07-25-code-dedup-sweep-plan]]"
---

# Add the structural AST gate refusing an inequality comparison of schema_version on a persisted inner-envelope read path, alias-aware rather than name-matching, shipping with a planted-violation anti-tautology proof modelled on commit a5d21ced8a

## Scope

- `src/cadrumo/adapters/persistence/storage/tests/`

## Description

A structural gate refusing an inequality comparison on a persisted inner-envelope
read path, alias-aware rather than name-matching, shipping with a
planted-violation proof.

## Outcome

Delivered by a peer agent as
`storage/tests/test_inner_envelope_version_check_shape.py`. Verified at HEAD.

It meets the standard the ruling demanded, which was not a formality: this
campaign's own critical finding was two structural gates reporting green against
violations they could not see. This one carries planted-violation proofs for the
exact pre-change spelling, an aliased envelope handle and a reversed comparison;
out-of-scope guards proving it did not widen reach; a relative-import resolution
test; and an anti-vacuity test asserting the governed surface is not empty — the
last being what stops the gate passing by scanning nothing.

## Notes

Semantic search was unavailable when the governing ruling was authored and was
re-validated before this verification pass: the code index had recovered to
68,502 chunks against 3,671 tracked source files, and two semantically unrelated
probes returned disjoint correct owners. The site-level claims here nonetheless
rest on `rg` and direct reads, not on the index.
