---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f3be30641ba97824cc600ea0ba824d84d83b8a105d45fc67a3921e3455667cec'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### s23 qualified resolver review | {level} | {summary}

     followed by a paragraph carrying the detail. s23 qualified resolver review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

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
