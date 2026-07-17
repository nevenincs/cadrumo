---
tags:
  - '#audit'
  - '#m184-socio-attribution-handoff'
date: '2026-07-09'
modified: '2026-07-17'
related:
  - '[[2026-07-09-m184-socio-attribution-handoff-adr]]'
  - '[[2026-05-26-cross-domain-continuity-plan]]'
---

# `m184-socio-attribution-handoff` audit: `m184 socio-attribution slice honesty review`

## Scope

Fresh-context campaign-close honesty review of the m184 socio-attribution slice
(plan steps `W09.P41.S411`-`S414` plus the tracking pointer `S397`), run before
the slice is declared structurally complete per the campaign-close honesty-review
discipline. Every artefact was re-read at HEAD: the decision addendum ADR, the
`attribution_received` profile schema fact group, the casilla 1577 bindings on the
2024 and 2025 M100 revisions, the per-socio handoff Notice, the M100 omission
advisory, and their tests.

**Verdict: PASS** — no CRITICAL or HIGH findings; the slice is merge-safe. The
slice is rule-clean on its load-bearing axes: legal grounding is corpus-verified
and non-fabricated, casilla 1577 is single-bound (no dual-modelling), the advisory
is real-behaviour and anti-tautology tested, the handoff Notice is correct
per-socio, and the exec records honestly disclose their scope deviations. The
findings below are honesty/wording and localization improvements, not safety or
correctness defects.

## Findings

### per-lens-summary | info | seven-lens verdict

Grounding honesty PASS (arts 86-89 LIRPF present in `legal/irpf.toml` with
`corpus_ref`/`required_text` cross-check, `review_status = reviewed`; advisory sums
`base_imponible_attributed` directly and never derives base from `share_pct`, which
the schema field description explicitly forbids; casilla 1577 keeps its actividades
grounding correctly per art-88). Dual-modelling PASS (1577 carries exactly one
binding, `source = relation_prefill` on 2025, `input_kind = informational` unbound on
2024; no `source = profile` binding authored; S412 supersession held). Silent
under-declaration PARTIAL (Finding 1). Handoff Notice PASS (one INFO Notice per
`Modelo184MemberRow`, exact importe, exact `--binding 1577={importe}` suggestion,
silent without member rows, wired into both `work verify` and `work file`). Test
integrity PASS (real-behaviour, no mocks/skips/xfail; anti-tautology flips one input
at a time). Provenance parity mostly PASS (Finding 3). Closure honesty mostly honest
(Findings 1 and 5).

### fully-forgotten-socio-overclaim | medium | ADR Consequences and S414 step overclaim omission-advisory coverage

The advisory's omission trigger requires `attribution_received` facts to be present
to fire (`facts_present and not casilla_has_value`). A socio who forgets the
attributed share entirely — captures no facts and folds nothing into 1577 — hits the
both-absent branch and receives zero findings. That is precisely the hazard the ADR
Considerations name, yet the ADR Consequences asserts the forgotten-share silent
under-declaration becomes a visible advisory, and the S414 step claims the advisory
prompts capture when an SC-membership signal exists with no facts. Neither is
delivered: there is no SC-membership signal on a socio's `natural_person` profile
independent of `attribution_received`, and the implemented second trigger is a
different case (casilla-present/no-facts, a provenance check). Failure scenario: a
comunero receives a real attributed base, never touches the app's attribution facts,
calculates M100, verify grants clean with no atribución finding, files under-declared.
Bounded by design: this residual is an accepted consequence of the no-cross-bucket
constraint (Option A deferred behind a future security ADR) and is no regression (the
pre-slice state was equally silent). The defect is the overclaiming prose, not missing
required code — the addendum decision (a) required only the facts-present trigger,
which was built.

### operator-surfaces-not-localized | medium | new handoff Notice and advisory are hardcoded strings, ADR locale-discipline constraint unmet

The ADR Constraints state that all new prompts/advisories route through `tr()` and the
locale CLI across en/es/ca/hu. Both new surfaces (the handoff Notice message in
`_modelo_rendering.py` and the advisory message plus next_action in
`_attribution_received_advisory.py`) are hardcoded English/Spanish literals with no
`tr()` keys. The sibling `_dt12_advisory.py` and `_art20_advisory.py` do route through
`tr()`; the newer `_objective_estimation_advisory.py` is hardcoded, so convention is
mixed — but the ADR explicitly committed these two surfaces to localization. Failure
scenario: a Catalan or Hungarian operator receives Spanish-English handoff and advisory
prose; a future locale-parity/honesty gate cannot ratchet strings it cannot see.

### manual-fold-drops-atribucion-provenance | low | manual --binding 1577 fold drops the atribución 86-89 refs on the persisted observation

The documented cross-bucket transport is a manual `--binding 1577=<importe>` override,
which bypasses the relation binding. The resulting bound-casilla observation is grounded
in the casilla's own `legal_refs` (actividades chapter plus orden-hap art-3) but not the
atribución mechanism refs (arts 86-89) that only the relation binding carries. Arts 86-89
then live only in the transient Notice/advisory text, not on the persisted value — a mild
asymmetry against the relation path, which persists 86-89. Low priority; the casilla
grounding is itself correct.

### advisory-bucket-load-branch-untested | low | advisory load-from-bucket production branch is untested

Every advisory test passes `profile_record=` explicitly, so the production path
(`UserProfileLifecycleRepository(bucket_id=...).load(...)` plus the `ProfileNotFoundError`
guard) and the surfacing of the advisory through a real `work verify` run are never
exercised. A wrong load signature or a swallowed error would pass CI.

### plan-body-vs-exec-deviation | low | S411/S412 plan-body text differs from what landed (disclosed in exec, not plan)

S411 is checked with text promising wizard/edit capture prompts and en/es/ca/hu locale
keys — none exist (capture is schema-generic; no locale keys). The S411 exec record
honestly discloses this deviation and tracks a follow-up, satisfying the
plan-closure-requires-exec-records rule. S412 is checked as SUPERSEDED with no dedicated
exec record (documented inline plus ADR addendum). Both are acceptable per the rule, but
the plan-body text reads as delivered-in-full.

## Recommendations

- Finding 1 (correct the overclaim): amend the ADR Consequences bullet and the S414 step
  text to state that the fully-forgotten case (no facts plus empty casilla) remains
  uncovered on the socio bucket, and name the closure path (Option A cross-bucket
  auto-flow, or the 2024 relation-symmetry follow-up). Optionally strengthen the S413
  M184-side handoff so the sociedad-civil operator is the unambiguous loud channel for the
  fully-forgotten socio. Verification gate: the amended prose names the residual explicitly
  and no code path claims coverage it does not deliver.
- Finding 2 (localize or honestly defer): move the handoff Notice message and the two
  advisory messages/next_actions to `tr()` keys via the locale CLI across en/es/ca/hu,
  matching the `_dt12_advisory` pattern; or fold these strings into the existing
  attribution locale follow-up (task #204) and correct the ADR locale-discipline prose to
  say localization is deferred to that follow-up rather than delivered inline. Verification
  gate: either the strings resolve through `tr()` with four-locale parity green, or the ADR
  records the deferral and #204 scope names these two surfaces.
- Finding 3 (LOW): consider carrying the atribución `legal_refs` onto the manually-folded
  1577 observation, or document that the casilla's actividades grounding is the accepted
  persistent grounding and 86-89 rides the advisory only.
- Finding 4 (LOW): add one integration test that seeds `attribution_received` facts on a
  real bucket profile and asserts the advisory appears in the verify report findings, plus
  one asserting `ProfileNotFoundError` yields no finding.
- Finding 5 (LOW): optionally annotate the S411 step body with the schema-generic-capture
  caveat so the plan matches the exec record; confirm the S412 supersession is captured in
  the close audit (it is, in the ADR addendum).
