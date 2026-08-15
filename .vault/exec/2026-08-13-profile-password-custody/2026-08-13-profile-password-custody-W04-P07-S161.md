---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:9893664182085736463369acd8bbbd612570c2db36818f5e7b00758f6b40acfc'
step_id: 'S161'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium state the boundary the persisted-format discriminator currently lacks, ruling whether a versioned shape nested inside a persisted record is itself a format, since the question has now arrived three times from different directions and each was answered locally, and the answer decides whether the custody hold evidence and the legal-hold and retention snapshots enrol or stay out

## Scope

- `src/cadrumo/core/compatibility_lifecycle.py`

## Description

- Read `compatibility_lifecycle.py` whole, the persisted-format enrolment gate,
  and the binding gate, then trace the three prior local answers to this
  question through their exec records: the independent-version discriminator
  argued for the profile-capsule formats and the profile record, its
  application to four taxpayer registers previously excused as living inside
  an enrolled container, and its distinct duplicate-declaration corollary
  argued for the bundle and fincas schema-version literals.
- Read the three named candidates' source (`_custody_hold_models.py`,
  `_custody_hold.py`, `_profile_legal_hold.py`, `_profile_filing_retention.py`)
  to determine, for each, whether its own bytes are durably written and read
  back through its own grammar, independent of any container.
- State the boundary as a documented two-part conjunctive test (independent
  grammar; durable readback of the shape's own bytes) on `compatibility_lifecycle.py`,
  immediately above `PersistedFormatClass`, and apply it to the three
  candidates.
- Fix a stale entry the grounding pass surfaced: an already-retired record
  class remained enrolled in the persisted-format literal-inventory gate's
  table and its anti-tautology synthetic fixture.
- Run the compatibility-lifecycle and persisted-format enrolment gates to
  confirm the discriminator addition and the stale-entry fix are both green.
- Persist the ruling as an ADR and this record.

## Outcome

The boundary was never stated because three local answers had actually
answered two different questions without anyone naming the split. The first
two answers argued, correctly, that a container's floor does not cover a
grammar living inside it, so an independently-versioned nested shape earns
its own inventory entry — this is what enrolled the three profile-capsule
formats, the profile record, and (on a later pass, self-correcting an earlier
exclusion) four taxpayer registers. The third pair of answers were solving a
different problem wearing the same clothes: two literals both claiming to
state ONE format's current version, resolved by asking which declaration is
actually exercised on the live write path rather than by an a-priori
domain-versus-persistence layering preference. Treated as one question, each
new candidate had to be re-argued by analogy; split into two, each is a small,
separately-answerable test.

**The stated boundary is a two-part conjunctive test**, recorded in
`compatibility_lifecycle.py` immediately above `PersistedFormatClass`:

1. Independent grammar — the shape declares a version distinct from any
   enclosing container's or envelope's, such that the container's floor does
   not cover it. Two declarations that never diverge state one format's
   version twice, not two formats; the surviving declaration is owned by
   whichever side is live on the write path.
2. Durable readback — the shape's own bytes, not a digest or a derived
   boolean, are themselves durably written and meant to be parsed back
   through that grammar. A shape that only folds a digest into another
   persisted structure has nothing on disk this inventory must guarantee
   readable. A shape that is durably written but always recomputed fresh from
   an already-durable source, never trusted on read, still enrols, but that
   fact argues for `REGENERABLE` over `DURABLE` downstream.

**Applied to the three named candidates, all three enrol, for two different
reasons.** The legal-hold case snapshot and the filing-retention snapshot each
declare an independent `schema_version`, are each their own file, and are each
loaded back through `model_validate_json` on every hold projection or
assessment — both parts hold cleanly. The custody hold evidence
(`ProfileCustodyHoldEvidence`) also declares an independent `schema_version`
and is durably written to its own per-owner file, so it clears both parts in
the loose sense — but nothing in the tree ever loads that file back through
its typed grammar; `refresh()` unconditionally recomputes it from the
legal-hold and filing-retention snapshots and overwrites the file every call.
That is the participation-index shape exactly: a derived, always-recomputed
read-side artefact for which delete-and-rebuild is the correct response to an
unreadable version. It enrols, but the note is left for the classifying row
that the evidence points at `REGENERABLE`, not `DURABLE`.

No candidate stays out. The value delivered is the two-part reason each can
now cite instead of re-deriving format-hood from proximity to its neighbours.

The ruling did not enrol any of the three candidates into `PERSISTED_FORMATS`
or the binding gate's tables, and did not touch `COMPATIBILITY_REGIME` or its
enforcing gates; that remains downstream work.

Verified: `pytest src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py
src/cadrumo/core/tests/test_compatibility_lifecycle.py
src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py
src/cadrumo/tests/test_persisted_format_enrollment.py
src/cadrumo/tests/test_persisted_version_literal_inventory.py` — 46 passed.

## Notes

**A stale entry was found and fixed, one file outside this Step's named
scope but load-bearing for its own gates.** `tests/test_persisted_version_literal_inventory.py`
still enrolled an already-retired record class
(`BucketManifest`, deleted by a peer's manifest-retirement work) in its
`VERSIONED_RECORDS` table and its anti-tautology synthetic fixture — the exact
"a key outliving its implementation" failure the binding gate exists to catch,
recurring one file over from where that gate lives. The stale table entry and
the two synthetic fixtures naming it were retired together with the format,
and the fixtures repointed at `PersistedProfileSession`, a still-enrolled
class with the identical no-default shape the anti-tautology proof needs. A
stale docstring line claiming the manifest lineage probes still exercise
`BUCKET_MANIFEST_SCHEMA_VERSION + 1` was also corrected, since it made a
false present-tense claim about deleted code.

**A second, larger regression from the same manifest retirement was found and
left unfixed, reported here rather than absorbed.**
`entrypoints/cli/tests/test_active_profile_env_override_name.py` still
constructs `BucketManifest` and calls `write_manifest` inside a helper
(`_write_second_live_bucket_sharing_label`) reached from a deferred,
function-local import a collection-only run cannot see — so it currently
fails at test-run time, not at collection. Fixing it correctly needs the
replacement mechanism for simulating a torn/duplicate-label bucket state under
the new custody capsule discovery marker (`profile_capsule_commit`), which is
outside both this Step's scope and this record's ownership boundary
(`adapters/persistence/storage/**`); it is reported to the team lead rather
than patched here.

No mocks, stubs, skips, or tautological tests were added. The two synthetic
fixtures proving the literal-inventory detector still discriminate were
re-pointed, not weakened — one still asserts the detector fires on a literal,
the other still asserts it stays silent on the bound form.
