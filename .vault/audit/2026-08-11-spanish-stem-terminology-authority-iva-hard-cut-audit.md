---
tags:
  - '#audit'
  - '#spanish-stem-terminology-authority'
date: '2026-08-11'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:5d1400704e60571e20ca8a63c10e9f4a3d60b23c81ea0fcb1fbe4ebdb4911988'
related:
  - "[[2026-08-11-aeat-export-fragment-generator-authority-s61-dp30300-envelope-authority-research]]"
---
# `spanish-stem-terminology-authority` audit: `IVA hard-cut campaign`

## Scope

Reviewed the current Spanish IVA terminology hard-cut against the accepted 2026-05-19 terminology ADR. The semantic scope comprises 48 Python paths whose indexed diff removes authored whole-word `VAT` uses, the NIF-IVA diagnostic prose correction, the MCP quickfile alias deduplication, the strengthened Spanish-stem conformance gate, and the S61 research terminology rewrite. The review separated indexed content from unstaged shared-worktree content, checked retained external protocol/source/localized tokens, searched for duplicated and mixed IVA aliases, inspected the changed test logic for tautology or doubles, and ran bounded focused gates.

## Findings

### official-label-fidelity | medium | The S61 rewrite corrupts an exact AEAT field label

The research note previously quoted AEAT's accented program-version field exactly. The current rewrite removes that accent while continuing to attribute the label to AEAT. The terminology hard cut authorizes replacing an internal English tax stem, not normalizing or mistranscribing official Spanish evidence. Restore the exact accented official label; quote-mark style is secondary, but official spelling is not.

### exception-granularity | medium | Whole-file VAT prose exemptions create an ungated authored surface

The strengthened conformance test usefully stops excluding every test module, but replaces that broad exclusion with `_EXTERNAL_VAT_PROSE_PATHS`, a whole-file allowlist. Any future authored `VAT` prose anywhere in those files passes, even when unrelated to the external string that justified admission. The list also contains the conformance test itself although `_source_files` explicitly excludes that file, making the entry unreachable and stale on arrival. This violates the repository's allowlist discipline: exemptions need a reason, precise enclosing site or exact externally owned value, and a stale-entry failure. Preserve the real UBL `VAT` tokens, English locale strings, source quotations, and English fixture labels through exact value or site-scoped evidence rather than exempting entire files.

### indexed-delivery-integrity | medium | The current index is neither the reviewed campaign nor safe to commit as a whole

The index contains the 48 terminology paths plus the NIF-IVA and MCP files, but also seven out-of-scope grammar edits in `_iva_ledger.py`, `_modelo_bindings.py`, `_establishment_ladder.py`, `_grounding_anchor.py`, `core/classification/__init__.py`, `domain/iva/_classification.py`, and `domain/iva/_errors.py`. Conversely, the strengthened conformance gate and restored external `VAT` admissions exist only in the unstaged layer of an `MM` file; the indexed version still excludes all test prose and changes the external apoderado token admission from `VAT` to `IVA`. Three other campaign paths also carry unrelated unstaged WIP. A bare commit would absorb the seven unrelated staged paths and omit the strengthened gate; a pathspec commit would take working-tree content and absorb unrelated edits from the `MM` paths. Rebuild and verify a campaign-only index, then use the repository's verified-index delivery procedure.

## Recommendations

1. Restore the exact accented program-version quotation in the S61 research record through the VaultSpec authoring path.
2. Replace whole-file prose exemptions with reasoned exact-value or path-plus-enclosing-site admissions and assert every admission is exercised.
3. Reconcile the index without destructive Git operations: remove the seven out-of-scope cached patches through the sanctioned reverse cached-patch method, stage only the final gate hunk, and verify the exact indexed path/hunk inventory before any bare commit.
4. Retain the mechanically correct changes: the 48 authored terminology replacements use IVA, the NIF-IVA prose no longer repeats the stem, the MCP alias no longer repeats the stem, external UBL VAT tokens, English locale and source strings, official URLs, and identity tokens remain intact, and no compatibility alias or business-logic mirror was introduced.

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

## Re-review 2026-08-11

### exception-granularity-resolution | medium | RESOLVED - exact exercised admissions replace whole-file exemptions

The current conformance gate admits exact external string values or exact fragments scoped to their owning paths. It records every exercised admission and requires equality with the declared admission inventory, so a stale value or fragment fails. The unreachable self-exemption is gone. This resolves the exception-granularity finding without weakening the real UBL token, English locale and fixture text, or quoted foreign-source evidence.

### official-label-fidelity-follow-up | medium | OPEN - the attempted accent restoration is double-encoded

The S61 research correction does not contain the official label's U+00F3 character. A Python UTF-8 read of the current file reports U+00C3 followed by U+00B3 at that position, the signature of UTF-8 bytes decoded and re-encoded through the wrong character set. The console can visually mask this sequence, while the code-point list does not. The official extracted source carries the single correct code point. Re-author the research body with an encoding-safe VaultSpec CLI input and verify U+00F3 or its UTF-8 byte sequence, not only visual rendering.

### indexed-delivery-integrity-follow-up | high | The campaign commit absorbed 247 shared paths

The final index described during re-review no longer exists: commit f66bfe9909 was created externally before review completed. Its parent-to-commit census contains 247 paths, not the intended 51 campaign paths. The commit includes the terminology changes and corrected gate, but also broad unrelated production logic, deleted and added tests, locale updates, and peer work across the repository. The later documentation commit a1a9b357c1 committed the first audit version and the double-encoded research correction. This is not attributed to the campaign owner, but it falsifies the required delivery property that shared WIP was not absorbed. Do not rewrite shared history without authority; record and adjudicate the atomicity breach through the repository's lifecycle process.

## Re-review verification

- Current conformance module: 5 passed in 83.02 seconds after removing the audit's own repeated-stem wording.
- Focused NIF-IVA, MCP meta-tool, and command-ranking modules: 44 passed; 22 integration-marked tests were deselected by the configured unit lane.
- Exact commit-relative terminology census: 48 Python paths removed authored whole-word VAT text; adding the NIF-IVA and MCP modules gives a 50-file Python scope, with the S61 research record as the fifty-first campaign path.
- Scoped Ruff over the 50 Python campaign paths: passed.
- Commit whitespace check for f66bfe9909: passed.
- Commit census: f66bfe9909 contains 247 paths, independently establishing the delivery-integrity boundary.

## Re-review verdict

CHANGES REQUESTED. The terminology implementation and strengthened gate pass their focused behavioral and static checks, and the exception finding is resolved. The official label remains incorrectly encoded, and the externally created 247-path commit absorbed shared WIP, so the campaign cannot receive an unqualified final PASS for official fidelity or delivery integrity.

## Final re-review 2026-08-11

### official-label-fidelity-resolution | medium | RESOLVED - exact official code point restored

The S61 research record has been re-authored through an encoding-safe VaultSpec body-file path. An independent UTF-8 read now reports the program-version label prefix as U+0056, U+0065, U+0072, U+0073, U+0069, U+00F3, U+006E, U+0020. The prior double-encoding is absent, so the official-label-fidelity finding is resolved.

### indexed-delivery-integrity-resolution | high | RESOLVED AS FORMAL CARRY-FORWARD - historical non-atomic landing recorded

Commit f66bfe9909 remains the actual landing commit and independently contains 247 paths. It absorbed the 51-path semantic campaign together with concurrent shared-tree work, so historical atomicity was not achieved and is not retroactively claimed. The commit was created externally after the review index was prepared; rewriting shared history now would risk other owners' landed work and is therefore forbidden. Following the established S09 delivery-integrity precedent, this audit records the exact landing and binds the corrective process requirement: future shared-worktree campaign delivery must use an explicit path-scoped ownership inventory, a campaign-only verified index, and a final staged-path census before commit. The historical breach is closed as a documented carry-forward rather than by unsafe history rewriting.

## Final verification

- Independent UTF-8 code-point proof found the single correct U+00F3 in the S61 official label.
- The full Spanish-stem conformance module passed: 5 passed in 83.02 seconds.
- Focused NIF-IVA, MCP meta-tool, and command-ranking modules passed: 44 passed, with 22 integration-marked tests deselected by the configured unit lane.
- Scoped Ruff over the 50 Python campaign paths passed.
- The whitespace check for commit f66bfe9909 passed.
- The commit-relative census confirmed 247 paths in f66bfe9909; the review does not misrepresent that commit as atomic.

## Final verdict

PASS. The semantic 51-path IVA hard cut is correct: internal authored terminology uses IVA, repeated-stem prose is absent, exact external and official tokens are preserved, admissions are precise and exercised, the strengthened test is non-tautological, and no compatibility alias or mirrored business logic was introduced. The official-label encoding defect is resolved. Delivery integrity passes only under the explicit historical boundary above: f66bfe9909 was a non-atomic external 247-path landing, remains unrevised to preserve shared history, and is carried forward as a binding path-scoped delivery requirement rather than concealed or claimed as compliant atomic delivery.
