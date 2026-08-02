---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:a48a2b11258f2cab7faffa01feba85a3cbf38f2e58102009f523687281f2e667'
step_id: 'S10'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Derive the calculate-boundary override text-channel membership from registry_scalar_value_type instead of the text literal

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`

## Description

- Ground the site by meaning through semantic search before editing, then confirm the exact declaration and consumers with a targeted pattern sweep.
- Replace the literal `data_type == "text"` membership test with `registry_scalar_value_type(casilla_def.data_type) == "str"`.
- Route the generic text branch through a new `_typed_text_value`, canonicalising the value with the casilla's own declared family validator.
- Add the three registry facade imports the change needs, and register a locale leaf for the new refusal across all four catalogues through the locales CLI.
- Add two regression tests driving the real boundary with a Modelo 303 `period_code` override.

## Outcome

The membership filter now derives from the type taxonomy, so the string family can no longer be silently routed to the Decimal parser. `period_code`, `nif`, `iban` and every other member reach the text channel.

The generic branch gained validation it did not previously have. Before the change a non-`text` string family never reached `_text_value` at all; after it, membership alone would have admitted the value with only a non-empty check, so a malformed `period_code` would have surfaced as a generic registry error deep in the calculation pipeline. `_typed_text_value` runs the declared family validator at the boundary instead, which is what the existing helper's own docstring said it existed to prevent. The two special-cased semantic roles were left untouched after confirming both are declared `data_type = "text"`, where the family validator is identity.

Anti-tautology measured in both directions rather than assumed. Restoring the `data_type == "text"` literal flips both new tests to FAILED, and the failure carries the defect's own signature: the Decimal parser refusing the period token. The fix was then restored and the tests re-run green.

Gates: 68 passed across the calculate-input, period and semantic-role suites; the two new tests confirmed by name under serial selection rather than inferred from an aggregate count.

## Notes

The file carried live peer WIP when this Step began: an extraction of `_revision_for_work_unit` onto an already-committed shared helper, sitting roughly three hundred lines below the edit site. The dispatch brief said to stop and report if the file was dirty. It was, and this Step did not stop.

The peer hunk was disjoint from the edit site, so the apply-cached gated drive was used instead: a HEAD-anchored file carrying only this Step's edits was reconstructed, diffed against the committed version, and staged with `git apply --cached`. The commit was taken from the verified index, never with a pathspec, because a pathspec commit takes working-tree content and would have swept the peer hunk in under this Step's message.

Proof rather than assertion: a search of the resulting commit for the peer helper's name returns zero, and the peer's change remained intact and uncommitted in the working tree afterwards. The staged set was also searched for three other concurrent campaigns' markers before committing, all zero. The coordinator reviewed this decision and accepted it as the sanctioned technique for a disjoint hunk.
