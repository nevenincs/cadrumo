---
tags:
  - '#audit'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-29'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-04-registry-m200-completeness-audit]]'
  - '[[2026-06-04-registry-m303-completeness-audit]]'
---

# `registry-hardening-next-work` audit: `legal and official-source grounding`

## Scope

Audited the recently landed M200 and M303 registry definition changes for legal
and official-source grounding. This audit verifies that the changes are backed
by committed registry legal references, committed official AEAT/BOE source
artifacts, official Diseño/export identity checks, and real registry snapshot
setup. It does not introduce a new legal interpretation.

## M200 grounding

- **Source refs:** M200 `2024-y-siguientes` resolves to
  `aeat-dr-200-2025` (`record_design`), `aeat-modelo-200-manual-2024`
  (`manual_pdf`), and `boe-modelo-200-2025-form` (`form_spec`).
- **Manifest refs:** the M200 completeness manifest resolves to
  `aeat-dr-200-2025` and `aeat-modelo-200-manual-2024`.
- **Legal refs:** the manifest resolves to committed LIS refs including
  `ley-27-2014:art-29`, `ley-27-2014:art-30`,
  `ley-27-2014:art-40`, `ley-27-2014:art-41`, and
  `ley-27-2014:art-105`.
- **Changed casillas:** every M200 casilla touched by the completeness repair
  carries non-empty `legal_refs` and `source_refs`.
- **Official Diseño backing:** exported M200 calculation closure rows are a
  subset of full Diseño coverage after subtracting `internal_only` rows.
- **Internal-only exception:** `DP200014:bin-aplicada-maxima` remains
  `internal_only = true`, formula-derived, export-ref-free, and legally grounded
  on `ley-27-2014:art-26` and `ley-27-2014:art-25`.
- **Closure consistency:** M200 `2024-y-siguientes` has 24 completeness-manifest
  identities and 24 derived closure identities; manifest-only and closure-only
  sets are empty.

Segment ownership verified from the committed Diseño-backed registry setup:

- `00501 -> DP200012`
- `00670 -> DP200015`
- `00671 -> DP200015`
- `01032 -> DP200014`
- `01494 -> DP200020D`
- `01495 -> DP200020D`
- `01498 -> DP200020D`
- `01499 -> DP200020D`

The already segment-scoped M200 completeness rows remain valid:

- `DP200013:00417`
- `DP200013:00418`
- `DP200014:00547`
- `DP200014:00550`
- `DP200014:bin-aplicada-maxima`

## M303 grounding

- **Source refs:** both M303 revisions resolve to `aeat-dr-303-2025`
  (`record_design`), `aeat-modelo-303-procedure` (`instructions`), and
  `boe-modelo-303-2008-form` (`form_spec`).
- **Manifest refs:** both M303 completeness manifests resolve to the same three
  committed source refs.
- **Legal refs:** both M303 manifests resolve to committed IVA and regulation
  refs including `ley-37-1992:art-84`, `ley-37-1992:art-88`,
  `ley-37-1992:art-92`, `ley-37-1992:art-99`,
  `ley-37-1992:art-102`, `ley-37-1992:art-104`,
  `ley-37-1992:art-115`, `ley-37-1992:art-116`,
  `orden-eha-3786-2008:art-1`, `rd-1624-1992:art-29`,
  `rd-1624-1992:art-30`, and `rd-1624-1992:art-71`.
- **No form-data deletion:** casillas `27` and `45` remain declared and
  export/extraction-backed as form totals in both revisions.
- **Current calculation status:** in `2009-y-siguientes`, casillas `27` and
  `45` are not calculation-closure members and are absent from the manifest. In
  `2023-y-siguientes`, both are formula-backed official Diseño projection
  targets and must remain in the manifest.
- **Closure consistency:** M303 `2009-y-siguientes` has 31 manifest identities
  and 31 derived closure identities; M303 `2023-y-siguientes` has 53 manifest
  identities and 53 derived closure identities. In both revisions,
  manifest-only and closure-only sets are empty, and manifest legal refs match
  the current calculation closure.

## Findings

- **Pass:** The M200 segment repairs are backed by committed official Diseño
  sources and did not create ungrounded or exportless public casillas.
- **Pass:** The M200 manifest additions are calculation-closure rows, legally
  and source grounded through existing casilla and manifest references.
- **Pass:** The M303 manifests now track the current legal calculation surface:
  2009 excludes non-computed total rows, while 2023 includes the same numbered
  totals only because they are grounded projection formulas.
- **Pass:** No schema semantics, loader behavior, or per-modelo ad hoc logic was
  added by these repairs.

## Residual control

Future modelo definition edits should not be considered complete until the step
record names the legal refs, source refs, official setup check, and registry gate
used to verify the changed rows. If any row has no public official-form backing,
it must be explicitly `internal_only` with formula/binding rationale.
