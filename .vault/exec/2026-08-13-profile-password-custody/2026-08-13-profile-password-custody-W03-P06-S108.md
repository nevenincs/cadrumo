---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:8cfebcec6140dafdec614ff5e39b1ec9c5029588d57ab647d53e56805912edc6'
step_id: 'S108'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh re-found the label ambiguity refusal test on the custody label authority rather than retire it, since the refusal itself was restored as real operator-facing work and is live, while only the test's mechanism is stale in manufacturing two casefold-equal labels by rewriting the retired plaintext bucket manifest, and the restored refusal already ships five tests that manufacture the same collision correctly

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_profile_label_ambiguity_refusal.py`

## Description

- Establish what the module's subject actually is before replacing its fixture.
- Author a named corruption fixture in the capsule test-support home that forges
  the colliding state the way the service's own transaction would.
- Keep the assertions at the CLI surface the module exists to test.

## Outcome

The module is re-founded on the current authority and its subject is intact. Two
of its three tests pass; the third fails for a reason that belongs to another
open step.

The row's own premise was wrong and the correction is the useful part. It
directed copying the setup from the restored duplicate-label refusal, on the
assumption that those tests manufacture the same collision. They do not: they
register ONE profile and assert that creating a second with a casefold-equal
label is refused. That is the WRITE-side refusal which prevents the collision;
this module tests the READ-side backstop for when the collision already exists
on disk. Opposite sides of one guard, so there was no setup to copy, and the
mechanism cost more than the row assumed.

That is also why the old test forged the state at all. Every label writer --
creation and rename alike -- routes through the same casefolded duplicate check
under the custody-root lock, so no supported path produces two colliding
committed labels. **A backstop against a state every writer prevents cannot be
tested without forging it.** The old module reached for the plaintext manifest
to do so; what changed is the authority, not the necessity.

The forging now lives in a named fixture in the capsule test-support module,
where the other capsule helpers already live, rather than being open-coded in an
entrypoint test reaching into storage internals. Its docstring opens by stating
that no supported path produces the state and why, so a later reader cannot take
its existence as evidence the collision is reachable through an operator action.

The fixture mirrors the service's own rename transaction -- advance the durable
lineage head, replace the committed label record against its expected digest,
re-verify the head -- omitting only the duplicate refusal. Preserving that order
is what makes the forged state coherent rather than merely damaged: the label
record and its verification head still agree afterwards, which is precisely the
state a reader must disambiguate. Randomly corrupted bytes would exercise a
different failure and prove nothing about this backstop.

One deviation is deliberate and documented in the fixture: the service wraps the
sequence in the custody-root transaction lock and the fixture does not. A test
forging a state has no concurrent writer to exclude, and that lock is not on the
custody package's public facade, so taking it would have meant reaching past the
facade for something the test does not need. Every other symbol used is
exported.

## Notes

The remaining failure is `No such command 'delete'`, verified by running the
module: `config profile delete` is one of the seventeen command subtrees that
resolve to nothing today, which is owned by the open subtree step. It will clear
when that step lands, with no further work here.

Recording it rather than absorbing it, because a step closed while one of its
tests still fails needs the dependency named -- otherwise the next reader cannot
tell a deferred carry-forward from an unnoticed regression.

That failure is also evidence for the step that owns it. The unresolved subtrees
were argued from a schema-coverage crash and an MCP module's failures; here one
of them breaks a freshly re-founded entrypoint test as well, so the cost of
leaving them unresolved is wider than the surface where it was first measured.
