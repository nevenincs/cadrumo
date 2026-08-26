---
tags:
  - '#plan'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-08'
body_hash: 'sha256:62fb40f36492bfdb45d87b4975d64db3737cd51526a9ce2e78f6fc927b129bc5'
tier: L2
related:
  - '[[2026-08-07-justificante-identity-matching-adr]]'
  - '[[2026-08-07-justificante-identity-matching-reference]]'
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
predicate's signature entirely rather than merely re-documented. The PRIMARY
protection against a cross-filing artefact mis-pairing was always the
row-scoped Playwright fetch (`_row_locator_for_expediente`), not the
predicate; this plan also hardens that locator from a substring to an exact
`expediente_id` match, since it becomes the sole mechanism once the
predicate's wrong-namespace re-check is gone. `P01` lands the domain and
application fixes plus their tests, including a mutation-proof regression for
the CSV check's defense-in-depth role against a wrong-artefact-selection bug;
`P02` closes the swallowed-outcome observability gap.

## Steps

### Phase `P01` - Correct the presentation_id namespace at each call site

Promote the shared CSV-extraction helper, harden the row-scoped locator to an exact match, drop the wrong-namespace argument at the two already-guarded call sites, add the missing csv defense-in-depth check at the third rather than dropping it check-less, remove the now-unusable presentation_id parameter, and prove the fix with the corrected pinning test, a real-fixture regression, an exact-match locator test, and a mutation-proof two-filings-per-period discrimination test.

- [x] `P01.S11` - Confirm extract_csv_from_url already resolves through the sede package public facade before landing S01, promoting it only if a fresh HEAD read shows it missing; `src/cadrumo/adapters/outbound/aeat/sede/__init__.py`.
- [x] `P01.S13` - Harden the row-scoped locator to an exact expediente_id match instead of a substring filter, reusing the existing re import rather than a second selection idiom, with a test proving it cannot match a second row whose id merely contains the target as a substring; `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py (_row_locator_for_expediente)`.
- [x] `P01.S01` - Add a csv-equality check recovering the CSV from the justificante_pdf artefact source_url via extract_csv_from_url, fold a resolution failure into the existing swallowed-outcome shape, and drop the now-signature-invalid expediente_id argument in the same change; `src/cadrumo/application/live/_filed_observation_persistence.py`.
- [x] `P01.S02` - Drop the now-signature-invalid expediente_id argument now that register_capture_justificante_metadata's existing csv equality check already covers identity; `src/cadrumo/application/live/_justificante.py (_justificante_matches_capture_axis)`.
- [x] `P01.S03` - Drop the now-signature-invalid expediente_id argument now that register_capture_as_filing_evidence's existing csv equality check already covers identity; `src/cadrumo/application/live/_justificante.py (register_capture_as_filing_evidence)`.
- [x] `P01.S04` - Remove the presentation_id parameter entirely from matches_filing_target and its three now-dead pass-through wrapper parameters; `src/cadrumo/domain/justificante/_schema.py, src/cadrumo/application/live/_justificante.py, and src/cadrumo/application/live/_filed_observation_persistence.py`.
- [x] `P01.S05` - Update the pinning test to the corrected signature and matching behavior and remove the fixture's false expediente-as-presentation_id equivalence, landing in the SAME commit as S04 because a parameter removal published without its consumer sweep is a TypeError on a clean checkout; `src/cadrumo/domain/justificante/tests/test_filing_target.py`.
- [x] `P01.S06` - Add a real-fixture regression proving the register-reconciliation path enrolls a committed M303 justificante via the new csv-equality check; `src/cadrumo/application/live/tests/_filed_capture_history_support.py and a new or existing test in src/cadrumo/application/live/tests`.
- [x] `P01.S12` - Add a mutation-proof test proving the new csv defense-in-depth check discriminates two same-period filings sharing modelo, ejercicio, period and tax_id, confirming a wrong-artefact-selection bug would be caught even though the row-scoped fetch is the primary binding; `src/cadrumo/application/live/tests`.
- [x] `P01.S07` - Run the domain and application justificante test suites and confirm green; `src/cadrumo/domain/justificante/tests and src/cadrumo/application/live/tests`.

### Phase `P02` - Distinguish swallowed justificante-matching outcomes

Surface a Notice distinguishing all six swallowed outcomes at the register-reconciliation site (unreadable artefact, manifest mismatch, unparsable PDF, CSV-resolution failure, CSV mismatch, filing-target mismatch) so an operator can see why a capture produced no evidence.

- [x] `P02.S08` - Distinguish all six swallowed outcomes (unreadable artefact, manifest mismatch, unparsable PDF, CSV-resolution failure, CSV mismatch, filing-target mismatch) and return a typed reason instead of returning None uniformly; `src/cadrumo/application/live/_filed_observation_persistence.py (_parse_matching_filed_justificante)`.
- [x] `P02.S09` - Emit a Notice through the shared envelope spine naming the unreached-evidence reason when an enrollment call finds an artefact but saves nothing; `src/cadrumo/application/live/_filed_observation_persistence.py (persist_filed_justificante_metadata and enroll_filed_justificante_evidence)`.
- [x] `P02.S10` - Add a mutation-proof test confirming the reason-distinguishing branch fires per swallowed case and confirm the CLI report surfaces the Notice; `src/cadrumo/application/live/tests and src/cadrumo/entrypoints/cli/tests`.
- [x] `P02.S14` - Narrow the application-layer relay test's name and docstring to what its assertions actually prove. It constructs the advisories onto the run model and reads them back off the same object, so it is a pydantic storage roundtrip that cannot fail when the CLI forwarding is deleted, while its name and docstring both claim to cover the relay. The fold itself is now covered at the transport boundary, so this is a truthfulness repair rather than a coverage gap. Gate: the renamed test still derives its expected set from the enum, and a reader can tell from the name alone that it proves the taxonomy has members and the model stores one advisory per member, not that anything reaches an operator; `src/cadrumo/application/live/tests/test_filed_history_onboarding.py`.

## Parallelization

`P01.S11` (facade promotion) must land first; `P01.S01` depends on it, because
`_filed_observation_persistence.py` cannot import `extract_csv_from_url`
before it is exported. `P01.S13` (locator hardening) touches
`_declarations.py` only and has no dependency on `S11`; it may run in
parallel with `S11`/`S01`. `P01.S02` and `P01.S03` touch a disjoint file and
have no dependency on `S11`/`S01`/`S13`; they may run in parallel with each
other and with `S01`/`S13`. `P01.S04` (removing the `presentation_id`
parameter) depends on
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
the pre-fix four swallowed outcomes and miss the two `P01.S01` introduces
(`CSV_MISMATCH` and `CSV_UNRESOLVABLE`) plus the pre-existing
`FILING_TARGET_MISMATCH` this plan's earlier draft had also omitted from its
own count — six total. Before
`P01.S05` begins, re-check whether the parallel-authored pinning test
mentioned in the ADR's Constraints has landed elsewhere in the tree; if so,
absorb and update that test in place rather than authoring a second one, per
`aeat-agent-orchestration`'s in-scope-regression mandate. `P01.S11` closed
against `extract_csv_from_url` already resolving through the facade — an
earlier draft of this plan credited that to a peer's independent change; it
was in fact the `S11` executor's own uncommitted edit, carried into HEAD by
a broad tree-wide sweep before this plan's review pass read it back and
misattributed it. Every implementing row in this plan touches a shared,
actively-contended worktree: commit each landed row with an explicit
pathspec (never a bare `git commit`), and verify what was actually committed
with `git show <sha> --numstat` after, not a pre-commit `git diff --cached`
(TOCTOU), per `aeat-worktree-safety`.

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
- `P01.S13`'s locator test proves `_row_locator_for_expediente` does NOT
  match a synthetic second row whose `expediente_id` contains the target id
  as a substring, and fails against the pre-hardening substring filter.
- `uv run --no-sync pytest src/cadrumo/domain/justificante/tests
  src/cadrumo/application/live/tests -m unit` (sequential, per
  `aeat-local-execution`) is green with the full log captured to a file, not
  piped through a truncating filter.
- Every mutation-proof test in this plan (`P01.S12`, `P02.S10`) is confirmed
  to run with `pytest-xdist` disabled (`-n0`), checking for a project
  `addopts` default injecting `-n auto` first — an un-forced proof under
  xdist is vacuous since worker processes never see an in-memory mutation
  performed by the test process.
- The `P02.S10` mutation-proof test fails when the reason-distinguishing
  branch is reverted to the uniform `logger.warning` plus `return None` shape,
  and passes against the corrected code.
- No legal-catalogue entry is added or modified by this plan.

- Closeout run at the plan's actual final state, after every row including
  `P02.S10` and `P02.S14` had landed, sequential and unfiltered so no marker
  lane could hide a module:

      uv run --no-sync pytest src/cadrumo/domain/justificante/tests
      src/cadrumo/application/live/tests
      src/cadrumo/entrypoints/cli/tests/test_app_live_filed_notice_relay.py -n0 -q
      324 passed, 2 deselected in 103.60s (0:01:43)

  An earlier attempt at this same run reported 48 failures, every one of them a
  single cause outside this plan: a peer's corpus hydration was mid-landing, so
  a bundled consolidated-law HTML file existed without its extracted sidecar and
  the legal catalogue refused, which reds every registry-loading test. A second
  reported cause, a construct missing a legal ref, came from a CACHED validation
  failure list and did not exist at HEAD. Both cleared once the sidecar landed.
  Recorded because a closeout that had accepted those 48 as its own would have
  either falsely blamed this plan or, worse, been "fixed" by editing another
  campaign's registry files.
- NOT verified in the closing session: the bullet above asserting that the
  `P02.S10` mutation-proof test fails when the reason-distinguishing branch is
  reverted to the uniform warn-and-return-None shape. The mutation actually run
  for `P02.S10` rebound the run model's advisory channel to empty, which proves
  the CLI transport forwards it; it does not exercise the branch revert. The
  branch-level claim may have been proven when `P02.S08` and `P02.S09` landed,
  but this session did not re-run it and does not assert it.
