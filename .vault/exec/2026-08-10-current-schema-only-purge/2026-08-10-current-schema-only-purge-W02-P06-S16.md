---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:2d0dcffd535397ae1487f1cfbf1e981ad1a14f6abc8008a0a9b4ca3f4daf76cd'
step_id: 'S16'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Require the exact current KdfParameters version marker

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`

## Description

No code was written for this step. The requirement was found already satisfied at HEAD and
was verified rather than re-implemented.

- Resolve the row's referent: read the version-gate model, the record model, and every
  consumer of the record's JSON parse.
- Confirm the read path requires the marker before strict parsing, and refuses a marker that
  is not the current one.
- Enumerate every construction site of the record to establish whether the model's own
  default is reachable from a file on disk.
- Confirm the comparison is made against the on-disk parameter-shape constant and not the
  Argon2 algorithm version.

## Outcome

Delivered as specified, by prior work. The governing decision requires that the KDF parameter
record "requires its current marker on every read and writes it on every write". Both halves
hold at HEAD.

**Read.** `_KdfVersionEnvelope` in the scoped module declares `version` with no default, so a
document carrying no version fails the preview. Its docstring records the defect that produced
it: while the field defaulted to absent, a file with no version satisfied the preview and
reached the comparison with an absent marker standing in for a real claim. The provider's
unwrap path parses that envelope **before** strict parsing and raises a typed,
runbook-pointing version error naming both the on-disk value and the expected one.

**Write.** Both the mint and the recovery paths construct the record and serialise it, so the
marker reaches disk on every write.

**The observation that decides the step, and the reason it is recorded here rather than left
implicit.** The record model's `version` field carries a default. That default is **not a live
read-tolerance on the production path**: the record's JSON parse has exactly one production
consumer, and it sits immediately after the version gate, so a version-less document is
refused before the default could ever apply. There is no second door. The default is reachable
only because both writers omit the argument — it is constructor convenience, not tolerance.
This step therefore closes over a hole that an upstream gate already shuts.

**The trap this row carried was avoided by whoever did the work.** Two constants sit one word
apart: the on-disk parameter-shape version and the Argon2 algorithm version. Gating against the
wrong one would refuse every document this build writes, including the positive round trip that
would otherwise catch it. The comparison uses the parameter-shape constant, which is correct,
and a sibling module in the profile-bundle boundary carries an explicit comment distinguishing
the two for its own record type.

## Notes

**The default does not stay, and it moves to the step that owns the writer.** A silent default
would make a future second consumer tolerant, in a plan whose purpose is removing
read-tolerance. Removing it here would break provisioning immediately, because every writer
relies on it. Scope for its removal has been added to the next step, which owns the mint and
recovery paths, so writer-explicit and default-removal land as one change. That is the only
safe order.

**Precondition for that step, measured here: there are five construction sites, not two, and
none passes the marker explicitly.** Two are production (mint, recovery); three are in the
record's own salt-validation tests.

**And two of those three would pass for the wrong reason.** They assert a salt refusal by
constructing the record inside an expected-validation-error block. Remove the default and they
still raise — on the missing version, before the salt validator is ever reached — so two
salt-validation tests would silently become version-validation tests while keeping their names,
their assertions and their green. Anyone landing the removal must supply the marker at all five
sites, not merely at the two that would fail loudly.

**A separate defect, in the step that exists to prove this behaviour.** The file-fallback test
asserts the written marker equals the record model's own field default. That comparison cannot
fail: it checks the written value against the thing that produced it, so a wrong default, a
wrong marker, or the Argon2-version confusion all still pass. It is a tautology inside the
module whose job is proving the marker is right, and the governing decision asks for the
opposite — an anti-tautology proof that mutates the stored payload to remove the field and
asserts refusal on reload. That work belongs to the proof step and is recorded here so the step
is not closed by making the tautology pass.
