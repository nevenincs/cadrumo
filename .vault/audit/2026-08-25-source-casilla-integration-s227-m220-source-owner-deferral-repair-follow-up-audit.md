---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e64652a98199e39569a38a9c411f4173eb8c920c585e88092e7e08acd244f40a'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S227 M220 source-owner deferral repair follow-up`

## Scope

Independently re-review repair commit `7d49f20d7f` against the prior HIGH
audit `3878275b05`: the M220 model-scoped decision home, factual research,
tracking links, unchanged two-era evidence and reopening predicate, and the
no-runtime/no-census boundary.

## Findings

### accepted ADR is the sole model-scoped normative home Ã¢â‚¬â€� PASS, HIGH resolved

`2026-08-25-source-casilla-integration-m220-source-owner-deferral-adr` is
accepted and makes the bounded `ingress_blocked` decision, owner, expiry
route, and complete reopening predicate explicit. Exact ADR search found the
generic accepted connectivity framework and the separate accepted M187
source-owner deferral, but no competing M220 decision. The new ADR defers to
the framework rather than replacing it.

The grounding research has no `## Decision` section and states only facts and
limits of the official evidence. The execution record links the ADR and
attests its boundary without redeclaring the decision; the checked plan links
the research.

### evidence and boundaries remain exact Ã¢â‚¬â€� PASS

The official AEAT workbook SHA-256 values recompute as
`a8f398dd42db0b1142d5f2e98bf3a60d79069e31d63af32001373f459fee4f2e` for
2024 and
`69c3a234e96eb4485a31c65209348bbcede0a49a8c143223c952000784f3f2df` for
2025. The reopening predicate still requires a non-lossy encrypted composite
owner, identity, period/revision, native role/unit/value identity,
fingerprinted provenance, absence semantics, full lifecycle, and
source-owned export for both eras.

The repair commit changes Vault documents only. Exact source/census search
finds no M220 source-connectivity census row, producer, binding, resolver,
casilla linkage, layout, lifecycle, or export promotion.

### verification Ã¢â‚¬â€� PASS

- `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py -k "not every_registry_revision_can_produce_a_filing_artifact"`: 5 passed, 1 deselected.
- `uv run ruff check` over the reviewed Markdown paths: passed (no Python files).
- `uvx vaultspec-core vault check all --feature source-casilla-integration --no-hints`: structure, frontmatter, links, schema, and ADR status clean. The 31 warnings are pre-existing M232/M360 documents and concurrent unfilled M390 research, outside this repair.

## Recommendations

PASS. The HIGH finding in `3878275b05` is resolved. Reopen only if a later
accepted owner satisfies every M220 predicate limb; do not infer a connection
from layouts, manual/direct entry, Modelo 200, Modelo 222, or export
coordinates.

