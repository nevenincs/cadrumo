---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:96a83ea8d341c3580f0a96caa65775e88ec23dbfa4d4054d79bc97f6a417cfbf'
step_id: 'S16'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Bring the Modelo 130 previous-year economic-activity net income carry onto a canonical mechanism, because as declared it occupies no row of the one-mechanism-per-calculation-type taxonomy. It declares source previous_filing with source_modelo 100, filing_year_delta minus one and grouping none, which makes it a CROSS-MODELO fold-in reading another modelo's annual return, and the taxonomy's row for a cross-modelo fold-in is a relation, not a direct previous_filing carry. The direct previous_filing row covers a SAME-modelo static carry only. This is the one renta carry that reads another modelo's annual return, so it is exactly the channel a pulled Modelo 100 history feeds, which is why the ruling declines to classify it while it sits outside the taxonomy. Preferred remedy is to model it as a relation with the cross_model_output kind so the enrolled relation resolver owns it. The alternative is to amend the taxonomy to admit a cross-modelo direct carry, which requires naming the rejected design and saying why one fold-in modelled two ways is acceptable here when the taxonomy exists to forbid it. Gate: the binding resolves through exactly one enrolled mechanism, the aggregation-taxonomy ADR either covers it by an existing row or carries an amendment naming the rejected design, and a test proves the carry still produces the same value through the new mechanism

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/130`
- `src/cadrumo/application/aggregation`

## Description

- Confirmed the ADR question first: the calculation-aggregation-taxonomy ADR
  (2026-06-10) already covers this exact shape by an EXISTING row — its
  implementation table names "Cross-MODELO fold-in" canonical as a relation
  (`cross_model_output`) — so no ADR amendment is needed; the row's
  "alternative" (amend the taxonomy) is not the right escape hatch here.
- Confirmed `RelationPrefillSourceResolver` is already enrolled in the live
  calculate mesh (`_calculation_actions.py`), so the migration is registry-
  data-only, not an application-layer enrollment gap.
- Designed and built the full migration: four `cross_model_output` relations
  (the relation schema's `source_casilla_id` is singular, so the binding's
  four-casilla `previous_filing` selector needs four relations, not one —
  mirroring the ADR's own M100 casilla 0604 worked example, which sums
  multiple relations directly via `{ relation = ... }` formula operands
  rather than re-aggregating inside one relation entity), four
  `relation_prefill` slot bindings, one new `internal_only` computed casilla
  summing the four relations, and a rewrite of the consuming minoración
  formula (casilla 13) to read the new casilla instead of the old binding.
  Construct membership and legal_refs coverage updated in the same pass.
- Discovered mid-build, via the temp-root validator: a genuine, previously-
  unexercised structural gap in the relation-source year-coverage gate
  (`validate_relation_source_coordinate_coverage`,
  `_validate_relation_sources.py`/`_validate_relation_periods.py`). Every
  EXISTING relation with a negative `filing_year_delta` (the M202→M200
  precedent) reads from a source modelo whose OWN revision is open-ended
  (`year_from`, no `year_to`), so the gate's `_is_pre_modelled_history`
  exception (covering years BEFORE the source's earliest modelled year) is
  the only relief it has ever needed. Modelo 100 is period-versioned
  per-year (each revision covers exactly one closed year), unlike Modelo
  200's open-ended revision, so an open-ended Modelo 130 relation reading
  Modelo 100 at `filing_year_delta=-1` fails this gate for every year beyond
  Modelo 100's latest authored revision — a standing, perpetual failure with
  no discharge, because this gate (unlike its `previous_filing` sibling,
  `_validate_previous_filing_year_coverage.py`, built this campaign) has no
  "future year not yet published" structural exclusion AND no allowlist
  mechanism at all.
- REVERTED every registry TOML edit back to the exact HEAD content (byte-
  identical `git diff` after restore) rather than land data that fails an
  ALREADY-LIVE mandatory build validator — landing it would red the whole
  registry for every concurrent agent in this shared tree, the same class of
  mistake this campaign already caught and corrected once this session.
  Confirmed clean via a fresh temp-root `authority.validate_registry()` pass
  after the revert.

## Outcome

NOT COMPLETE. The ADR question is answered (relation is canonical, already
covered, no amendment needed) and the full migration is DESIGNED — every
registry entity, every id, every legal ref, every construct-membership
update — but landing it is blocked on a real prerequisite this row did not
anticipate: `validate_relation_source_coordinate_coverage` needs the SAME
allowlist-with-structural-exclusions treatment this campaign already built
for the `previous_filing` sibling gate (P01.S13), because this is the FIRST
relation in the bundled corpus to pair an open-ended consumer with a
per-year-versioned (not open-ended) source modelo. Building that safely — a
build-time refusal with a reasoned, keyed allowlist, plus the "future not
yet published" structural exclusion its sibling already has — is its own
scoped task, not a corner of this one, and per this campaign's own standing
caution ("wiring anything into the mandatory build-time validator in a
shared worktree takes the whole tree down for every concurrent agent,
instantly"), it must not be attempted as a rushed addendum here.

The registry tree is verified back to its exact pre-row state (temp-root
`validate_registry()` clean, zero diff against HEAD on every touched file).
Nothing in this row's investigation was destructive or left in a partial
state; the full migration design (relation ids, slot-binding ids, the
internal casilla, the formula rewrite) is recorded above so the follow-up
row does not have to re-derive it.

## Notes

WHAT THE FOLLOW-UP ROW NEEDS, IN ORDER: (1) extend
`validate_relation_source_coordinate_coverage` (or add a sibling module
mirroring `_validate_previous_filing_year_coverage.py`'s exact shape) with
a build-time allowlist for a source modelo whose latest revision predates
what an open-ended consumer's relation can ask for, keyed by relation id
with a reason and discharge condition, plus the same "beyond the source's
own latest published year is not a corpus gap" structural exclusion the
`previous_filing` gate already has; (2) re-apply this row's already-
designed migration (the exact TOML content is recorded in the Description
above) once that prerequisite gate change is live and verified against a
temp root; (3) remove this row's own now-obsolete S13 allowance entry
(`irpf.previous_year_economic_activity_net_income`) in the SAME commit that
deletes the `previous_filing` binding, since the `encountered_binding_ids`
staleness check cannot detect a permanently retired binding on its own — it
is never "encountered" by any call once the binding no longer exists
anywhere, so the allowlist would otherwise silently outlive the gap it was
written for; (4) a value-parity test proving the relation-based path
resolves to the same Decimal a real Modelo 100 observation would have
produced through the old `previous_filing` path.

The row's own escape-hatch framing ("the alternative is to amend the
taxonomy... naming the rejected design") does not fit what was actually
found: the taxonomy is not wrong and does not need amending. What blocks
completion is a gap in a DIFFERENT, already-existing enforcement mechanism
that nothing in the corpus had exercised yet, discovered only by attempting
the real migration against the real validator rather than by reasoning
about the schema in the abstract.

FOLLOW-UP STEP (1) LANDED, in a later session. Extended
`validate_relation_source_coordinate_coverage` exactly as prescribed above:
a STRUCTURAL, unconditional "beyond the source's own latest modelled year"
exclusion (`_is_beyond_latest_modelled_source_year` /
`_source_upper_bound` in `_validate_relation_periods.py`), separate from the
existing observation-history-only pre-modelled exception, plus a keyed
allowlist mechanism (`_RelationSourceYearCoverageAllowance` /
`_ALLOWANCES` in `_validate_relation_sources.py`) mirroring the
`previous_filing` sibling's exact shape: matched by `(relation_id,
source_modelo, source_period, missing_from_year, missing_through_year)`,
never by line number, with a stale-entry check run once per full registry
sweep. `_ALLOWANCES` ships EMPTY — nothing in the committed corpus needs an
entry yet, proven by a synthetic fixture (see below) rather than assumed.

A real, first-hand finding surfaced while proving the extension against a
fixture shaped like this row's own designed migration: because the relation
schema's `OBSERVATION_BACKED_BINDING_SOURCE_KINDS` set already includes
`relation_prefill` (not just `previous_filing`), a relation whose
`target_binding` is `relation_prefill`-sourced is ALREADY
`source_is_observation_history = True`
(`_relation_is_prior_year_filing_carry`), so the EXISTING pre-modelled
exception ALREADY covers the 2018-2019 gap this row's own Description
predicted would need an allowlist entry. Once step (2) re-applies the
migration with `relation_prefill` slot bindings (as designed above), the
2018-2019 range needs NO allowlist entry at all — only the NEW future-year
exclusion (2026 onward) does any work for this specific relation. This
narrows step (2)'s remaining allowlist need to zero for the 2018-2019 range
specifically; re-verify this holds once the real relations exist, since a
synthetic proxy fixture is evidence, not the same claim as the real one.

Verified: `ruff check`, `ruff format --check`, `basedpyright` clean on both
touched files; the existing `test_relation_closure.py` suite (23 tests
covering the real bundled corpus) passes unchanged; a fresh temp-root
`authority.validate_registry()` pass over the full bundled tree is clean;
6 new tests added to `test_relation_closure.py` proving, against a synthetic
relation attached to Modelo 130's real open-ended revision reading Modelo
100's real per-year-closed revisions: the future-only structural exclusion
fires and the historical one stays scoped to observation-history carries,
the observation-history-backed shape needs zero findings end to end, the
allowlist suppresses a matching finding and reports a genuinely stale one,
and a widened gap is NOT silently absorbed by a narrower allowance (the
match is exact, never start-year-only).

NOT YET DONE, and NOT attempted in this pass on purpose: re-applying the
actual M130 registry migration (step 2), removing the now-obsolete S13
`previous_filing` allowance in the same commit as the binding deletion
(step 3), and the value-parity test (step 4). Landing registry TOML while
this shared tree shows widespread, clearly pre-existing unrelated
`domain/calculations/registry/tests` breakage (157 failures spanning M303
period-split, M390 recargo boxes, M100 art. 23.2 tiers, M322/M353 grupo
worked examples, none of which touch the two files this session's changes
touched, and none of which the isolated temp-root `validate_registry()`
run reproduces) is a bad time to also introduce new registry content: any
NEW failure would be unattributable against that noise floor. Flagged to
the team lead rather than pushed through.

RE-VERIFIED SEQUENTIALLY, per the team lead's instruction that a parallel
count is not trustworthy on this share: `pytest
domain/calculations/registry/tests/ -n0 -q`, full output to a file, exit
status captured on the very next command (not the pipeline's), sliced for
`^FAILED` after the write. Result: **157 failed, 4195 passed, 23
deselected, exit 1 — identical to the parallel count.** This is NOT the
loader-cache race; the noise floor is real.

Grouped by exact exception message rather than by owning file, the 157
decompose into a handful of systemic causes, not 157 independent defects:
51 (37+14) share one already-committed origin — `IvaLedgerObservation`
("IVA facts require exact deduction authority") and `_IvaLedgerSelector`
(missing required `observation_roles`/`cash_accounting_treatments`)
validation failures, tracing by `git log` to `173a9a5038 feat(iva): bind
deduction fact authority`, whose message matches the validation wording
exactly — a validation rule that shipped without updating every binding
and fixture it now constrains. 43 share one exact message,
`RegistryValidationError: binding
'renta-2024-profile-deduccion-maternidad' has no supplied value`, across
most of the M100/Renta 2024 test files. The remainder (46 AssertionError,
8 IndexError, 6 StopIteration, 1 FileNotFoundError) are more varied:
casilla TOML naming-convention violations, a continuidad-completeness
ratchet baseline drift for modelo 303, and Modelo 232's `2016-2017`
revision carrying an entirely empty `export_layouts`.

Confirms this row's own two touched files
(`_validate_relation_periods.py`, `_validate_relation_sources.py`) are not
implicated: neither appears anywhere in the 157 failure signatures, both
are confirmed clean by the isolated temp-root `validate_registry()` run
already recorded above, and the two systemic clusters above trace to
`_ledger_bindings.py`/`_formula_runtime.py` and M100 registry data — files
this row never touched. Reported to the team lead with the full grouping;
this is bigger than this row and is not this row's to fix.
