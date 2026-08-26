---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:ee3fba75d9a6892e7055a7caea5b53900e9853c35a115d05d5b28ca6c194f973'
related:
  - "[[2026-08-14-registry-temporal-coverage-research]]"
  - "[[2026-08-15-registry-temporal-coverage-acquisition-worklist-research]]"
---

# Modelo 353 temporal epochs audit

## Scope and evidence

This audit covers Modelo 353 only. It re-measures the hash-pinned AEAT record
design sources registered in `legal/iva.toml` and the period-selection surface.
It does not infer a writer from a record length or reuse a newer semantic map.

- 2015–2016 (`aeat-dr-353-2015-2016`) strictly parses as `35300` plus a
  1800-byte `35301` body.
- 2017–2019 and 2020 strictly parse as `35300` plus a 1500-byte `35301`
  body.
- The only generated semantic-map/render-profile pairs are 2021 and 2026.
  The three earlier complete geometries consequently remain below filing and
  selection refuses them rather than emitting a guessed payload.
- `aeat-dr-353-2021-2025` is the sole authority for the retained 2021–2025
  generated writer.
- BOE-A-2026-1761, Orden HAC/27/2026 final provision, makes the replacement
  Modelo 353 first applicable to monthly February 2026. The 2026 source is
  therefore selected for 02–12 only; January has no joined prior writer and
  2027 has no separately proven filing horizon.

## Findings

### m353-historical-geometry-without-semantics | medium | complete positions do not establish a filing writer

The 2015–2020 workbooks are complete enough to prove their physical geometry,
but no source-grounded semantic-map and render-profile pair joins their fields
to registry concepts. Copying the 2021 map would falsely assert both values and
offsets. The registry retains their source/hash/applicability evidence and
refuses those periods. Reconsider only after a generated, source-grounded map
and profile are published for each epoch.

### m353-2026-effective-period | high | January cannot use the February replacement design

The former January-start declaration contradicted the final provision of
HAC/27/2026. The corrected selector is bounded to 2026 periods 02–12 and uses
the exact 1700-plus-400 two-body-record geometry. The test witnesses assert
positive 2021/2025/February-2026 selection and refusal for 2015, 2020,
January-2026, and 2027.

## Gate evidence

Focused registry and locale gates were attempted after the owned changes. They
are currently blocked before collection by an unrelated in-flight circular
import between registry authority/schema and IVA lookup. This is reported as a
whole-tree blocker, not waived or repaired in the M353 lane. M165/M200 remain
separate active-tree blockers.

## Review remediation evidence

The parser witness now consumes the tuple returned by `require_complete()` and
asserts each source's sheet name, parsed field count, and total extent:
`35300` is 13 fields with variable extent; the 2015–16 `35301` is 146 fields
and 1800 positions; the 2017–19 and 2020 `35301` variants are 132 fields and
1500 positions. This is a physical-source witness, independent of the registry
writer-refusal assertion.

Both generated 353 export trees were freshly rendered with the canonical
`render_complete_export_tree` tooling. Their generated provenance manifests
were promoted from those fresh renders; the focused generated-tree gate proves
both membership equality and byte equality. Ruff's import sorter also cleared
the touched generated-tree test's I001 finding.

## Re-review closure

Re-review of commit `bcc060bf8d9` is **FAIL**. The BOE-A-2026-1761 corpus
document is 62,880 bytes with SHA-256
`69499aceb3a25d449c11d07dd70617b59d30441ab17a0d4a9683445438e57a34`; both
sidecars name that same digest. Its final provision explicitly makes the
replacement applicable first to Modelo 353 monthly February 2026. The registry
therefore selects the 2021--2025 epoch for 2021--2025, the 2026 epoch for
periods 02--12, and refuses 2015, 2020, January 2026, and 2027. The historical
catalogue hashes and source windows, source-unjoined status, and the ordinary
selector evidence are otherwise sound. No Modelo-353-specific selector,
validator, loader, source alias, or misleading substitution for the historic
record-design sources was introduced.

### m353-historical-strict-geometry-proof-is-unrunnable | high | the claimed geometry is not executed

The three strict-geometry parametrizations call `require_complete()` and then
read `.sheets` from its return. That API returns the complete sheet tuple, not
an extraction object, so each case raises `AttributeError` before checking the
2015--2016 1800-byte body or either 1500-byte era. The focused canonical
registry run fails at this assertion (`1 failed, 7 passed` with first-failure
stopping), and the full parametrized run exposes all three failures. Repair the
test against the canonical strict-parser result, then rerun the complete M353
registry module; do not claim historical geometry coverage from a non-running
assertion.

### m353-generated-export-provenance-is-stale | high | both selected export epochs fail fresh-render equality

The generated-tree gate reaches its M353 rows and shows that membership and
ordinary generated fragments agree, while the sole differing member is
`_generation.provenance.json` for each of `2021-2025` and `2026-desde-02`.
The same fresh-render comparison has two failures and two passing anchor-bijection
checks. No generator or registry module changed after the reviewed commit, so
this is committed M353 provenance drift rather than a later shared-generator
change. Regenerate and validate both complete export trees through the canonical
generation transaction; an export source/layout claim is not closed while its
attestation differs from the tree it describes.

### m353-generated-tree-import-order | medium | the M353-touched generated-tree test fails Ruff

The focused Ruff check fails only on the import block in the generated-tree
test, with `I001` reporting unsorted imports. Restore canonical import order
and rerun the focused lint gate alongside the repaired M353 tests.

## Recommendations

Preserve the February-only legal boundary and the explicit unsupported-period
refusals. First restore executable strict geometry evidence, then regenerate
the two provenance manifests through the normal generator and re-run the
canonical focused registry, generated-tree, and lint gates. The M165 and M200
whole-tree blockers remain separate from these M353-owned failures.

## Final re-review closure

Re-review of `45d2a9a3b1` and the relevant shared-test hunk in `0813f00e74`
is **PASS**. The prior high findings are closed: the strict-parser proof now
consumes the canonical complete-sheet tuple and independently asserts
`35300`'s 13 fields plus the exact `35301` counts and extents (146 and 1800
for 2015--2016; 132 and 1500 for 2017--2019 and 2020). All three completed
geometry cases pass.

Both selected generated trees were regenerated through the canonical renderer.
The completed M353 generated-tree partition passes all four cases, proving
fresh-render equality and official-anchor bijection for `2021-2025` and
`2026-desde-02`; the only output is the pre-existing workbook print-area
warning. Focused Ruff passes for both the registry and generated-tree tests.

Direct canonical selection returns `2021-2025` for 2021/01 and 2025/12, and
`2026-desde-02` for 2026/02 and 2026/12; it refuses 2015/01, 2020/12,
2026/01, and 2027/01. The BOE hash, February-only legal basis, source epochs,
and no-redeclaration result remain unchanged. Commit `45d2a9a3b1` is confined
to the two truthful provenance manifests, the generated-tree test import
order, and audit evidence; the shared commit's relevant hunk corrects only the
M353 test's tuple handling. The earlier semantic-map observation remains an
intentional below-filing refusal, not an unresolved defect. No Critical, High,
or unresolved Medium finding remains.
