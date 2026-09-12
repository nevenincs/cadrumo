---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:fee6689dd7f445e221ae86c246a88d0956ce120ace893020f00a826cc92e46a9'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# `registry-authority-artifact-boundary` audit: `source compile prerequisite review`

## Scope

Reviewed the Modelo 182 application-link edition move, the 2025 impatriado
income-ledger fact selector and citations, and the Modelo 576 historical
revision tests as prerequisites for compiling the complete authored registry.
The review checked the accepted immutable-authority decision, canonical source
ownership and inheritance, enrolled official evidence, typed schema contracts,
the distinction between corpus inspection and product filing admission, and
the preservation of unrelated concurrent edits.

The reviewed source state had completed the canonical compiler path with 58
modelos. The scoped test and source diff also passed Ruff, formatting, and
`git diff --check`. A later independent compiler rerun was prevented before
registry loading by an out-of-scope unterminated string in
`src/cadrumo/core/aggregation.py`; this is the same separate collection
blocker affecting focused Modelo 576 pytest execution and is not caused by the
reviewed files.

The re-review also covered the two predecessor-evidence additions to
`src/cadrumo/_data/registry/aeat/modelos/123/manifest.toml`. It checked their
use by the 2024 continuity evolutions, the unchanged closed predecessor and
successor revision windows, model-level corpus-source admission, and the
direct source-compiled Modelo 123 snapshot for 2025 period `1T`.

## Findings

No findings. The 2024 Modelo 182 fragment is the earliest common owner of the
two unchanged application links, supplies the enrolled official procedure
source, and allows the 2025 revision to inherit the same links without a
duplicate edition declaration. The impatriado mapping remains effective from
2025 and narrows its period selector to the Modelo 151 annual `0A` schedule;
each declared citation points to an enrolled BOE or AEAT source whose captured
content contains the required phrase. These declarations are consistent with
the typed source schema and the successful complete compiler result.

The Modelo 576 historical assertion now calls `select_revision` without a
support envelope, which bypasses only product-year admission for legitimate
corpus inspection. Production filing still invokes
`_refuse_unsupported_filing_year` before snapshot loading and retains the
registry-declared 2022 floor. The mutation test calls the owning generic
filing-capability check directly and still proves that promoting authority
grade cannot manufacture a missing export layout. Existing TaxDomain value
migration and snapshot-helper relocation edits in the test were preserved.

No findings in the Modelo 123 re-review. Each continuity evolution compares
the `2019-2023` and `2024-y-siguientes` forms, so it legitimately cites both
the predecessor AEAT record design and 2007 BOE form text alongside the
successor evidence. Adding exactly those two enrolled sources to the modelo's
source corpus admits the cross-revision records without weakening source
validation or introducing unrelated evidence. The predecessor remains closed
by `valid_to = 2023-12-31` and a selector ending in 2023; the successor remains
open from 2024. Neither temporal declaration changed. Canonical source
compilation produced a Modelo 123 snapshot for 2025 `1T` selecting
`2024-y-siguientes`, which confirms the additions satisfy the real compiler
and snapshot path.

## Recommendations

None for the reviewed scope. Re-run the focused Modelo 576 test and canonical
source compilation after the separate `src/cadrumo/core/aggregation.py`
syntax migration is complete; do not treat that external collection failure
as evidence against these registry declarations.

The artifact-backed Modelo 123 tests should remain pending until the complete
authority is published atomically. A stale tracked artifact is not contrary
evidence to the successful source-compiled snapshot and must not be repaired
piecemeal.
