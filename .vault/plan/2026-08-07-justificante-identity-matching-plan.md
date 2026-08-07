---
tags:
  - '#plan'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:66a6483269a8c8e81afc98ffa4dcdf91c3a65fd71a73f920590f0a7c3fefd500'
tier: L2
related:
  - '[[2026-08-07-justificante-identity-matching-adr]]'
---

# `justificante-identity-matching` plan

## Description

Executes `2026-08-07-justificante-identity-matching-adr`. Three sites pass a
register-sourced `expediente_id` into `Justificante.matches_filing_target`'s
`presentation_id` parameter; two of the three already sit behind a genuine,
independent `csv == csv` check their callers run beforehand, so the
wrong-namespace argument at those two is dropped as strictly subtractive. The
third site has no such check today, but its CSV is independently resolved
during artefact capture and then discarded rather than persisted, and is
fully recoverable from an existing field (`FiledDeclaracionArtefact.source_url`)
via the existing canonical `extract_csv_from_url` helper — so that site GAINS
a `csv == csv` check in the same change that drops its wrong-namespace
argument, never landing in a weaker intermediate state. Once every site
performs its own CSV check, `matches_filing_target`'s `presentation_id`
parameter has no remaining valid caller anywhere, so it is removed from the
predicate's signature entirely rather than merely re-documented. `P01` lands
the domain and application fixes plus their tests, including a mutation-proof
regression for the two-filings-per-period hazard the added check exists to
catch; `P02` closes the swallowed-outcome observability gap.

## Steps

### Phase `P01` - Correct the presentation_id namespace at each call site

Promote the shared CSV-extraction helper, drop the wrong-namespace argument at the two already-guarded call sites, add the missing csv check at the third rather than dropping it check-less, remove the now-unusable presentation_id parameter, and prove the fix with the corrected pinning test, a real-fixture regression, and a mutation-proof two-filings-per-period discrimination test.

- [ ] `P01.S11` - Promote extract_csv_from_url into the sede package public facade; `src/cadrumo/adapters/outbound/aeat/sede/__init__.py`.
- [ ] `P01.S01` - Add a csv-equality check recovering the CSV from the justificante_pdf artefact source_url via extract_csv_from_url, fold a resolution failure into the existing swallowed-outcome shape, and drop the now-signature-invalid expediente_id argument in the same change; `src/cadrumo/application/live/_filed_observation_persistence.py`.
- [ ] `P01.S02` - Drop the now-signature-invalid expediente_id argument now that register_capture_justificante_metadata's existing csv equality check already covers identity; `src/cadrumo/application/live/_justificante.py (_justificante_matches_capture_axis)`.
- [ ] `P01.S03` - Drop the now-signature-invalid expediente_id argument now that register_capture_as_filing_evidence's existing csv equality check already covers identity; `src/cadrumo/application/live/_justificante.py (register_capture_as_filing_evidence)`.
- [ ] `P01.S04` - Remove the presentation_id parameter entirely from matches_filing_target and its three now-dead pass-through wrapper parameters; `src/cadrumo/domain/justificante/_schema.py, src/cadrumo/application/live/_justificante.py, and src/cadrumo/application/live/_filed_observation_persistence.py`.
- [ ] `P01.S05` - Update the pinning test to the corrected signature and matching behavior, and remove the fixture's false expediente-as-presentation_id equivalence; `src/cadrumo/domain/justificante/tests/test_filing_target.py`.
- [ ] `P01.S06` - Add a real-fixture regression proving the register-reconciliation path enrolls a committed M303 justificante via the new csv-equality check; `src/cadrumo/application/live/tests/_filed_capture_history_support.py and a new or existing test in src/cadrumo/application/live/tests`.
- [ ] `P01.S12` - Add a mutation-proof test proving the new csv check discriminates two same-period filings sharing modelo, ejercicio, period and tax_id, confirming the four-field match alone cannot; `src/cadrumo/application/live/tests`.
- [ ] `P01.S07` - Run the domain and application justificante test suites and confirm green; `src/cadrumo/domain/justificante/tests and src/cadrumo/application/live/tests`.

### Phase `P02` - Distinguish swallowed justificante-matching outcomes

Surface a Notice distinguishing all five swallowed outcomes at the register-reconciliation site (unreadable artefact, manifest mismatch, unparsable PDF, CSV-resolution failure, CSV mismatch) so an operator can see why a capture produced no evidence.

- [ ] `P02.S08` - Distinguish all five swallowed outcomes (unreadable artefact, manifest mismatch, unparsable PDF, CSV-resolution failure, CSV mismatch) and return a typed reason instead of returning None uniformly; `src/cadrumo/application/live/_filed_observation_persistence.py (_parse_matching_filed_justificante)`.
- [ ] `P02.S09` - Emit a Notice through the shared envelope spine naming the unreached-evidence reason when an enrollment call finds an artefact but saves nothing; `src/cadrumo/application/live/_filed_observation_persistence.py (persist_filed_justificante_metadata and enroll_filed_justificante_evidence)`.
- [ ] `P02.S10` - Add a mutation-proof test confirming the reason-distinguishing branch fires per swallowed case and confirm the CLI report surfaces the Notice; `src/cadrumo/application/live/tests and src/cadrumo/entrypoints/cli/tests`.

## Parallelization

`P01.S11` (facade promotion) must land first; `P01.S01` depends on it, because
`_filed_observation_persistence.py` cannot import `extract_csv_from_url`
before it is exported. `P01.S02` and `P01.S03` touch a disjoint file and have
no dependency on `S11`/`S01`; they may run in parallel with each other and
with `S01`. `P01.S04` (removing the `presentation_id` parameter) depends on
`S01`, `S02`, and `S03` all landing first — removing the parameter while any
caller still passes it would break that caller's own build, so `S04` is a
hard convergence point, not a parallel row. `P01.S05` and `P01.S06` depend on
`S04` closing, since both assert against the narrowed signature and the
corrected matching behavior. `P01.S12` (the two-filings-per-period
mutation-proof test) depends specifically on `S01`'s CSV check landing, since
it is a regression against that exact check. `P01.S07` gates the Phase closed
and must run last within `P01`. `P02` depends on `P01` closing first: the
reason-distinguishing branch in `P02.S08` reads the same predicate call site
`P01.S01` corrects, so building it before `P01.S01` lands would encode only
the current four swallowed outcomes and miss the fifth (CSV mismatch) that
Phase `P01` introduces. Before
`P01.S05` begins, re-check whether the parallel-authored pinning test
mentioned in the ADR's Constraints has landed elsewhere in the tree; if so,
absorb and update that test in place rather than authoring a second one, per
`aeat-agent-orchestration`'s in-scope-regression mandate.

## Verification

- Every Step in this plan is closed (`- [x]`).
- `src/cadrumo/domain/justificante/tests/test_filing_target.py` asserts the
  corrected matching behavior against the narrowed signature (no assertion
  still encodes `presentation_id == expediente_id` as valid, and no test
  passes a `presentation_id` keyword the predicate no longer accepts) and
  passes.
- The `P01.S06` real-fixture regression passes and would fail if `P01.S01`
  were reverted (proven by a deliberate revert-and-confirm-red pass before the
  final commit, per `aeat-quality-gates`' "a gate is unproven until it
  bites").
- The `P01.S12` mutation-proof test fails when `P01.S01`'s CSV check is
  reverted to comparing only `modelo`/`filing_year`/`period`/`tax_id`, and
  passes against the corrected code — this is the concrete proof that no site
  ends this plan checked more weakly than it started, per the ADR's
  Constraints.
- `uv run --no-sync pytest src/cadrumo/domain/justificante/tests
  src/cadrumo/application/live/tests -m unit` (sequential, per
  `aeat-local-execution`) is green with the full log captured to a file, not
  piped through a truncating filter.
- The `P02.S10` mutation-proof test fails when the reason-distinguishing
  branch is reverted to the uniform `logger.warning` plus `return None` shape,
  and passes against the corrected code.
- No legal-catalogue entry is added or modified by this plan.
