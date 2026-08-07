---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9dbfdfcf4c3cae108e6acb54fcb869f211b090326a17906e897aee9cfacf1fda'
step_id: 'S13'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Harden the row-scoped locator to an exact expediente_id match instead of a substring filter, reusing the existing re import rather than a second selection idiom, with a test proving it cannot match a second row whose id merely contains the target as a substring

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py (_row_locator_for_expediente)`

## Description

The ADR's Implementation section ruled on this locator, and the row was added to
the plan during execution. Reading `_row_locator_for_expediente` confirmed the
divergence the ADR described, plus one the ADR did not: the docstring already
claimed the cell text *equals* the target while the filter matched a substring.

## Outcome

`_row_locator_for_expediente` now filters on an anchored compiled pattern built
with `re.escape`, reusing the module's existing `re` import rather than
introducing a second selection idiom. Surrounding whitespace is tolerated because
the cell text comes from rendered markup; nothing else is. The docstring now
explains why the anchoring matters for a mechanism that is the sole binder of a
fetched artefact to its declaration.

Added `test_row_locator_exact_expediente.py`, following the existing real-browser
precedent in `test_expand_matching_branches.py`: a local headless Chromium page
over synthetic ZK-listbox markup, no AEAT contact, no test double for
Playwright's selector engine. The fixture renders the *containing* row first, so a
substring filter would both match two rows and resolve `.first` to the wrong one -
which is how a wrong-artefact fetch would actually occur.

## Verification

Three tests pass. Two are controls: asking for the longer id selects the longer
id's row, and an absent id selects nothing, so a pattern that simply matched
nothing could not satisfy the suite.

Gate proven to bite: a plugin loaded with `-p` from outside the repository
replaced the locator with the substring filter, run with `-n0` explicitly. Only
the substring-hazard test went red; both controls stayed green.

## Notes

No reachable substring collision among AEAT expediente ids is known, so this
closes a latent hazard rather than an observed defect. That is the right posture
for a sole binding mechanism, and the test docstring says so rather than implying
a live bug was fixed.
