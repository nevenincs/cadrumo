---
tags:
  - '#audit'
  - '#spanish-stem-terminology-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:6c3b53a4578e0cbe1b38bb11d69dbb6c096fef9b85f6b51e7b44885189cf3edd'
related:
  - "[[2026-05-19-spanish-stem-terminology-authority-adr]]"
  - "[[2026-08-11-aeat-export-fragment-generator-authority-s61-dp30300-envelope-authority-research]]"
---
# `spanish-stem-terminology-authority` audit: `IVA hard-cut campaign`

## Scope

Reviewed the current Spanish IVA terminology hard-cut against the accepted 2026-05-19 terminology ADR. The semantic scope comprises 48 Python paths whose indexed diff removes authored whole-word `VAT` uses, the NIF-IVA diagnostic prose correction, the MCP quickfile alias deduplication, the strengthened Spanish-stem conformance gate, and the S61 research terminology rewrite. The review separated indexed content from unstaged shared-worktree content, checked retained external protocol/source/localized tokens, searched for duplicated and mixed IVA aliases, inspected the changed test logic for tautology or doubles, and ran bounded focused gates.

## Findings

### official-label-fidelity | medium | The S61 rewrite corrupts an exact AEAT field label

The research note previously quoted AEAT's field as `VersiÃ³n del programa`, matching the cited extracted official source exactly. The current rewrite changes that quote to `Version del programa`, dropping the accent while continuing to attribute the label to AEAT. The terminology hard cut authorizes replacing an internal English tax stem, not normalizing or mistranscribing official Spanish evidence. Restore the exact accented official label; quote-mark style is secondary, but official spelling is not.

### exception-granularity | medium | Whole-file VAT prose exemptions create an ungated authored surface

The strengthened conformance test usefully stops excluding every test module, but replaces that broad exclusion with `_EXTERNAL_VAT_PROSE_PATHS`, a whole-file allowlist. Any future authored `VAT` prose anywhere in those files passes, even when unrelated to the external string that justified admission. The list also contains the conformance test itself although `_source_files` explicitly excludes that file, making the entry unreachable and stale on arrival. This violates the repository's allowlist discipline: exemptions need a reason, precise enclosing site or exact externally owned value, and a stale-entry failure. Preserve the real UBL `VAT` tokens, English locale strings, source quotations, and English fixture labels through exact value or site-scoped evidence rather than exempting entire files.

### indexed-delivery-integrity | medium | The current index is neither the reviewed campaign nor safe to commit as a whole

The index contains the 48 terminology paths plus the NIF-IVA and MCP files, but also seven out-of-scope grammar edits in `_iva_ledger.py`, `_modelo_bindings.py`, `_establishment_ladder.py`, `_grounding_anchor.py`, `core/classification/__init__.py`, `domain/iva/_classification.py`, and `domain/iva/_errors.py`. Conversely, the strengthened conformance gate and restored external `VAT` admissions exist only in the unstaged layer of an `MM` file; the indexed version still excludes all test prose and changes the external apoderado token admission from `VAT` to `IVA`. Three other campaign paths also carry unrelated unstaged WIP. A bare commit would absorb the seven unrelated staged paths and omit the strengthened gate; a pathspec commit would take working-tree content and absorb unrelated edits from the `MM` paths. Rebuild and verify a campaign-only index, then use the repository's verified-index delivery procedure.

## Recommendations

1. Restore the exact `VersiÃ³n del programa` official quotation in the S61 research record through the VaultSpec authoring path.
2. Replace whole-file prose exemptions with reasoned exact-value or path-plus-enclosing-site admissions and assert every admission is exercised.
3. Reconcile the index without destructive Git operations: remove the seven out-of-scope cached patches through the sanctioned reverse cached-patch method, stage only the final gate hunk, and verify the exact indexed path/hunk inventory before any bare commit.
4. Retain the mechanically correct changes: the 48 authored terminology replacements use IVA, the NIF-IVA prose no longer duplicates IVA, the MCP alias no longer says `IVA IVA`, external UBL `VAT`, English locale/source strings, official URLs, and identity tokens remain intact in the working tree, and no compatibility alias or business-logic mirror was introduced.

## Verification

- Fresh VaultSpec RAG grounded the canonical terminology owner and external-boundary rule.
- Exact cached census found 48 Python paths removing authored whole-word `VAT`; the campaign edits are terminology-only apart from the strengthened gate and pre-existing unstaged peer work.
- Current-source `VAT` census found only the enumerated external protocol, source quotation, English locale/query, and English fixture cases plus the gate's own detector vocabulary.
- Duplicated-IVA census found only official locator/source material excluded by the accepted external-boundary rule.
- Focused NIF-IVA, MCP meta-tool, and command-ranking modules: 44 passed, 22 integration-marked tests deselected by the configured unit lane.
- Scoped Ruff over the 48 paths plus NIF-IVA and MCP files: passed.
- Scoped cached and working-tree diff checks: passed.
- Full conformance module: four tests passed; the identifier/path test was unverified because unrelated shared WIP currently leaves `_ledger_read_cli.py` syntactically incomplete at line 399. This is not an IVA-campaign failure, but the full gate is not green on the current shared tree.

## Verdict

CHANGES REQUESTED. The 48 hard-cut replacements and the two direct prose fixes are semantically correct, external tokens remain present in the working tree, and no compatibility surface or test double was introduced. The official-label corruption, over-broad/non-stale exception mechanism, and unsafe indexed payload must be corrected before the campaign can honestly close or be committed.

