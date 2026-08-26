---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:3e4b2e69ef3faf3bd0d5e8ab8ad80146c592e72a5149105dbb9a3feb5de5283a'
related:
  - "[[2026-08-26-tui-architecture-registry-facade-census-review-remediation-audit]]"
---

# `tui-architecture` audit: `Registry facade census final hardening`

## Scope

Re-audit the fixed c941 registry-family denominator after independent review
found missed package-symbol, registration, and fully-qualified access forms and
found the 78 semantic dispositions mechanically evidenced. This audit covers
the current-tree scanner, reviewed matrix, adversarial tests, and refresh/check
boundary. It implements no row disposition and does not close `W03.P20.S175`.

## Findings

### reviewed-field-boundary | high | refresh cannot author semantic adjudication

`generated_rows` emits null semantic placeholders. Reviewed refresh copies
`semantic_evidence`, owner, RAG, alternative-owner, disposition, and plan fields
verbatim while recomputing only census, locators, and terminal projections. A
regression compares all reviewed fields before and after refresh.

### current-consumer-completeness | high | omitted access forms resolve to exact rows

The current-tree scanner reads Python, TOML, JSON, YAML, Markdown, and
reStructuredText. Non-Python package-symbol targets use the historic facade
member-owner map. Direct/relative leaves retain base categories; aliased
registration, positional/keyword dynamic imports, full annotations/type aliases,
fully-qualified package access, fixture precedence, and reverse closure have
focused adversarial coverage.

### semantic-adjudication | high | every row has sequential semantic and exact evidence

All 78 rows received a path-scoped owner search, a separate wider competitor
search, and exact symbol confirmation. Each stored result names an exported
current definition except exportless snapshot, which names `build_snapshot`.
Rationales name bounded behavior and actual competitor outcomes. The checker
rejects unrelated symbols, queries omitting the result, inexact locations,
drifted owner locators, and normalized boilerplate collisions.

### execution-state | medium | S175 remains open for independent review

Deterministic refresh/check and focused tests exercise the repaired mutant
classes. This is a review candidate, not self-approval: `W03.P20.S175`, all 78
disposition Steps, and the final package gate remain open.

## Recommendations

Run a fresh-context independent architecture review of scanner, matrix, tests,
and this audit. Reject closure if a semantic result is unrelated to the row, a
competitor outcome is formulaic, or refresh changes a reviewed field. Only a
passing review may reconsider S175 status; no disposition belongs in this commit.
