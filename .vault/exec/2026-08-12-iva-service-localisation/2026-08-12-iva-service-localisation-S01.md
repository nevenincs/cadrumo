---
tags:
  - '#exec'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d20e8dc0ad44cea4c0a7863ed1dcc87909b246a17a7e27243510886b3c698dcc'
step_id: 'S01'
related:
  - "[[2026-08-12-iva-service-localisation-plan]]"
---

# Make the statutory-citation gate anchor-aware: a corpus_ref may name an anchor, and when it does the gate resolves that single unit from the extraction sidecar and reads its rubric and text rather than the whole file. Land the mutation proof in the same change - a row pointed at an anchor whose article names the other limb must red - because an anchor-aware reader that silently fell back to the whole file would pass every existing row and prove nothing. Do NOT fetch per-article files for arts 68-70, because the consolidated text is already bundled and the module's own prose warns against duplicating it

## Scope

- `src/cadrumo/domain/iva/_supply_nature.py`
- `src/cadrumo/domain/iva/tests/test_supply_nature.py`

## Description

- Made `corpus_ref` accept an optional `#anchor`, resolved through the core
  anchored-unit resolver the registry's evidence validator already reads
  citations by. Nothing new was written to resolve an anchor.
- Read the article's rubric alongside its text, because the rubric is where the
  statute names the limb most plainly.
- Extracted the limb check out of the parametrized case so a deliberately wrong
  row can drive it.
- Added the mutation proof: a row claiming art. 69 fixes goods reds.
- Added the scoping proof: two anchors of one document resolve to different
  text, each naming only its own limb.
- Documented the anchor on the field that carries it.

## Outcome

Done. 33 pass in the module's own suite.

The gate was proven to bite in both directions rather than asserted to. A
file-scoped read was driven against the real corpus: it returns identical text
for the two anchors, so the scoping proof reds on its first assertion, and its
opening names only the goods limb -- meaning the pre-change reader would have
asserted GOODS for art. 69, which is a services article. The weakening this
protects against therefore fails loudly rather than passing quietly.

## Notes

The step's own instruction not to fetch per-article files for arts 68-70 held
and mattered: the consolidated law and its sidecar are already bundled, the
sidecar already carries the three articles as anchored units, and fetching
would have duplicated committed text to work around a check.

Worth stating because it reframes the original deferral. The table's own prose
recorded the omission as waiting for "a citation the check can read a single
article from". That citation form already existed elsewhere in the tree -- the
registry has resolved anchored `corpus_ref` values for some time, with a shipped
gate pinning that a file-scoped check cannot produce the refusal an
anchor-scoped one does. The blocker was that this gate did not use it, not that
nothing did.
