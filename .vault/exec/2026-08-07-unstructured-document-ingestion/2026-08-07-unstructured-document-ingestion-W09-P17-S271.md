---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:4223e4ee393616b305f34a56e2c0eefaedb09f8e0e3cc215ed6787e13ada73bd'
step_id: 'S271'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Close the two identity leaks the S250 review found - a two-letter word beside a tax identity defeats redaction on both funnels because the prefixed arm admits a space internally so the scan swallows the neighbour and re-sub consumes the identity inside a span the gate then correctly rejects and returns verbatim, and separately the bare arm leaks a dotted CIF that the prefixed arm redacts because validate_identity normalises hyphens but not dots while normalise_nif_iva strips both - route the matched span through the canonical normaliser that same_tax_identifier already uses so the funnel stops contradicting the codebase own same-bearer answer

## Scope

- `src/cadrumo/core/redaction/__init__.py`

## Description

- Reproduce all three reported spellings on both funnels before touching anything, and confirm at source that `validate_identity` strips spaces and hyphens but not dots while `normalise_nif_iva` strips all three.
- Add `_gated_sub`, a scanner that replaces `re.sub` for every strategy whose gate can refuse a match. A refused span is re-read longest-first from the same start, each candidate required to end where a real token ends, and only when every candidate is refused does the scan advance one character instead of past the whole match.
- Route the CIF gate's span through `normalise_nif_iva` before `validate_identity`, which is the composition the canonical `same_tax_identifier` predicate already uses.
- Rewrite the three gated strategies to return `None` on refusal rather than the span, so refusal and rewrite are distinguishable to the scanner.
- Add a corpus of identities pressed against short Spanish function words, plus a negative corpus of ordinary words beginning with a Member State prefix.

## Outcome

Both leaks are closed on both funnels. `counterparty ESB12345674 is declared`, `NIF ESB12345674 en factura` and `de SE556677889901 y DE811234567` now hash every identity while leaving every surrounding word intact; `B.1234567.4` hashes like the `B12345674` the codebase already calls the same bearer.

The mechanism is the durable part. Three arms here are deliberately a wide scan admitted by a strict gate, and `re.sub` spent the span whichever way the gate decided, so every one of them could lose an identity inside a correctly-refused match. The gate was never wrong; it was never asked about the right string.

## Verification

Reproduction before the change, both funnels, exit 0 on shipped code:

    'counterparty ESB12345674 is declared' -> 'counterparty ESB12345674 is declared'
    'NIF ESB12345674 en factura'           -> 'NIF ESB12345674 en factura'
    'de SE556677889901 y DE811234567'      -> 'de SE556677889901 y sha256:57b1196e'
    'B.1234567.4'                          -> 'B.1234567.4'

The same strings after:

    'counterparty sha256:786dd607 is declared'
    'NIF sha256:786dd607 en factura'
    'de sha256:280987bd y sha256:57b1196e'
    'sha256:67d35751'

Suite:

    uv run --no-sync pytest src/cadrumo/core/tests/test_redaction_neighbouring_word.py src/cadrumo/core/tests/test_redaction.py src/cadrumo/core/tests/test_redaction_nif_iva.py src/cadrumo/core/tests/test_redaction_separator_bearing_identity.py -m unit -q -p no:randomly
    180 passed in 7.21s

Over-redaction control. Every string in the four shipped locale catalogues was frozen to a snapshot, then run through both funnels under the shipped module and under the changed one:

    compared: 69657   differing: 0

Mutation A, applied by a pytest plugin outside the repository so nothing under `src` changed. It restores the spend-the-whole-match behaviour and asserts the window opened before any test runs:

    MUTATION A APPLIED. leak reopened: 'counterparty ESB12345674 is declared'; control still redacts: 'counterparty sha256:786dd607 declared'
    14 failed, 166 passed in 2.99s

Mutation B removes the canonical normalisation from the gate:

    MUTATION B APPLIED. leak reopened: 'B.1234567.4'; control still redacts: 'sha256:6c0705f7'
    6 failed, 174 passed in 4.25s

Both mutations carry a positive control (a genuine identity still hashes) and the suite carries a negative control (ordinary prose still survives), so "the gate stopped running" cannot be mistaken for "the gate passed".

Wider suite, sequential:

    uv run --no-sync pytest src/cadrumo/core -m unit -q -p no:randomly
    3 failed, 1651 passed in 251.40s

## Notes

The three failures in the wider core run are tree-wide gates over peer surfaces and are unrelated to this change: an AEAT route literal in an adapter auth test, two M036 refusal codes with no authored suggestion, and year-qualified period tokens in adapter and registry test fixtures. None of them touch the redaction package.

A first attempt at the over-redaction control produced four apparent regressions. They were the instrument: a peer rewrote two locale values between the two sweeps, so the before and after runs were reading different corpora. Freezing the corpus to a snapshot and running both module versions against that one file reduced the difference to zero.

The space in the prefixed arm's separator class survives only because a refused span is now re-read. That dependency is recorded in the comment beside the separator, because removing the scanner without removing the space silently reopens the leak.
