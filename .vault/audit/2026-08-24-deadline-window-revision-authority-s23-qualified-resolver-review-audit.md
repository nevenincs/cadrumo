---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b8f0270b705b6804db73c07e989fefb4ea6e3a78735f9fae4b1b83c92be5b345'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# `deadline-window-revision-authority` audit: `s23 qualified resolver review`

## Scope

Reviewed approved step `W03.P10.S23` against the accepted deadline-window and
M210 plazo decisions. The review covered canonical semantic-coordinate reuse,
wildcard and exact qualifier matching, ambiguity refusal, absence semantics,
import-cycle safety, the public cached resolver contract, and focused test bite.
Semantic discovery plus exact-symbol confirmation found no redeclared deadline
matcher, period vocabulary, ResultDisposition vocabulary, or M210 official-code
map in the step implementation.

## Findings

### qualifier-validation | medium | Invalid qualifier context is laundered into deadline absence

`resolve_filing_window` accepts its two new qualifier values at a public domain
boundary but does not validate that `resultado` is a `ResultDisposition` or that
`tipo_renta_code` belongs to the canonical official M210 code projection. The
shared coordinate helper intentionally projects identity and does not validate
these request values. Consequently an unknown code such as `"99"`, or a raw
string in place of `ResultDisposition`, simply matches no expanded coordinate and
returns `None`. That contradicts this step's documented contract that `None`
means the validated registry declares no matching window: malformed caller
context is not an authority-declared absence. Existing tests exercise valid,
nonmatching coordinates but do not plant invalid qualifier types or codes, so
the laundering path remains green.

Resolution: fixed in S23. The public resolver now checks `ResultDisposition`
membership and the existing canonical M210 official-code projection before any
authority lookup, raises `DeadlineValidationError` for malformed context, and
has planted public-boundary tests for raw resultado strings and unknown codes.

## Recommendations

For `qualifier-validation`, validate supplied qualifier context through the
existing canonical `ResultDisposition` and M210 official-code authority before
coordinate matching, raising a typed domain validation error for invalid input.
Do not add another enum, code collection, or matcher. Add public-resolver tests
that plant an invalid resultado value and an unknown official code and prove
neither can return `None`; retain the current exact absence, wildcard, exact
scope, ambiguity, and year-isolation proofs.

Implemented and verified with focused Ruff plus six resolver tests.
