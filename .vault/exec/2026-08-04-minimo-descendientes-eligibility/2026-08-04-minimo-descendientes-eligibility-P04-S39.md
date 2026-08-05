---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e1b3a8e5e7f0d95773de2802bea7d17475320ea50de6deca849f2c549ef52805'
step_id: 'S39'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
# Model both limbs of the fallecimiento rule in one slice

## Scope

- `src/cadrumo/domain/contribuyente/family.py`
- `src/cadrumo/domain/contribuyente/_descendant_facts.py`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Add `death_date` to the canonical descendant record, with a validator refusing
  a death that precedes the birth.
- Add the two predicates the limbs read separately: died-in-period for the flat
  cuantia, died-before-devengo for the ordering exclusion.
- Fail eligibility outright for a descendant who died in a prior year, gated on
  the predicate both the aggregate and the calculate-path advisory share.
- Replace the birth-order tranche with the norma 4a flat figure for a descendant
  who died in the period, read from its own registry parameter.
- Compute the birth-order ranking over the survivors alone, keyed by position.
- Resolve and pass the flat figure through the profile-binding injector for both
  the estatal and autonomico aggregates.
- Carry the fact through the persistence layer: writer, key pattern, reader, and
  the flag parser's accepted-key set.
- Ship the entry surface with the field: the `--descendiente` flag key, its help
  string, the CLI list row, and the typed list payload.
- Declare the field and the new legal reference on the user-profile schema.
- Add the two-limb suite and the persisted-shape roundtrip with its
  anti-tautology proofs.

## Outcome

Both limbs of article 61 norma 4a are modelled, and the fact they turn on is
enterable, persistable, and reloadable.

The rule was unreachable rather than merely unimplemented: the death date
existed on the Modelo 100 profile row and never on the canonical descendant
record, so no caller could state the fact the aggregate needed.

The worked case is three children with the middle one dying in June. The
manual's answer is 7.500 EUR. With neither limb it is 9.100. With the flat
cuantia alone it is ALSO 9.100 - the flat figure buys nothing at that rank, so a
flat-amount-only fix would have shipped looking complete while leaving the whole
over-grant standing. That case is now the load-bearing test.

The menor-3 supplement accrues ON TOP of the flat figure. The flat figure
replaces the tranche only.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

FOR WHOEVER WIRES THE ASCENDIENTES MINIMO. Article 61 norma 4a fixes both
figures in ONE sentence: 2.400 EUR for a descendiente and 1.150 EUR for an
ascendiente. The legal entry `ley-35-2006:art-61-norma-4` is already written as
the single authority for both. Cite it and add the 1.150 figure beside the
existing parameter. Do NOT mint a second legal entry for the same clause - one
clause, one authority. The entry's own notes repeat this instruction.

Three findings the Step as written did not carry, each grounded in the bundled
manuals rather than reasoned:

The menor-3 supplement SURVIVES the death. The manual states the increase
applies where the descendant died during the period, so the flat cuantia
displaces the tranche and nothing else. Reading the flat figure as the whole
entitlement would UNDER-grant a bereaved filer - the opposite direction to the
over-grant this Step closes, and it is what a literal reading of the original
row invited.

The two limbs are scoped differently, and this is implemented literally. The
cuantia is owed on any death in the period; the ordering exclusion is expressly
conditioned on the death preceding the devengo. A death ON 31 December therefore
takes the flat figure and KEEPS its rank, while a 30 December death does not.
The pair is pinned so the boundary sits on the exact day. Collapsing the two
conditions would be a choice neither text supports.

A death in a PRIOR year now fails eligibility outright. The birth date alone
goes on satisfying "under 25 at year-end" indefinitely, so without that gate a
bereaved filer would keep claiming for a child who died years ago, and norma 4a
would not catch it either, being scoped to a death in the period.

Ranking is keyed by POSITION, not by record. The descendant record is frozen, so
twins with identical declarations compare equal and a value-keyed lookup would
hand the survivor the deceased's rank.

Neither limb can regress silently. A mutation probe disables each limb in the
production code path in-process, leaving no mutation window on any tracked file:
limb one disabled gives 9.100, limb two disabled gives 8.800, both give 7.500.
Expected totals throughout are the manual's printed euros added by hand, pinned
to the registry parameters by a guard test so a re-authored parameter fails
first and names the drift.

The entry-surface test earned its place by failing on its first run: the flag
parser carries an accepted-key allow-list that was missed, so the field would
have shipped persistable but not enterable - the dead-shape defect in reverse.
Two further self-inflicted defects were caught before commit: a
died-before-devengo predicate written as a month comparison, which would have
mis-scoped every December death, and a schema description pushed over its
512-character cap.

INCIDENT, self-inflicted and reported. That description overflow was live in the
working tree between the edit and the fix. The user-profile schema then failed
to load, which took down every consumer of it tree-wide, and two peer agents saw
it as flapping test failures in their own modules with an error naming a length
constraint that says nothing about descendants. One lost a probe to it. The
working tree is what peers execute against, so an invariant intended to hold "by
commit time" is broken for everyone until then; it must hold at every save. The
recovering signal - red then green - is the expensive part, because a flapping
red reads as flake and gets re-run rather than diagnosed.

The 512-character cap is NOT the wrong constraint, despite being the easy
diagnosis. The field is an object carrying sixteen sub-fields and its
description is a comma-list of fourteen clauses; raising the cap would let the
sentence keep growing. The real fix is per-sub-field descriptions, a schema-shape
change outside this campaign. Logged, not acted on.

Affected lanes: 2033 passed, 4 failed, 103 deselected. All four failures are
foreign and attributed with evidence: two fixture constructors passing a label
field the revision schema no longer permits, from the localization cascade; one
diagnostic message exceeding its cap from locale catalogues under active peer
edit; one stale expectation left by the pre-2023 cotizaciones-ceiling landing.
The eligibility gate added here is guarded on a populated death date, so it is
provably inert on all four fixtures.
