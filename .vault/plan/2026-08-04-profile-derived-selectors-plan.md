---
tags:
  - '#plan'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_hash: 'sha256:969101381c44947a9e51f1badfca56d51faacf2206359949e675399b65c30870'
tier: L2
related:
  - '[[2026-08-04-profile-derived-selectors-adr]]'
  - '[[2026-08-04-profile-derived-selectors-research]]'
  - '[[2026-08-04-minimo-descendientes-eligibility-adr]]'
---

# `profile-derived-selectors` plan

## Description

Executes `2026-08-04-profile-derived-selectors-adr` in full. Twenty profile schema fields
declare a value the engine computes, render as editable rows, and silently suppress the
law computation when written to. This plan declares those paths as data, refuses operator
writes to them, deletes the declarations, and hardens the injectors.

`P02` must not begin until `2026-08-04-minimo-descendientes-eligibility-plan` is complete.
That plan corrects the derivation, and the refusal authored here closes the only channel
by which a filer can currently correct it. Landing the refusal first would convert a
correctable tax under-declaration into an uncorrectable one.

## Steps

### Phase `P01` - Prove the hazard and declare the namespace

Demonstrate the override with a real failing test before designing around it, then land the derived-selector pattern namespace additively while the field declarations still stand, so no commit boundary leaves a binding selector unresolvable. Retire the dormant selector-level as-of channel in its own commit rather than leaving a second unread temporal axis beside the new placeholder.

- [x] `P01.S01` - Prove with a real failing test that an operator-stored value at a derived aggregate path suppresses the Art. 58 computation on the live calculate path, and record the red run before flipping it; `src/cadrumo/application/modelo/tests/`.
- [x] `P01.S02` - Declare the derived-selector pattern namespace as ONE atomic commit over three interlocked files, the schema TOML array, the typed entry model and its field on the schema definition, and the loader payload that passes the key through, because the TOML alone is silently dropped and the loader alone raises at every schema load, compiling the filing-year placeholder as a four-digit terminal-anchored fragment so a shorter pattern cannot swallow a longer sibling; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/domain/user_profile/_schema.py, src/cadrumo/domain/user_profile/_loader.py`.
- [x] `P01.S03` - Retire the dormant selector-level as-of field, its two populated registry declarations, and the presence-only assertion that blesses it; `src/cadrumo/domain/calculations/registry/_bindings.py, src/cadrumo/_data/registry/aeat/modelos/100/revisions/, src/cadrumo/application/modelo/tests/test_profile_binding_real_path.py`.

### Phase `P02` - Refuse operator writes to derived paths

Add the path-legitimacy judgment beside the existing unknown-path check rather than inside the value-refusal authority, filter derived rows out of the overview in the same commit to close the transitional window, and convert the duplicated test seeding to real source facts.

- [x] `P02.S04` - Add a domain helper answering whether a path is derived, as the single written-once judgment over the declared patterns; `src/cadrumo/domain/user_profile/_schema.py`.
- [x] `P02.S05` - Consume the helper as the FIRST statement of the per-fact validation, before the field-index lookup, not merely before the unknown-path arm, because during this phase the declarations still stand so the index lookup succeeds and the unknown-path arm never fires, and invert in the same commit the write-door half of the override proof from P01.S01, whose fixture writes a sentinel through the real write door and will begin raising the moment this refusal lands; `src/cadrumo/application/user_profile/_validation.py, src/cadrumo/application/modelo/tests/test_derived_aggregate_override_real_path.py`.
- [x] `P02.S13` - Retire the write-time emission of the guarderia aggregate from the descendant projection AND add its calculate-time injection in the same commit as the refusal, injecting UNCONDITIONALLY with a zero default exactly as its menores-3 sibling does, never preserving the current emit-only-when-positive shape, because a conditional emission is the one derived pattern that legitimately resolves to nothing on an ordinary filer with descendants and no childcare spend and would therefore false-fire the later advisory on the majority case, and because that aggregate is otherwise the only one of the four with no injector so a childless or zero-expense filer leaves its casilla unresolved today; `src/cadrumo/domain/contribuyente/_descendant_facts.py, src/cadrumo/application/wizard/_checkpoint_store.py, src/cadrumo/application/modelo/_profile_binding.py`.
- [x] `P02.S06` - Confirm the refusal copy follows the validation module's own convention rather than adding a locale key, because every sibling issue message there is a formatted string and the translator is not imported, so a catalogue entry for this one message would be the inconsistent pattern and would leave the copy split across two homes; `src/cadrumo/application/user_profile/_validation.py`.
- [x] `P02.S07` - Filter derived paths out of the profile overview projection in the same commit as the refusal, closing the window where a row would render that the write door refuses; `src/cadrumo/application/user_profile/_overview.py`.
- [x] `P02.S08` - Delete the three derived-path seed lines from the eight files carrying the duplicated block, leaving the raw operator field untouched, and do NOT add per-descendant rows to compensate because all eight profiles declare zero descendants so the injector re-derives zero from genuine absence and no expected figure may move, treating any assertion that shifts as evidence the deletion was done wrong rather than as a figure to re-pin, and excluding the two idempotency tests whose purpose is asserting the injector defers to an explicit fact; `src/cadrumo/application/modelo/tests/, src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P03` - Delete the declarations and harden the injectors

Delete the twenty declarations, their locale entries, and the one write-time materialisation in a single explicit-path commit, then make the injectors compute-always, gate future filing years on registry content rather than Python constants, and replace the silent parse swallow with a refusal.

- [x] `P03.S09` - Delete the twenty derived field declarations, then run the locales scaffold verb in the same commit to prune all eighty catalogue leaves in one pass because the per-key remove verb accepts a live key silently and would need eighty invocations, and delete the one registry-contract test that asserts the year-suffixed selectors are declared field paths while keeping the shared year constant its surviving siblings consume; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/locales/, src/cadrumo/domain/user_profile/tests/test_registry_contract.py`.
- [x] `P03.S10` - Make the remaining injectors compute-always so a stray stored fact cannot win, and invert rather than delete the three tests that bless the defer-to-explicit-fact behaviour being removed, namely the two idempotency tests whose seeded sentinels stay valid as anti-tautology proof in the inverted direction, and the suppression half of the override proof from P01.S01; `src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/application/modelo/tests/test_minimo_descendientes_engine.py, src/cadrumo/application/modelo/tests/test_anualidades_eligibility_derivation.py, src/cadrumo/application/modelo/tests/test_derived_aggregate_override_real_path.py`.
- [x] `P03.S11` - Replace the two year-gating frozensets and the hardcoded single-year gate with gating on registry content, dropping the minimo frozenset outright because its parameter-presence check already covers the same ground and keying the other two on consuming-binding presence, and land this in the SAME commit as the derived-scoped advisory because removing the code-maintained year ceiling is only safe once an uncovered year with a declared binding surfaces visibly rather than silently resolving to nothing; `src/cadrumo/application/modelo/_profile_binding.py`.
- [x] `P03.S12` - Replace the silent parse swallow that under-counts a descendant with a raised binding-resolution refusal naming the index and value, reusing the existing error class in that module rather than minting one, and add the derived-scoped advisory through the existing calculation-source diagnostic channel the profile resolver already returns but has never populated, landing it in the same commit as the year-gate change it makes safe; `src/cadrumo/application/modelo/_profile_binding.py`.

## Parallelization

`P01` steps are sequential: the proof grounds the design, and the namespace must exist
before anything depends on it. The `valid_at` retirement is independent of the rest of
`P01` and may run in parallel with it. `P02` and `P03` are strictly sequential, and both
are gated on the sibling eligibility plan completing.

## Verification

The plan is complete when every Step is closed and all of the following hold: the
override hazard is demonstrated and then demonstrably closed, with the same probe
inverted; every declared pattern matches at least one live binding selector and the
anti-rot gate fails if one does not; the refusal fires from both the lifecycle write door
and the manager validator pre-check, and no derived row renders in the overview
row-count probe; the value-refusal authority and its two exhaustive consumers are
unchanged; a full registry load and per-modelo validation pass green after the deletion
commit, with collection clean across the tree; a stray stored fact at a derived path
provably does not alter the computed aggregates; and the shipped tests derive expected
figures from external oracles rather than from the formulas under test.

Two further criteria cover hazards a grounding pass surfaced after the Steps were first
written.

The advisory must be proved in its false-fire direction, not only its true-fire one. A
profile carrying descendants but no childcare spend is the ordinary case, not an edge
case, and must NOT raise the derived-scoped advisory. A test pinning that specific shape is
required, because the one conditional emission among the five patterns is exactly where a
blanket advisory would train operators to ignore it.

The refusal's effect on an already-stored fact must be stated and tested, not assumed. The
profile validator judges the full merged fact set on every edit, not the incoming delta, so
a bucket carrying a stale fact at a derived path from before the refusal existed will have
that fact re-judged on every subsequent edit to any other field, refusing a write the
operator did not make. This is a pre-existing structural property shared with the shipped
unknown-path check rather than something this campaign introduces, and under the
pre-release no-released-data posture it is acceptable to accept rather than close. What is
not acceptable is leaving it undiscovered: the plan is complete only once the behaviour is
either covered by a test or recorded as knowingly accepted in the closing audit.
