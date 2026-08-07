---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0c96ea6291ed1deb601da5e5e1147e84b13a92d6f5ba5674d241015c839dade6'
step_id: 'S33'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Run the mutation-proof pass over every W01 through W03 gate, breaking from outside the repo, observing red, restoring, and recording each red signature

## Scope

- `src/cadrumo`

## Description

- Enumerate the eleven delivered W01-W03 gate files from the tree rather than
  from plan row status, which has drifted from delivery in both directions.
- Take a baseline run of all eleven together before mutating anything.
- Apply sixteen mutations, one at a time, each from a throwaway plugin on
  `PYTHONPATH` **outside** the repository. Nothing under `src` was edited at any
  point, so no peer sweep could commit a mutation and no crash could leave
  residue.
- Record, for each mutation, the set difference against the baseline failure set
  rather than a pass/fail or a count.
- Re-run the full set with the mutations removed to confirm restoration.

## Outcome

**Counts are not the signal; set differences are.** The first mutation returned
*fewer* total failures than the baseline, which read as an improvement and was
nothing of the kind: sixteen unrelated reds in a concurrently-edited file had
resolved between the two runs. Every result below is therefore the set of tests
that were green at baseline and red under the mutation. Reading the totals would
have inverted the conclusion on the first result and quietly corrupted the rest.

**Eleven gates bite, each with a precise blast radius.** Every entry names the
mutation and the tests that newly reddened:

- *FieldOrigin* member dropped from the closed set: **4** - three enum tests
  (member set, and the dropped member's token and hydration parametrisations)
  plus one provenance test, which validates an origin field and legitimately
  depends on the enum.
- *FieldRole* stored token altered: **3** - the token and hydration
  parametrisations for the altered member, plus the importer hydration for the
  same column.
- Importer column with no role member: **1** - the column-resolves-to-a-role
  parametrisation for exactly that column.
- Importer denominator emptied: **1** - the vacuity guard, and see below.
- Transcription serialization refusal removed, both mechanisms: **2** - the
  dedicated tripwire and the restored-from-cache tripwire.
- Anchor validator neutralised: **1** - the anchored-field-must-show-its-anchor
  test.
- Ambiguity validator neutralised: **1** - the
  ambiguous-field-must-record-candidates test.
- One payload field excluded from the projection: **1**, and it is the
  interesting one; see below.
- Dialect reader normalising printed decimals: **6**, spanning three files.
- Projection stripping cell whitespace: **3** byte-equality tests.
- Page order reversed: **6** reading-order and printed-form tests.
- Decimal comma normalised in the transcription: **6**, including the
  no-normalised-form-is-introduced assertion.
- Mapping lane ordered first: **2** ordering tests.

**The projection-parity mutation earns its billing.** Marking one payload field
excluded leaves it declared and typed, so both structural tests -- every draft
field has a home, and the payload invents nothing -- stay green **correctly**,
while only the value-survival test reds. That is a direct demonstration that the
structural and value tests do different work, and that neither substitutes for
the other. A field-name comparison alone would have passed over a projection
that silently emitted nothing.

**The emptied denominator shows why its guard exists.** With both importer
column sets emptied, the coverage assertion passes over nothing, the
per-column parametrisation reports *"got empty parameter set"* and **SKIPS**,
and only the dedicated populated-set guard fails: one failure against two passes
and a skip. Without that guard the run reads green over an empty world. A
skipped test and a passing test are indistinguishable in a summary line.

**Two gates are defence-in-depth, which a single-mechanism mutation hides.**
Removing the transcription's `model_dump` and `model_dump_json` overrides
produced **no** red on the dedicated tripwire test, because the registered model
serializer still refused underneath. That reads exactly like a vacuous gate and
is the opposite: the hole stayed shut. Only after removing both mechanisms did
the tripwire red. A mutation that fails to open the hole proves nothing about
the gate, and the distinction is invisible without deliberately escalating.

## Verification

Baseline, all eleven gates, sequential, no marker filter and nothing deselected:

    uv run --no-sync pytest <11 gate files> -p no:randomly -n 0 -q
    19 failed, 190 passed in 100.06s (0:01:40)

After the pass, with every mutation removed and nothing under `src` changed:

    uv run --no-sync pytest <11 gate files> -p no:randomly -n 0 -q
    3 failed, 206 passed in 33.00s

Restoration is confirmed by that run and by a clean working tree across every
file touched by a mutation. The drop from nineteen to three is not an effect of
this Step: sixteen of the baseline failures were transient reds in one
concurrently-edited file, which its owning lane resolved while the pass ran.

## Notes

**Three gates were already red at baseline, on genuine landed drift, and stayed
red throughout.** They were recorded and not patched. These are the pass's most
valuable output, because the tree supplied the mutation itself:

- The role enum gained two bank-movement members in a later commit than the one
  that last touched its closed-set gate, so the gate's declared-token map never
  learned them. The gate has been red since that commit, doing exactly what a
  closed-set gate is for.
- An importer declares a column in English while the role enum declares the same
  concept under its Spanish stem, so the column resolves to no member. The
  coverage gate catches it. This is a naming-rule violation, not merely a
  coverage gap, and the open Step that consumes the mapping lane from that
  importer owns it.
- The same mismatch surfaces a third time through a downstream contract test.

**Two mutations were retired as unsound rather than reported as findings.**
Deleting an enum member crashed production import and reddened by collection
error, which proves far less than a targeted red; it was replaced by altering a
stored token. Reassigning a pydantic `model_validator` attribute is a silent
no-op, because the validator body is compiled into the model's core schema at
class build -- two validator gates initially looked like they did not bite, and
both bit once the mutation was applied to the module source in memory instead.
A clean run under an ineffective mutation is not evidence about the gate.

**One mutation was inert and is recorded as such.** Collapsing whitespace runs
in the transcription changed nothing, because the gate's fixture lines carry no
multi-space runs. Replacing it with a decimal-comma normalisation -- the loss the
gate actually names -- reddened six tests.

**One gate could not be mutation-proven and is named rather than passed.** The
field-contract gate was red for the whole pass under a lane's in-flight move of
the extraction prompt and grounding surface, with the test file, four production
modules and a new untracked test all dirty. No stable signal was obtainable; it
needs a pass once that surface settles.

**One finding is a guard that is correct in code but insensitive at its call
site.** Ordering the mapping lane first reddened both ordering assertions, but
the known-bank test -- the one asserting an exact provider is not shadowed --
stayed green. The reason is not that ordering protects it: the lane's resolver
reaches a model and a profile-bound cache, neither available under test, so the
lane declines every file on the detection path regardless of position. The
file's own anti-vacuity test anticipates this risk and injects a static
resolver, but that proves the capability of a hand-constructed lane, not of the
object detection actually consults. The shadowing regression that test exists to
catch would not, today, be caught by it.

**Peer reds elsewhere were recorded, never patched.** The concurrently-edited
surfaces moved repeatedly during the pass; a transcription-adjacent import was
transiently broken by a peer mid-change and blocked two mutations until retried.
