---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:71ebaf487fc88475b0db03f5440f2a8484db3582115e970d81029efd593cfa7c'
step_id: 'S35'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
# MEASUREMENT row. Partition the error-registry entries carrying no default_suggestion into operator-reachable and internal-only by reading each entry's raise sites. Measured when S13 landed: 377 of 606 entries carry no suggestion, 62 percent. That count is NOT itself a defect, because an entry an operator can never reach correctly carries none, which REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED demonstrates by firing only under pytest, where suggesting the opt-in environment variable would have armed real AEAT access. The open question is therefore not why 377 lack suggestions but how many of them an operator can actually reach. That is decidable per entry by reading raise sites, as S13 did for ERROR_APPLICATION_LIVE by finding all seven of its direct raises inside stages the history sweep sequences, but nothing in the tree records which side any entry falls on, so it is worth measuring once rather than rediscovering per row. A suggestion that MISDIRECTS is worse than none, because the agent-operator this CLI targets follows it, which is why declining FAIL_SNAPSHOT_NOT_FOUND was correct: a filed-specific citation on a base shared with borrador and deudas would misdirect their misses. The output is a classified inventory plus a per-entry decision, never a blanket sweep adding suggestions to 377 entries. Gate: the partition is total over the suggestion-less set with a stated justification recorded per entry for the side it lands on, gated on totality and per-entry justification rather than on any count, and the suggestion-command conformance test stays green for every suggestion added. Scope-adjacent to history-onboarding rather than native to it, and lives here for provenance because S13 surfaced it

## Scope

- `src/cadrumo/core/errors/registry`

## Description

- Enumerated the suggestion-less entries from the live registry rather than by reading files, and resolved each to its declared exception qualname, since binding is per-qualname and a base class never raised directly can never render its own entry.
- Scanned every shipped module for raise sites, resolving each module's local names back to the declared class so a raise made through an aliased import is not invisible.
- Classified the guard on every raise site by whether its enclosing function can only be entered by a non-operator context.
- Landed the classification as a gate rather than a document, so the partition is re-derived every run and the reviewed set of undecided reachable refusals fails when it changes in either direction.
- Authored no suggestion, per the row.

## Outcome

The partition is total with no remainder, over 376 suggestion-less entries of 606 and 1534 shipped modules scanned. It falls out as 109 with no direct raise site, 2 raised only behind a non-operator guard, 262 operator-reachable, and 3 whose class shares a short name with another declared error and which are reported rather than guessed at.

The headline is that 70 percent are reachable, so the reachable-versus-internal split does not explain the silence. Reading it the other way is the useful result: of the reachable ones, only the refusal categories are operator-actionable by construction, which is 69 entries. An ERROR, FAIL, INTEGRITY or INTERNAL entry reports a defect or a corruption, where a run-this-next line is frequently not the honest answer. So the set warranting an authoring decision is 69, not 376, and the difference between those two numbers is the whole value of measuring rather than sweeping.

The no-raise-site bucket has a coherent explanation rather than being noise. Roughly half its members, 50 of 109, are family ROOTS that exist to be subclassed and are never raised themselves. Since binding is per-qualname, such a root can never emit its own code, so its missing suggestion is correct and not a gap. The remaining 59 are leaves with no direct raise site, of which 20 are constructed somewhere in shipped code and so may be raised indirectly through a variable. That leaves a residue of entries that nothing appears able to emit, which is a finding this row surfaces rather than resolves.

The row's own denominator moved during the campaign and it is worth stating rather than quietly reconciling: the measurement was 377 when the sibling error-registry row began and is 376 now, because that row authored the one suggestion it found justified. The gate derives the set live, so it cannot drift the way a recorded number would.

What the row asks that this does not deliver. The 69 reachable refusals carry one shared recorded reason, that an operator hits them and is told nothing, rather than 69 individually argued ones. Deciding each on its merits is the authoring work the row explicitly defers, and inventing 69 distinct justifications now would be prose asserting a review that did not happen. The standing goal still asks for a per-entry decision across that set. What the gate guarantees today is narrower and honest: the set cannot grow silently, because a newly reachable refusal fails until somebody decides.

Two instrument defects were found and corrected before the numbers were trusted, and both moved the answer. Production imports around forty error classes under an alias, so a bare short-name match missed every raise made through one and inflated the no-raise-site bucket by two entries. And two short names are each shared by two declared codes, so a site matched on the short name alone was cross-attributed between them; those are now reported as their own outcome instead of being assigned to a side.

One approach was measured and rejected rather than assumed. Reachability was first attempted as an import-closure question by executing the live CLI tree build and recording which modules loaded. Only 198 of 1534 modules load at tree-build time, because command bodies import lazily, so that closure under-approximates reachability badly and would have misclassified most genuinely reachable entries as undetermined. The guard on the raise site is the discriminator the row actually names, and it is the one used.

## Verification

    uv run --no-sync pytest -n0 -q src/cadrumo/core/errors/tests/test_suggestionless_reachability.py
    5 passed in 13.36s

    uv run --no-sync pytest -n0 -q src/cadrumo/core/errors/tests/
    47 passed in 67.52s

    uv run --no-sync pytest -n0 -q src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py -m integration
    12 passed in 35.99s

Three controls were chosen before the classifier ran, each with a known expected side, and all three landed where independent reasoning had already put them. The live-read access gate classified as non-operator-guarded, matching the finding that it fires only under pytest. The shared snapshot-not-found base classified as having no direct raise site, which strengthens the earlier decision to decline it: not only would a filed-specific citation have misdirected a borrador or deudas miss, that base can never emit its code at all. And the live application error correctly reported as no longer in the suggestion-less set, since the sibling row gave it one, which is a change-detection control rather than a static one.

Two mutation proofs, both from pytest plugins resident OUTSIDE the repository, each asserting its target was present before rebinding and asserting the rebinding took, printing that the mutation was applied and the holder found. No tracked file was edited to perform either.

Removing one reviewed entry, simulating a reachable refusal nobody has decided about:

    1 failed, 4 passed in 7.99s
    AssertionError: operator-reachable refusal(s) reach an operator with no next step and nobody has decided about them: ['REFUSED_NO_ACTIVE_PROFILE']

Blinding the guard detector so it recognises no non-operator token:

    4 failed, 1 passed in 9.31s

That second mutation reddens the non-degeneracy check, the synthetic detector proof, the fixture anchor and the reviewed-set gate together, which is the correct blast radius: a blind detector reclassifies the guarded entries as reachable. The one test that stayed green under it is the totality check, and that is also correct and worth recording, because totality survives misclassification. Totality alone would therefore have been a decorative gate, which is why the other four exist.

Type and lint gates: ty check reported all checks passed, ruff format left the module unchanged, ruff check clean.

## Notes

Nothing here asserts a count as a pass condition. The reviewed set is gated on its identity, so it fails in both directions, and the message on each side tells the reader what to do. A tally would have needed editing on every legitimate change until nobody read it.

No suggestion was authored, per the row and the dispatch. The row's standing warning is carried into the gate's own failure message: never add one that misdirects, because the agent-operator this CLI targets follows it.

Separately, a side effect worth recording rather than hiding. Running the modified-stamp check unscoped, without the fix flag, re-attested the body fingerprint of two exec records belonging to another feature. Their bodies are unchanged against the committed version, so the run corrected a stale fingerprint those documents already carried rather than altering any content. They were left dirty and untouched rather than committed or reverted, since overwriting a peer's working copy would risk more than the harmless difference it would remove. The lesson is that the check verb writes even without the fix flag, so it must be scoped by feature.
