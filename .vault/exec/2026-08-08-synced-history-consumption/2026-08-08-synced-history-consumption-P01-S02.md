---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:bc6902d3591c55ef8397dde2891bcd8b5d58d6a5f5200f4adc441facb2be21bc'
step_id: 'S02'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Prove the consumption rather than assuming it, in the direction S01 measured

## Scope

- `src/cadrumo/application/calculations/tests`

## Description

- Read the nearest existing analogue, the live Modelo 100 pagos-fraccionados
  fold-in test, in full before authoring, and reuse its persona and
  zero-defaulting shape rather than inventing a second one.
- Choose Modelo 100 casilla 0604 as the channel: the census marks it reachable,
  it is not the IVA wallet, and its Modelo 130 feeder declares a
  filed-declarations read surface.
- Build the history pole from synthetic AEAT declarations-register rows pushed
  through the production pull persistence function, so the persisted provenance
  is the one the real pull stamps rather than a hand-chosen source kind.
- Run both poles through the live operator calculate path over one
  law-resolved revision and assert the revision ids agree before comparing.
- Prove the comparison bites with an out-of-repo mutation that installs the
  provenance filter the research document assumed exists.

## Outcome

The step's stated expectation is FALSIFIED, and the regression records the
opposite of what the row was written to prove.

The row asked for a regression showing that a profile whose AEAT history was
pulled produces the same engine output as a profile with no history at all,
expected RED on landing. The census established, and this step confirms by
execution, that the two do NOT agree on a reachable channel. The regression
therefore asserts DIVERGENCE and lands GREEN. It is stated plainly here rather
than rewritten into an equality the tree does not exhibit.

What runs: two real calculations of the annual Modelo 100 over the same
law-resolved revision, differing only in whether the AEAT filing history was
pulled. The no-history pole produces NO value for casilla 0604 and names the
unresolved relation on the diagnostics channel. The pulled-history pole produces
1416.00, the sum of the four quarters the synthetic register rows carry.

Neither expected figure is derived from the formula under test. The no-history
pole expects an ABSENCE, for which no formula can produce a number. The
pulled-history pole expects the sum of values this module chose as inputs to the
run and wrote into the register rows, which is an input, not an output read back.

A positive control on the write half asserts the pull actually landed four
distinct observation keys with `ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE`
provenance carrying the expected casilla values, so a history pole that silently
persisted nothing cannot masquerade as a passing comparison.

## Verification

    uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_pulled_history_reaches_calculate.py -n0 -q
    3 passed in 22.52s

Mutation proof, loaded with `-p` from a directory outside the repository so no
tracked file changed. The mutation makes the observation read path return `None`
for any payload whose provenance is official AEAT — exactly the filter the
research document assumed already exists:

    PYTHONPATH=<scratch> uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_pulled_history_reaches_calculate.py -n0 -q -p mutate_pull_provenance -s
    MUTATION APPLIED: holder confirmed on cadrumo.application.calculations._observations_repository.CalculationObservationRepository.load_observation
    2 failed, 1 passed in 22.98s

The holder confirmation is asserted, not printed: the plugin reads the function
out of the class `__dict__` and raises if it is absent, so a no-op rebinding
cannot print APPLIED and let every assertion pass unchanged. It also re-reads the
attribute after rebinding and raises if it still resolves to the original.

The two mutated failures are the right two, with the right messages:

    E   AssertionError: the pull must have landed M130 2024/1T
    E   AssertionError: the pulled-history pole must produce an annual pagos credit; the pull persisted 4 register rows and the credit is still absent

The third test — the no-history pole — correctly still PASSES under the mutation.
That is the negative control: a mutation that reddened all three would be
blanket rather than targeted, and would not show that the divergence is
attributable to the provenance the pull stamps.

Neighbouring modules, run sequentially:

    uv run --no-sync pytest <this module> test_modelo_100_multiyear_renta_enrollment.py test_relation_prefill_source_mesh.py ../../live/tests/test_filed_capture_calculation_history.py -n0 -q
    62 passed in 53.83s

Static gates on the new file:

    uv run --no-sync ruff format --check <file>   ->  1 file already formatted
    uv run --no-sync ruff check <file>            ->  All checks passed!
    uv run --no-sync pytest src/cadrumo/tests/test_import_hygiene_gate.py -n0 -q  ->  19 passed

The repository type check and the import-linter run are both red on peer
surfaces, and neither names this module: `dev.quality.types` reports 203
diagnostics with zero occurrences of this file, and `lint-imports` reports one
violation, `cadrumo.application.ledger.tests.test_invoice_extraction_authority ->
cadrumo.llm`. The relative-import check reports 4 violations, all in
`domain/invoices` and `domain/iva`, none here.

## Notes

INCIDENT, peer sweep. This module was authored, iterated and tested as an
untracked working-tree file, and before it could be committed under its own
subject it was swept into HEAD by a peer's bare whole-index commit
`a629434f9eae7a2e243dc62c1e35b8749c21c444`, subject "feat(cadrumo): land the
in-flight source work", at 2026-08-08 08:49 +0200, as a 384-line addition.
Nothing was lost: the swept content is byte-identical to the working copy and
carries the final tested helper, verified by an empty `git diff HEAD` for the
path and by grepping the HEAD blob for the corrected return. No corrective git
action was taken and none is appropriate. This record is the durable attribution.

WHAT THIS DOES NOT ESTABLISH, written beside the completion rather than left
implicit. The row's standing intent is to establish whether a synced history is
silently unconsumed. This step answers that for ONE channel and answers it "no".
It does not establish that no channel is silent. The census found 9 carry slots
whose every feeder modelo the declarations register does not serve — 5 on Modelo
200 and 4 on Modelo 202 — and those ARE silent in exactly the way the campaign
was opened to investigate: a Sociedades filer's prior pagos fraccionados and
prior-year bases cannot arrive by pull at all, and the absence presents as a
plausible figure rather than a refusal. Nothing in this step tests them, and a
regression over them cannot be written the same way, because there is no pull to
drive the history pole with. That residue is opened as its own row rather than
left as a note here.

The row's text was amended by its owner while this step was in flight, after the
falsification was reported, and now asks for the divergence test this step built
— including the mutation direction, that the two runs CAN be made equal. The work
was authored against the original wording and was not retrofitted to the
amendment; the two happen to agree. The original expectation is recorded above as
falsified rather than quietly rewritten, which the amended row also requires.
