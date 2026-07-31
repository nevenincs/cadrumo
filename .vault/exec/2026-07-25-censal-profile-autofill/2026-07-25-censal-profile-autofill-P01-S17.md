---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:4d4e757e1d11bed5146f952c5ac0fe04095d8e66b684b367a50b92f37bb36543'
step_id: 'S17'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Declare the renta sex fields with the value set the AEAT registro design defines, and anchor the provenance contract at the schema rather than at a consuming module

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`

## Description

- Probe whether the declared sex enum is enforced at all before assuming the divergence bites, finding it is not.
- Settle which authority is right by reading the bundled AEAT registro design, which types the field and enumerates its two values.
- Declare both sex fields with the value set AEAT defines, rather than translating between the two spellings.
- Confirm nothing in the tree writes the numeric form, so the change moves no persisted value.
- Pin the schema against the runtime enum by set equality, and pin the runtime enum against the documented pair so the two cannot drift together and stay green.
- Anchor the provenance contract at the schema instead of at a consuming module, and check the outer-layer token in its own layer.
- Promote the schema accessor to the domain package facade, so the outer-layer check reaches a public surface rather than a private module.

## Outcome

Three tests in `src/cadrumo/domain/user_profile/tests/test_renta_code_schema_alignment.py`, and the provenance contract split across a domain half and an application half.

`uv run --no-sync pytest` over the profile domain, the wizard and the core tests reported `2 failed, 818 passed in 101.63s`. Both failures are other campaigns' surfaces: a censal consulta URL literal in a manager test, and year-qualified period tokens in a docs sequence fixture. Neither names a file touched here.

`uv run --no-sync pytest` over the profile domain and the new application check reported `94 passed in 22.42s`.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` reported `All checks passed!`, and the import gate names neither contract file.

## Notes

The declared enum turned out to bind nothing: a probe wrote an arbitrary token to the sex field through the real store and it was accepted and read back unchanged. So the divergence had no runtime consequence and was never going to surface as a failure, which is why it survived. The same is true of every enum the schema declares, not only this field; that is the wider hole and it is recorded as its own finding rather than widened into this Step.

Correcting the enum was therefore a documentation fix with a test behind it, not a behaviour change. Nothing writes the numeric spelling, so no persisted value moves and no operator sees a difference today.

The right home for enum enforcement is the validation service, which already enforces the date type and receives its schema by injection. That matters: the injected schema is why enum enforcement would not repeat the coupling that made path validation on the carrier untenable.

Switching the domain contract test to the neighbouring package's public facade would have satisfied the import linter while leaving domain depending on application. Anchoring on the schema removes the dependency rather than hiding it, and the accessor promotion was needed because the first attempt swapped one ownership violation for another.

A commit attempt aborted on its own guard when peers staged files between the check and the commit, and a later attempt lost the index lock to a concurrent commit. Both are ordinary contention in this worktree; the guard behaved as intended and the lock cleared without intervention.
