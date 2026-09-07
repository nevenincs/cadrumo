---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:271ed127cedd59f22ba76cb3d52ba0889110758f66e94e968a3bf0a414a2bce2'
related:
  - "[[2026-08-04-canonical-storage-management-void-assertion-class-audit]]"
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---

# `quality-gate-zero-closure` audit: `absence assertion current measurement`

## Scope

This audit re-measures the absence-assertion sampling frame established by
`2026-08-04-canonical-storage-management-void-assertion-class-audit` against an
immutable current revision. The measurement scopes the implementation work for the
closing conformance mechanism; it does not attempt to enumerate every void assertion.

The measured revision is
`9e60f9a2b67cf58f5e7455942fc55a9254f8106a`. From PowerShell, a Python probe was supplied
on standard input with `@'<probe>'@ | python -u -`. The probe resolved that revision with
`git rev-parse HEAD`, read `git archive --format=tar <revision> src/cadrumo` entirely in
memory, and parsed Python modules whose path contains `tests` or whose basename begins
with `test_`. This avoids mixing concurrent uncommitted work into a revision-labelled
measurement. It parsed 3,804 test modules with zero parse errors.

Supported absence assertions are `assert not <call>` where the outer call is
`.exists()`, `.is_file()`, `.is_dir()`, `any(...)`, or `list(...)`. The taxonomy
vocabulary is the set of individual path parts recovered statically from the live
`_location(...)` declarations in `src/cadrumo/core/storage_taxonomy_locations.py`; the
probe recovered 64 tokens. Like the existing declaration conformance scan, module-token
detection ignores multiline strings and strings of 49 or more characters and decomposes
slash-containing strings into path parts.

Classification is ordered: an inline taxonomy literal; a call to `storage_path` or
`bucket_scoped_storage_path`; a helper-routed subject; a direct subject name assigned
from an expression containing a taxonomy literal; an unresolved assertion in a module
that mentions a taxonomy token; then an assertion in a module that mentions no taxonomy
token. A helper-routed subject is returned directly by a call, rooted through a
call-bearing attribute or path expression, or supplied by a called iterable to a
comprehension. Predicate calls inside `any(...)` do not alone make the path
helper-routed.

As a calibration check, the same classifier was applied to revision
`7ee7ee74411df49ddc57d780c7bf321e6044b792`, the settled 2026-08-04 audit state. It
reproduced that audit's exact partition: 400 total, then 19 inline, 13 accessor-routed,
58 helper-routed, 8 local-variable-held, 89 unresolved token-mentioning, and 213
token-free.

## Findings

### absence-assertion-current-measurement | medium | the supported frame now contains 539 assertions

The current partition is:

| Category | Assertions | Distinct modules |
| --- | ---: | ---: |
| Inline taxonomy literal | 25 | 18 |
| Canonical accessor-routed | 13 | 12 |
| Helper-routed | 107 | 63 |
| Local-variable-held taxonomy literal | 6 | 6 |
| Unresolved; module mentions a taxonomy token | 93 | 47 |
| Provably excluded; module mentions no taxonomy token | 295 | 157 |
| **Total supported absence assertions** | **539** | — |

The partition balances exactly. The 295 token-free assertions are excluded in the same
conservative direction as the source audit: a permissive vocabulary can move a module
into the token-mentioning side, but cannot hide a taxonomy token by narrowing the
vocabulary after the fact.

### absence-assertion-current-measurement | high | 93 assertions remain on the unresolved mechanism boundary

The 93 unresolved assertions occur in 47 modules that mention at least one taxonomy
token but whose supported assertion expression neither uses a canonical accessor nor
exposes an inline, helper-routed, or direct local-variable-held route recognised by this
sampling classifier. This is implementation context for the module-level closing rule,
not a 93-item completion target. Helper and local routing remain known blind directions
for any literal-only candidate scan.

### absence-assertion-current-measurement | low | the declaration corpus has 32 live modules and retains the legacy shrink-only mechanism

The immutable snapshot contains 32 AST-visible `PINNED_TAXONOMY_LITERALS` declarations.
The declaration conformance implementation remains in
`src/cadrumo/tests/test_pinned_taxonomy_literal_conformance.py`; that module also contains
`PENDING_UNDECLARED`, its shrink-only test, `HOMONYM_EXCEPTIONS`, and
`EMBEDDED_LITERAL_EXCEPTIONS`. `PENDING_UNDECLARED` is empty at the measured revision.
A separate `HOMONYM_EXCEPTIONS` conformance mechanism exists in
`src/cadrumo/tests/test_production_taxonomy_literal_duplication_gate.py`.

Every count in this audit is a diagnostic floor and scoping context. None is a pass
condition, threshold, baseline, debt allowance, or claim that the full void-assertion
population has been enumerated.

## Recommendations

Close the class with the governing decision's conformance mechanism: for a supported
absence assertion in a module mentioning a taxonomy token, require either a route through
the canonical accessor or a checked, site-naming declaration. Prove both declaration
drift directions. Do not use the 539 total, the 93 unresolved assertions, or any other
count above as the completion condition.

When installing that mechanism, retire the empty shrink-only `PENDING_UNDECLARED` path
rather than carrying forward a baseline that the governing decision explicitly does not
sanction. Preserve only mechanisms whose checked semantics remain part of the accepted
declaration contract.
