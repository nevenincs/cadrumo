---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1da6dfe0c64dcfd676f4476b1782e2e23e081a37d694e4223db7801eff2e7701'
step_id: 'S03'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Promote EvidenceInput to the application.ledger public facade as a precondition of any consuming change

## Scope

- `src/cadrumo/application/ledger/__init__.py`

## Description

- No code was written for this Step. It was found already satisfied at HEAD and closed by verification against the Step's own specification rather than re-landed.
- Confirmed the promotion is complete across all four surfaces the package's export pattern requires: the lazy attribute map, the `__all__` list, the type-checking import block, and the module docstring's inventory of exported types.
- Confirmed it follows the package's existing lazy resolution pattern rather than introducing an eager import beside it.
- Confirmed both gates the Step names exist, and ran the consumer-import one.

## Outcome

Delivered by a prior commit, verified here. As with the sibling taxonomy Step, this is a closure by verification rather than implementation, recorded as such so the row does not read as work this lane performed.

The Step's premise is worth restating because it is what made this a precondition rather than a tidy-up. The extraction entry point was already exported from the package, but its argument type was private. An out-of-package consumer therefore could not construct a call to the exported function without reaching into the private module, which the architecture boundaries rule forbids — so the exported function was effectively uncallable from outside the package. Promotion is a precondition of every consuming change in the wave, not a follow-up to one.

The consumer-import gate the Step names exists and is stronger than a bare import assertion, which is the part worth recording. It identity-checks the object resolved through the facade against the canonical class, so a second definition shadowing the canonical one — rather than a genuine re-export of it — also reds. It separately asserts the name is declared in the facade's export list, because attribute resolution alone would pass on an undeclared accident that the lazy attribute map happened to serve. And it asserts the exported extraction entry point still annotates the exported type, so if that function stopped taking it the export would be justified by nothing and the gate reds rather than leaving a stale public name behind.

One honest qualification on the wording of the Step. At the time of this closure no out-of-package module imports the type yet; the cross-package imports from this facade resolve other names. That is the expected state for a precondition Step and not a defect — the promotion exists so that consuming changes later in the wave are possible at all — but it means the gate proves reachability rather than observed use. A first real consumer arriving later does not require this Step to reopen.

A substring hazard was met while verifying this and is worth passing on: a plain search for the type's name also matches an error class whose name contains it as a substring, which inflates the apparent consumer list. The reachability judgement above was made against a word-boundary search after that contamination was noticed and discarded.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_input_facade_export.py -p no:randomly -p no:cacheprovider
    3 passed in 12.04s

The log was written in full to disk and read back; grepping it for deselection and error markers returned nothing, so all three collected tests ran rather than being deselected by a marker lane.

The prior commit that delivered both the promotion and its gate was identified by inspection of the history for each path, so the closure cites a specific landed change rather than present-day existence alone.

## Notes

No commit was issued from this Step, because nothing was written.

The repository-wide import-hygiene gate named in the Step's own gating clause was red throughout the phase at 83 reaches against 79 documented, from four undocumented private test imports that arrived in peer commits and carry no entry in the test-debt ledger. It is unrelated to this Step's surface — the promotion removes a private reach rather than adding one — and it was recorded rather than patched. The Step's other gate, the consumer-import test, is green.
