---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:63c100e6ba569b7c5e8013b9d6b8152d07d59a9f12db8f636cf381aabd9eb096'
step_id: 'S257'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Close the separator-bearing tax identity that passes the redaction funnel raw, which PREDATES the EU VAT rule rather than being introduced by it. Verified at HEAD: SE556677889901 ESB12345674 and B12345674 all redact while SE-space-556677889901, ESB-1234567-4 and B-1234567-4 all pass RAW, the last being a plain Spanish CIF with nothing to do with the EU arm, so the shipped CIF pattern has always had this limitation. Not theoretical: the application itself normalises separators, so normalise_nif_iva of the hyphenated form returns the unspaced one and a shipped gate asserts the spaced form yields the same establishment key, meaning the app treats these as one identity while the funnel sees only one of them. And FieldProvenance.anchor is documented as the verbatim printed form exactly as it appears, so the spelling reaching an operator surface is precisely the one the funnel cannot see. A curiosity that bounds it: ES-space-B12345674 IS redacted because the body token stands alone, so the leak is specifically separators INSIDE the body, which is the common printed rendering. NOT a regex widening: a separator-tolerant scan would start matching ordinary hyphenated output, and SE-2026-000412 survives today precisely because the hyphen breaks the token, so the honest shape is normalise-then-match rather than a wider pattern, which changes the rule's form and needs its over-firing evidence rebuilt from scratch

## Scope

- `src/cadrumo/core`

## Description

- Build the negative corpus before the pattern, and measure the baseline: seven
  of twelve printed renderings of a real tax identity passed the funnel raw.
- Widen the SCAN so a separator-bearing span can reach the admission gates,
  which already normalise what they are handed.
- Split the separator class after measuring: punctuation only for the ungated
  and checksum-gated arms, the space admitted only where a country prefix and a
  per-State table constrain the match.
- Gate both directions, including a control proving the negative half is not
  measuring an empty set.

## Outcome

Modified: `src/cadrumo/core/redaction/__init__.py`. Added
`src/cadrumo/core/tests/test_redaction_separator_bearing_identity.py`.

**The shape is normalise-then-match, as the row ruled, and the reason is
structural.** Both admission gates were already separator-tolerant --
`validate_identity` documents that it tolerates dashes and spaces, and the
prefixed arm calls `normalise_nif_iva` before consulting the per-State table --
so the separated spelling was never rejected by a rule. It never reached one,
because a scan anchored on unbroken word characters cannot produce a span
containing a hyphen. The tolerant half and the intolerant half sat on opposite
sides of one funnel.

**The space is excluded from two of the three arms, and that exclusion was
measured rather than reasoned.** Running the four shipped locale catalogues
through the funnel with the space admitted produced two real false positives on
operator text: a Hungarian date range `A 2020-2024`, which normalises to a
checksum-VALID CIF and was therefore admitted by the gate rather than caught by
it, and a monetary bound `6 000 000-t` matching the ungated personal-identity
arm. A space separates TOKENS in prose, so admitting it lets a scan join a word
to the number beside it. The prefixed arm keeps the space because a match there
must begin with two letters naming a real Member State AND satisfy the per-State
structure.

**An edge defect the same sweep caught:** the first attempt placed the optional
X/Y/Z group's separator outside the group, so it could match empty and stand at
the START of the pattern. `for example 12345678Z` redacted to
`for examplesha256:...`, consuming the space in front of the number. Found by
running the catalogues, not by reading the regex.

Final measurement: eleven of eleven printed renderings redact, twenty-four of
twenty-four operator strings survive, and across 69,637 shipped catalogue
strings the funnel modifies twelve -- three keys in four locales, all of them
tax-identity format examples the previous funnel also redacted. New false
positives on that corpus: zero.

## Verification

    uv run --no-sync pytest src/cadrumo/core -n0 -q -m "unit or integration"
    9 failed, 1583 passed in 455.11s (0:07:35)

Seven of those nine were caused by this change and are described below; the
remaining two are an AEAT route-literal gate and a combined-period gate outside
this surface.

After the corrective landed, the redaction and observability suites together:

    uv run --no-sync pytest <redaction x3, observability> -n0 -q -m "unit or integration"
    241 passed in 10.65s

Mutation-proved from outside the repository, three rungs: narrowing the scans
back reds 13 cases, admitting the space on every arm reds 4 (the measured false
positives), and disabling the scans wholesale reds 25 -- the last including the
removal-count case, which exists because a suite of absence assertions passes
trivially when the funnel removes nothing.

## Notes

**This change caused a real regression, which a peer found and fixed.** A
serialised instant renders as `...T09:32:12.345678Z`, whose seconds and
microseconds are seven separated digits with a trailing letter -- a personal
identity by shape, and `12345678Z` carries a valid check character, so
validating the span cannot tell the two apart. The funnel hashed it, the stamp
stopped parsing, and every model re-validating it on the way to storage refused
the record. The corrective exempts complete ISO-8601 instants rather than
narrowing the patterns, because an exclusion tight enough to spare a microsecond
field would also spare a genuine dotted identity.

**Why the verification missed it, which is the part worth carrying.** Over-firing
was bounded against 69,637 shipped OPERATOR STRINGS. The funnel also runs over
SERIALISED RECORDS on the way to storage, and a timestamp appears in that
population and in no locale catalogue. The corpus was sound and its SCOPE was
wrong: it sampled the surface the change was reasoned about, not every surface
the funnel guards.

**A control that flipped because the tree moved under it.** The first control --
same selection, scans narrowed at runtime -- correctly attributed seven failures
to this change. A later run with the mutation disabled showed only two, which
read as though the harness rather than the change were the variable. It was not:
the peer's corrective had landed in the working tree between the two
measurements. Two readings of the same control minutes apart disagreed because
the thing under measurement changed, and the first reading was the correct one.
