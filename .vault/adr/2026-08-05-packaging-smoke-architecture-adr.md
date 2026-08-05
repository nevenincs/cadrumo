---
tags:
  - '#adr'
  - '#packaging-smoke-architecture'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e35e2fecf7cf651023308894dccfc74e6a95cb0eb5bbe93802ef322254163e3a'
related:
  - "[[2026-08-05-packaging-smoke-architecture-audit]]"
  - "[[2026-06-28-product-packaging-research]]"
  - "[[2026-07-20-ci-speed-redesign-adr]]"
  - "[[2026-07-15-distribution-installation-readiness-research]]"
---

# `packaging-smoke-architecture` adr: `Lane-form hierarchy for the packaging proof surface` | (**status:** `accepted`)

## Problem Statement

The packaging proof surface has no ratified structure. The two-level shape — a small
number of lanes, each owning an invariant, each carrying several forms that vary one
axis — exists only as a recommendation in `2026-06-28-product-packaging-research`, which
defined Core as one lane listing the isolated-virtualenv, plain-pip, source-distribution,
aggregate-optional-extra, and Linux-container forms inside a single bullet, and Browser
as a second lane. It was never carried into an accepted decision: the accepted
`2026-06-28-product-packaging-adr` decides the exact-version wheel cohort and names lanes
only in passing, and no later record rules on lane structure. What shipped is `_LANES` in
`dev/packaging/campaign.py`, a flat dictionary in which every form was promoted to a
top-level peer lane.

This is therefore a missing decision, not a violated one, and it is the root cause
`2026-08-05-packaging-smoke-architecture-audit` names for the surface's other defects.
Because no lane owns its invariant, each form re-asserts it. Because no lane owns the
question "what did this prove", each form hand-writes a `checks=` string literal, and a
string literal cannot go stale loudly.

A decision is needed now rather than another point-fix because the point-fixes have
already happened and changed nothing structural. At HEAD the split form's two false
manifest claims are gone and its duplicate installed-oracle call is gone — the installed
tax oracle now runs twice per campaign (`smoke_core` plus the serial installed-oracles
pass), not three times. Both corrections landed by hand, inside a swept checkpoint commit
whose subject describes unrelated Modelo localization work. The mechanism that permitted
the false claim is untouched, so the same class recurs on the next form added.

The framing that must survive into implementation: the surface accreted redundant
STRUCTURE, not redundant PROOFS. Eight of ten registry lanes carry unique marginal proof
per the audit's per-lane verdicts. This is not a lane-deletion campaign, and nothing here
proposes reducing what is proven.

## Considerations

- The two-lane shape is a research recommendation only; ratifying it is this record's
  job. Verified against the ADR corpus, not inferred.
- Two headline symptoms are already closed at HEAD, which removes their urgency and
  strengthens the structural argument rather than weakening it: hand-discipline is
  currently the only thing standing between the manifest and a false claim.
- `2026-07-20-ci-speed-redesign-adr` D1 governs the per-push gate and the ten-minute
  budget; its `quick` profile is a one-lane per-push gate, the same correction arriving
  from the other end. Its D3 makes the campaign registry the owner of profiles, and its
  D6 pins `test_campaign.py` to the justfile recipes.
- That D6 pin is a substring check, and its target is moving: the per-lane `just` recipes
  exist at HEAD but a peer is removing them in the working tree at the time of writing,
  leaving only the three profile aggregates. Any decision here must re-point the pin
  rather than depend on the recipes.
- The manifest `checks` tuple has no production consumer that reads its contents. Only
  `dev/packaging/tests/test_smoke_manifest.py` pins it; the readiness gate and the
  evidence checkpoint read `ok`, `lane`, and `completed_at`. That is both why the false
  claim went unnoticed and why correcting the mechanism is cheap.
- `2026-07-15-distribution-installation-readiness-research` F2 already found the evidence
  contract fragmented, with real 0.2.1 execution results, and measured the split lane at
  740 seconds. That measurement predates the oracle removal, so the lane's current cost is
  unmeasured.
- Some invariants are properties of cohort bytes and genuinely run once; others are
  properties of an installed virtualenv and are inherently per-form. Collapsing the second
  class would delete proof, not duplication.

## Considered options

- **Keep the flat registry, continue point-fixing.** Cheapest, no migration, no evidence
  risk. Rejected: it is the status quo that produced a false manifest claim and a
  triplicated oracle, and both were repaired without changing the mechanism that allowed
  them. The next form repeats the class.
- **Prune lanes economically.** Delete the lanes that look redundant, chiefly split and
  the container Browser form. Rejected: the audit's per-lane verdicts find unique marginal
  proof in eight of ten, and the container Browser form is explicitly unmeasured. This
  trades real coverage for apparent tidiness and answers the wrong question.
- **Express forms as profile membership only.** Let `_PROFILES` carry the hierarchy and
  leave `_LANES` flat. Rejected: profiles select what runs on an occasion; they cannot own
  an invariant or a proof contract, so the `checks=` literal and the re-asserted invariant
  both survive untouched.
- **A fully generic parameterised matrix** over installer, artifact, extras, cohort
  assertions, and environment. Rejected: the axes are not orthogonal — no
  sdist-plus-container form exists or is wanted — so a cartesian registry generates
  combinations nobody has justified, inverting this record's own principle that every
  executed unit names the defect class it uniquely catches.
- **Two-level registry: lanes own invariants, forms vary one axis; manifest claims derived
  from executed assertions.** Chosen. Preserves every currently executed proof, gives the
  invariant and the proof contract an owner, and is the shape the original research
  described.

## Constraints

- Publication is HELD behind two structural blockers. This surface mints release evidence,
  so the decision must not change what evidence is produced or how it is attributed. It
  does not: the executed proof set is preserved unit-for-unit, and
  `PackagingSmokeManifest` keeps its schema and field types, so every existing evidence
  row remains valid and readable and no row is invalidated or needs re-minting.
- `aeat-architecture-boundaries` and `no-legacy-compatibility` bar shims, compatibility
  layers, and parallel authorities. The flat `_LANES` must not survive alongside the
  two-level registry "for compatibility"; the replacement is atomic.
- `2026-07-20-ci-speed-redesign-adr` D1's per-push budget binds. The `quick` profile must
  keep resolving to exactly one executed unit — the uv-virtualenv form of Core — with
  unchanged behaviour and wall time, and must remain structurally unable to enter the
  promotion gate.
- The proof-cache fingerprint covers `dev/packaging`, so any change here invalidates
  carried quick-profile proofs by construction. That is correct behaviour, and it means
  the first push after each migration step pays a full quick run.
- Parent-feature stability: the cohort contract of `2026-06-28-product-packaging-adr` and
  the profile mechanism of the CI-speed ADR are both accepted and stable. This record
  builds on them and contradicts neither.

## Implementation

**Scope bound, stated so this record is not read as complete over a set nobody
enumerated.** This decision governs the campaign registry — the ten install-form lanes
`_LANES` resolves and the profiles that select them. It does NOT govern the
acquisition-channel surfaces (`smoke_homebrew`, `smoke_mcpb`, `smoke_plugin_install`,
`smoke_desktop_client`, `smoke_scoop.ps1`), which are not in `_LANES`, are driven by
separate per-channel workflows, and answer an orthogonal question — how a user obtains the
artifact, not how it installs. Conflating the two populations is why the surface looks
more repetitive than it is, and nothing here sweeps them into the hierarchy. The decision
is also NOT complete over the wider proof surface: the `smoke_*` filename glob that
produced the audit's inventory misses `installed_tax_oracle`, `installed_mcp_oracle`,
`serving_path_benchmark`, `constraint_effect`, and `source_preflight`, each a real proof
without the prefix. Bringing those under the hierarchy is out of scope and unenumerated.

**The hierarchy.** Three lanes replace ten. A lane owns an invariant and a behavioural
proof; a form varies exactly one axis of how that invariant is reached.

- **Core** — invariant: the exact-version wheel cohort installs, and the installed CLI
  performs grounded tax work. Forms: uv-virtualenv, plain-pip, source-distribution,
  aggregate-extras, joined-cohort, container.
- **Browser** — invariant: the installed wheel provisions Chromium. Forms: host,
  host-with-deps, container.
- **Dev** — standalone, one form: the frozen lock materialises a working developer
  toolchain. It is a lane rather than a Core form because its invariant is not
  shipped-artifact installability and it consumes no cohort.

This places the container form of Core inside Core, where the original research put it,
and diverges deliberately from the audit's recommendation that the container Core lane
stand alone. The audit's own criterion decides it: that lane consumes the same cohort and
asserts the same invariant, varying only the environment axis (host or clean container).
"No host contamination" is what varying that axis proves, which is the definition of a
form, not of a lane. The developer-toolchain lane stands alone under the same criterion,
because its invariant differs.

**Where forms live.** Forms live on the lane record, not in the profiles: `Lane` gains a
`forms` tuple, each form carrying its module, its arguments, and the assertions it
uniquely contributes. `_LANES` becomes a three-entry registry of lanes. `_PROFILES`
changes from tuples of lane names to tuples of qualified form selectors, so a profile
still says exactly which executable units run — `quick` becomes the single Core
uv-virtualenv form — while the lane, not the profile, owns the invariant. The registry
stays the single authority for what each profile proves, as the CI-speed ADR D3 requires.

**Invariant ownership, split by class.** Naive "assert the invariant once per lane" would
delete proof, so the classes are separated explicitly. Cohort-byte invariants — the
three-wheel completeness, the shedding filter, the per-file sub-cap, the metadata surface
— are owned by the cohort builder at construction time, where `python_cohort` already
enforces them, and are asserted by no form. Install-level invariants —
`assert_installed_cohort` and the resolver's own dependency check — stay per-form, because
the installed virtualenv is precisely what a form produces and asserting it once would
leave the other installers unproven. The behavioural proof — the installed tax oracle —
becomes lane-level: it runs once per lane per campaign against a designated reference
form, and a conformance pin asserts no other form invokes it. That is the class where the
triplication lived, and it is the only class that legitimately collapses.

**"What did this prove", derived rather than declared.** The `checks=` string literal is
replaced by a two-sided mechanism, because either half alone still permits a lie. Each
assertion helper records its identity into a run-scoped ledger as it executes, and the
manifest writer reads the ledger — so a claim cannot appear unless its assertion ran,
which is the over-claim the split form made. Independently, each form declares the
contract it is expected to satisfy, and the run fails loudly at the end of `main()` when a
declared claim was never recorded — which catches the inverse, a form that silently stops
running something it promised. `PackagingSmokeManifest` is unchanged: `checks` keeps its
name, type, and schema, and only its provenance changes from a hand-written literal to a
derived record.

**What becomes of split.** It stops being a lane and becomes the joined-cohort form of
Core, contributing exactly its two uniquely executed assertions: the joined-companion-
namespace corpus probe and the byte-exact registry verification. Nothing it proves is
lost. Its justification did not evaporate — it decayed when the core lane absorbed the
cohort install and nothing recomputed it — so the correct record is a structural
reclassification, not a retirement. Its 740-second measurement in
`2026-07-15-distribution-installation-readiness-research` F2 predates the oracle removal
already landed at HEAD; the current cost is inferred to be materially lower and is
unmeasured. No economic claim is made for or against it here.

**Migration sequencing, green at every step.**

1. Replace the flat registry with the two-level one in one atomic commit: lane and form
   types, the three lane entries, profiles rewritten to form selectors, and the
   conformance pin re-pointed from justfile substrings to the profile-to-form sets. The
   executed set is byte-identical because each form is the current module with its current
   arguments, so no campaign changes what it mints. No flat `_LANES` remains anywhere.
   This step also resolves the live collision with the peer removal of the per-lane `just`
   recipes: the registry becomes the sole authority for what runs, and the justfile
   carries only profile aggregates.
2. Land the proof ledger and the declared-contract check, manifest schema unchanged. Green
   because a correctly declared contract matches what already runs; any mismatch this step
   surfaces is a real pre-existing overstatement and is fixed in the same commit.
3. Move the installed tax oracle to lane-level ownership with its pin. At HEAD this is
   almost entirely the pin, since the duplicate call is already gone.
4. Measure the container Browser form and the post-oracle joined-cohort form. Keep or
   retire each on the measurement, as separate decisions. "It looks redundant" is not
   evidence and does not license a deletion here.

No intermediate step leaves a knowingly-broken state in the shared pipeline, because each
step preserves the executed proof set and each lands its own pin.

## Rationale

The knockout criterion is that every alternative leaves the mechanism intact. The audit
establishes that the defects are symptoms of the flattening; HEAD establishes that the
symptoms can be repaired without touching the cause, because they already were. A decision
whose effect is another round of hand-repair is not a decision.

Against the deletion option the argument is evidentiary rather than aesthetic: eight of
ten lanes carry uniquely caught defect classes per the audit's per-lane verdicts, so a
shorter registry would buy tidiness with coverage. The two-level shape reaches the same
tidiness by reorganising rather than removing, which is why the split question dissolves
under it instead of needing to be won.

Against the profile-only option, profiles are occasion selectors; an invariant needs an
owner that exists independently of which occasion is running. The CI-speed ADR's `quick`
profile already demonstrates the limit — it is the correct small per-push gate, and it
still cannot stop a form from re-asserting a lane invariant or from claiming a check it
did not run.

The derived-plus-declared manifest is the one part that is strictly stronger than the
original research's design, and it is justified by the observed failure: a hand-written
literal is unfalsifiable by construction, and the checking instrument gets less scrutiny
than the thing it checks. Deriving alone would still let a form quietly stop proving
something; declaring alone reproduces the literal. Both sides are required.

## Consequences

Good. The invariant and the proof contract each gain an owner, so the two defect classes
this campaign found become structurally unavailable rather than currently absent. A new
install form costs one form entry and its axis-specific assertions instead of a full lane
with a re-asserted preamble and a hand-written claim list. The registry becomes readable
as an answer to "what do we prove, and how many ways do we reach it", which is the
question the flat list could not answer. The proof-cache and profile mechanisms are
untouched and keep working.

Bad, and stated plainly. This is structure work that mints no new proof: after it lands,
the product is exactly as well proven as before, so the entire return is in defect classes
avoided and in future forms being cheaper. It costs a migration across the campaign
driver, every smoke writer, and the conformance pins, in a tree where three agents are
concurrently live in the same directory. The form abstraction can over-generalise — if a
future proof does not vary one clean axis, forcing it into a form is worse than a
standalone lane, and the developer-toolchain lane is already the precedent for refusing
that pressure. Step 2 will probably surface further overstatements in the other forms'
claim tuples, which the audit verified only for split and the five wheel forms; those are
honest findings but they widen the step.

Neutral. Two measurements are deferred rather than resolved: the container Browser form
and the current cost of the joined-cohort form. Both were already unmeasured before this
record; it neither improves nor worsens that, and step 4 is where they come due.

Pathway opened, and the reason for the recommendation below. Once a run can state what it
proved because it recorded it, the same mechanism generalises from the per-lane manifest
to the release evidence document, which is the consolidation question seen from the other
end.

**Recommendation on the second question, which this record does not decide.** The
evidence-module consolidation — six evidence modules and a 1,605-line identity verifier,
already found fragmented by `2026-07-15-distribution-installation-readiness-research` F2
with real 0.2.1 execution results — should be its own ADR, sequenced after this one. The
trade-off, stated plainly rather than resolved: one combined record risks an unruleable
blast radius, because this decision is confined to the campaign registry and the smoke
writers and changes no schema, whereas consolidation touches the release evidence schema,
the readiness gate, and the scrub surface, all on the publication path that is currently
HELD — an operator asked to approve both at once is asked to approve the second without
the first's mechanism having been observed working. Two records risk the second never
happening, which is a real cost and is exactly what F2 documents, since that finding has
stood unconsolidated since 0.2.1. The mitigation that makes the split defensible is
concrete rather than procedural: this record's derived-plus-declared ledger installs the
owner for "what did this prove" at the manifest level, so the consolidation ADR inherits a
working, exercised mechanism to generalise instead of starting from the same blank
question. The operator's call is whether that inheritance is worth the risk of the delay.
