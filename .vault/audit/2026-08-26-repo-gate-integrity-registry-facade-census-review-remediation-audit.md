---
tags:
  - '#audit'
  - '#repo-gate-integrity'
date: '2026-08-26'
modified: '2026-08-30'
body_schema: 'body-v1'
body_hash: 'sha256:31cdeec9f92f7bdea7cd504377a68fc61480db9e24d962f4ea6677b34377a63a'
related:
  - "[[2026-08-26-tui-architecture-registry-facade-family-census-audit]]"
---
# `repo-gate-integrity` audit: `registry facade census review remediation`

## Scope

This follow-up audits the independent-review remediation of the fixed 78-row c941 registry-facade family in `dev/quality/registry_facade_family_census.py` and its reviewed matrix. It leaves the prior family-census audit frozen and does not close S175 or any dependent Step.

## Findings

### registry-facade-census-review-remediation | high | Consumer discovery now resolves the Python forms that determine a real owner

The scanner resolves relative `ImportFrom` targets in each consumer's package context before it attributes references. Fixture paths and `conftest.py` are classified before generic test paths. It examines variable annotations, every positional, keyword-only, variadic, and return annotation, PEP 695 aliases when available, and `TypeAliasType` values. Package uses are attributed to one exported facade member rather than every relocated module, and the reverse-import traversal starts from both a defining module and package-member direct consumers so it reaches the complete transitive closure.

### registry-facade-census-review-remediation | high | Reviewed ownership has a reproducible RAG and exact-evidence trail per row

Each matrix row contains its own `rag_query`, a structured RAG result with path, range, node kind, and symbol, and alternative-owner evidence. The refresh preserved reviewed adjudications while recomputing only derived census fields. The checker requires the RAG result to name the row's current defining module and requires that exact result location in both semantic and alternative-owner evidence. The results were obtained by scoped RAG queries against each candidate's current module, then confirmed against the c941 one-to-one rename pair and current AST member locators.

### registry-facade-census-review-remediation | medium | Deterministic verification protects reviewed work from a blank regeneration

The reviewed refresh is keyed by the historic and successor path pair, retains all adjudicated fields including RAG evidence, and the check mode rejects a missing, malformed, or mismatched reviewed result. Focused tests cover relative imports, fixture precedence, annotation and type-alias ownership, package-member narrowing, closure through an intermediate direct consumer, and RAG-result traceability.

## Recommendations

Run an independent review of the scanner, matrix, and follow-up audit before any S175 status change. Keep future refreshes in reviewed-refresh and check modes so manual dispositions and evidence are never regenerated from a blank template. Treat a changed c941 pair, RAG path, or AST locator as a new review event rather than silently accepting it.
