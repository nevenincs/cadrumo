---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:121c430bde2d4c5b21c9166fb9c22524d284094fd492c0f0485f29c96c2509d8'
step_id: 'S124'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Move the remaining three custody records onto the digest base, each with its digest proved unchanged, the envelope and recovery envelope and capsule commit still hand-rolling the computation

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/custody/records.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule_records.py`
- `verify:` all three digest-format checks probed against the canonical on 6 inputs -- identical on every one
- `verify:` `pytest storage/tests -k "custody or capsule or digest or envelope" -n 0 -m ""` -> 39 pass, 1 pre-existing

## Notes

The move the step names is already done: the envelope, the recovery envelope and
the capsule commit all extend `CustodyDigestModel`, as does the recovery
artifact. The digests are proved unchanged by the roundtrip suite rather than by
a fresh proof, since the move landed earlier in the campaign.

`ProfileCustodyCapsuleLabel` stays off the base, correctly -- it chains two
digests, computing one over a payload that already contains another, which the
base's single-digest shape cannot express.

What remained was a different duplication in the same files: the digest-STRING
format check, written three ways. `recovery.py` and `recovery_artifact.py` call
the canonical `validate_prefixed_digest`; `records.py` had a rival regex
implementation; `capsule_records.py` inlined the length, prefix and alphabet
checks by hand -- while ALREADY IMPORTING the canonical at the top of the file.
That last one is the sharpest version of this campaign's shape: the canonical was
in scope and the check was written out anyway.

Probed all three against the canonical before collapsing them, on six inputs
including uppercase hex and a wrong length. Identical on every one, so the
collapse changes nothing but the number of places the rule lives.

### A regression this found, and did not re-baseline

`test_inner_envelope_vacuity_invariants` fails at `assert 15 >= 16`: one read
path has stopped calling `inner_envelope_version_is_current`. It is NOT this
change -- neither file mentions that predicate and the diff contains zero
references -- and the gate's own docstring is explicit about what to do:
"Lowering this floor is only ever legitimate alongside evidence that the missing
calls moved into a shared reader. A drop with no such consolidation is the
regression this gate exists to catch: verify before re-baselining, never the
reverse."

So it is left red. Fifteen call sites across thirteen files, listed by a scan
run for this purpose; the shared kernel in `profile/_secure_enveloped_document.py`
is still among them, so the loss is one of the individual readers rather than the
inherited check.

Worth recording how nearly I mis-reported it: the first scan output was piped
through `tail` and the kernel fell off the visible list, which read exactly like
the kernel having lost its call. A truncated list of members is not a
measurement of the population.
