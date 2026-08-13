---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:574042dff5bd6708f52b98123211fdbdd9993892ba0e81b3a215a34ae8124e7d'
step_id: 'S15'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---
# Close the three smaller review findings in one pass

## Scope

- `dev/audit/legal_excerpt_vintage_screen.py`
- `dev/audit/legal_attribution_screen.py`
- `dev/audit/tests/`

## Description

- Add `confirms_citation`, a second cross-check binding the catalogue's own citation token to the unit the comparison was made against, derived through the existing candidate-key ladder and forking no unit selection.
- Carry it on `Finding` as `citation_confirmed`, render it beside the identity flag, and print the disagreements as their own reported section.
- Rewrite the module's cross-check prose to state what each leg proves, and to record the literal binding form that was measured and rejected.
- Hoist the duplicated catalogue walk into one `legal_catalogue` module owning the directory constant, the refusal and the traversal, with a `required_text` projection for the narrower consumer.
- Move both screens onto it and delete both private copies, leaving no re-export bridge.
- Split `norm_root`'s two distinct None outcomes at the call site by declaration, routing an entry with nothing bundled to its own reported verdict, and document the two outcomes on the function.
- Correct both screens' `main` docstrings, which promised an unconditional zero exit while each refuses on inputs that cannot support a result.
- Correct the attribution screen's factual prose, which asserted four live mis-attributions that have since been corrected, and its promotion paragraph, which said the worklist was non-empty.

## Description of the identity decision

The literal option was implemented and measured before being rejected, and the measurement is the reason. Resolving the catalogue's citation token against the excerpt's own sidecar and requiring it to reach that sidecar's single unit returns true for 275 of 275 entries, and for the 53 excerpts whose sole unit carries no anchor it returns true by construction, because the canonical resolver serves a lone anchorless unit for any key at all. A check that cannot fail for a fifth of its population is a tautology standing where a safeguard is claimed, which is worse than the docstring it would have justified.

The binding that was taken keeps the same intent and discriminates. It compares the reached unit's structural heading against a heading the entry id derives, through the same candidate-key ladder, and the two are written by different authors in different files. Measured over the real corpus it confirms 274 and flags one, the ordinal-spelling case the review predicted. It is reported and never promoted to `misresolved`, because a written ordinal against a digit is a spelling variant and putting it in the wrong-article bucket teaches a reader to stop trusting that bucket.

## Outcome

The hoisted loader lives at `dev/audit/legal_catalogue.py`, exporting the directory constant, the raw entry read and the `required_text` projection. Both screens consume it and neither retains a walk of its own. The attribution screen's output is unchanged across the hoist, verified by running the pre-hoist module against the same root: 633 entries read, 60 approving a named modelo, 0 mismatched citations, identical on both sides.

The one live citation disagreement is the 2024 orden's article 9, whose consolidated unit BOE titles with a written ordinal against a derived digit form. It is reported unbound, keeps a real clause comparison and is not misresolved.

Anti-duplication is now enforced rather than asserted: a test keyed on the catalogue directory path, not on a function name, requires that exactly one module under `dev/audit` names it, so a re-implementation under any name reds the gate.

Gates: 49 tests pass sequentially across both screens' test modules. Ruff format and check clean; `ty` clean on the changed files, with the two pre-existing diagnostics in the attribution screen's approval helper confirmed present at HEAD and out of the project type gate's `src` scope. Full-tree collection clean at 25474 tests.

## Notes

The attribution screen's promotion condition is now met, since its worklist reads zero. The promotion to a pytest gate was deliberately not taken here: it is a scope decision of its own and not a consequence of reading the file. The prose says so rather than leaving a stale instruction.

Landed in one commit with the sibling row that shares this file. The loader hoist is a relocation and must be atomic across both consumers, and the two rows' edits interleave in the same functions, so a split would have required a bridge state the relocation discipline forbids.
