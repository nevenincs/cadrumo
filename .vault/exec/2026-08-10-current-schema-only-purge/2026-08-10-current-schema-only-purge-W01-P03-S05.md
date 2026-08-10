---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:30308da934606f0ed2ab4a12cb02c2c915f888d9bc814703755eaabf05e0b1e5'
step_id: 'S05'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Prove current BucketPointer round trips and non-current marker refusal

## Scope

- `src/cadrumo/core/tests/test_bucket_pointer.py`

## Description

- Prove the declared constant and the type-level pin agree, so the constant
  cannot drift from the constraint it names.
- Prove a non-current version refuses, parameterised across older and newer.
- Prove a document omitting the version key refuses.
- Prove the current document round trips through serialisation unchanged.
- Prove that deleting the version line from a written file surfaces at read.

## Outcome

Landed in `aa52757` alongside the production change.

The anti-tautology proof is the load-bearing one: a real pointer file is written
through the production writer, its bytes are edited on disk to remove the version
line, and the read path is asserted to refuse. Without that, every refusal test
in the file could pass while the boundary silently re-defaulted, because a
constructor-level refusal says nothing about what happens to a file that reaches
the parser.

A test asserting the constant equals the enforced literal guards a specific
decay: the constant is documentation and the literal is the enforcement, and
nothing but a test keeps a later edit from advancing one without the other.

## Notes

The pre-existing invalid-constructor-fields test lost its zero-version case,
which the parameterised non-current test now covers more directly. Recorded so a
reader diffing the file does not read the removal as lost coverage.

Real files under a temporary directory throughout; no mocks and no monkeypatching
of the parser. Verified at HEAD independently rather than on the implementer's
report.
