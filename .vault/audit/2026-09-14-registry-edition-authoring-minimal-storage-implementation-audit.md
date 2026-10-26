---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:e31c64b8eb38b3414a6897af167fe6829d612e1d68aef5961896acdb41111204'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# `registry-edition-authoring` audit: `Minimal registry storage implementation`

## Scope

Lossless declaration packing, schema-default elision, unchanged-member omission and evidence standardization across all 58 bundled modelos. Source changes are guarded against concurrent writers; exact originals and per-file hashes are retained. This audit distinguishes source equivalence from full authority conformance and actual rendered filing bytes.

## Findings

### apply-preflight | high | A late concurrent edit can leave a partially published modelo

`pack_modelo` validates and mutates each write target in the same loop (`compact.py:186-193`), then does the same for deletions (`compact.py:194-198`). If a later target changed, disappeared, or became newly occupied after the earlier whole-tree check, the function raises only after earlier replacements have landed; the CLI then catches the exception and continues to other modelos. The final fingerprint check is later still (`compact.py:199-200`), so an edit to an otherwise untouched file also detects drift only after all planned writes and deletions. The retained backup makes recovery possible but does not satisfy the promised all-or-nothing publication boundary. The focused tests have no concurrent-edit detector tooth and therefore cannot catch this partial-apply path. Preflight the complete live fingerprint and every exact write/delete condition immediately before the first mutation, and publish through a recoverable atomic strategy or roll back owned mutations on any failure.

### comment-association | medium | Packing preserves comment text but destroys its declaration association

`toml_comments` returns only the text from `#` onward (`compact.py:60-85`), and packing concatenates every extracted comment at the beginning of `0001-declarations.toml` (`compact.py:141-147`). A trailing evidence or label comment that originally identified one row is therefore detached from that row; indentation, blank-line grouping, fragment boundaries, and placement are also discarded. The test at `test_compact.py:43-51` checks only the extracted comment list, so it positively passes this lossy relocation while naming comment preservation. Preserve each comment with its declaration (or retain an explicit source-to-member association) and add a fixture proving row-specific trailing and leading comments remain attributable after consolidation.

### comment-association-resolution | low | Original comment placement is now retained on the concatenable path

Resolved on re-review. `compact.py:197-228` concatenates fragment text in the compiler's POSIX-path order, and `test_compact.py:44-54` now proves each inline evidence comment remains attached to its row while locales and declaration order remain unchanged. The fallback for syntactically non-concatenable singleton-table fragments keeps the original commented source as explicit context before the canonical projection, so it does not silently discard the association.

### apply-preflight-resolution | low | Whole-tree preflight and focused late-edit teeth now precede bounded publication

Partially resolved on re-review. `publish_staged_tree` performs a fresh whole-tree equality check before its first mutation (`compact.py:118-121`), uses same-directory replacement for forward writes, rolls back completed paths on the two injected late-refusal shapes, and the CLI stops applying further modelos after a failure (`compact.py:298-303`). `test_compact.py:93-146` supplies the previously missing real-filesystem teeth. The remaining rollback race is recorded separately below.

### rollback-publication | high | Recovery can overwrite a racing writer and is not interruption-safe

The forward path uses same-directory atomic replacement, but recovery restores an original with direct `shutil.copy2(originals / name, target)` after a separate digest check (`compact.py:146-156`). A writer that changes `target` after line 148 and before line 154 is overwritten, contradicting the function's stated guarantee that recovery never overwrites concurrent bytes. `copy2` is also non-atomic at the destination, and any exception in one recovery operation escapes the recovery loop, leaving earlier or remaining completed paths unrestored. The two focused concurrency tests inject edits before the digest check and therefore do not exercise either recovery race or an interrupted recovery. Restore through a same-directory temporary plus atomic replace, revalidate immediately before replacement, keep attempting every owned rollback after an individual recovery failure, and report all unrecovered paths without claiming concurrent bytes were preserved.

### rollback-publication-resolution | low | Capture-before-compare publication preserves racing bytes and continues recovery

Resolved on final bounded re-review. `replace_if_unchanged` now stages replacement bytes beside the target, renames an existing destination to a private displaced path before comparing its digest, and installs with non-overwriting `os.link` (`compact.py:112-155`). A destination created during the gap makes installation fail rather than overwrite it; changed captured bytes are either restored to their name or retained at the reported displaced path. Forward publication and rollback share this helper, journal entries are recorded before mutation, and `publish_staged_tree` catches each ordinary recovery refusal independently so remaining entries are still attempted (`compact.py:169-195`). `test_compact.py:150-171` injects racing bytes immediately before capture and proves they survive at the target. No concrete remaining data-loss path was found in this bounded check.

### delta-help-localization | high | Fallback-key movement can change help text while the proof reports equality

`semantic_value` removes sibling occurrence keys from `localization_keys` and compensates only by resolving labels in every supported language (`delta_compact.py:32-50`). A casilla's public `get_help` behavior derives a parallel `.help` key chain from those same localization keys (`schema_surfaces.py:434-437`). Two occurrence keys can therefore resolve the same label but different help text; dropping the successor row moves the fallback source, the normalized localization-key comparison ignores that movement, and `resolved_labels` remains equal, so `differences` accepts a user-visible help change. The three focused delta tests contain bindings only and never exercise casilla fallback movement. Compare resolved help as well as labels for every supported language, and add a real-loader casilla fixture whose predecessor and successor labels match while their help strings differ; the drop must be refused.

### delta-help-localization-resolution | low | Source-omission proof now compares both localized casilla surfaces

Resolved on focused implementation review. `semantic_value` records resolved label and resolved help values for every supported language before allowing sibling occurrence fallback keys to move (`delta_compact.py:55-73`). The help chain is derived exactly as the production casilla accessor derives it. The parameterized detector at `test_delta_compact.py:153-192` proves an unchanged fallback is accepted while a label or help difference is rejected.

### lineage-sidecar-projection | low | Target-only evidence projection preserves ownership and does not feed inheritance

No open finding in the bounded implementation. Whole-modelo sidecar membership, uniqueness and edge validation completes before `_with_lineage_claims` projects casilla claims (`_loader_internals.py:479-531`); a row already carrying either claim is refused as duplicate ownership. Projection rebuilds only the current typed revision after raw inheritance is complete, retains `lineage_attestations` as the authored authority, and therefore cannot propagate the target edge's claim into grandchildren. The delta proof removes a casilla sidecar carrier only when its projected origin, evidence, and ordered legal/source references exactly match the resolved target row (`delta_compact.py:36-54`); all row fields remain compared. Focused real-loader tests cover relocation, typed equality, grandchild isolation, duplicate ownership, changed evidence/citations, and both localized text surfaces.

## Recommendations

The reviewed publication, comment-association, localized-help and evidence-projection findings are resolved. Keep complete typed-field comparison (including serialization-excluded fields), ordered references, label/help resolution, exact-edge evidence validation and race-preserving publication as transformation gates.

The final combined proof passed for all 58 modelos: 20,551 TOMLs became 1,938 and 793,421 authored leaf occurrences became 736,787. The work removed 46,241 explicit schema defaults and 967 redundant members, including five M390 evidence-bearing rows. Generated export and locale files remain byte-identical. Detailed field-path enumeration and fingerprints are in `.logs/audit-runs/2026-09-14/registry-storage-fields.json` and `registry-storage-proof.json`; the condensed human overview is `registry-storage-overview.md` in that directory.

Focused transformation and fact-scope tests passed (32). The stable directory-loader suite passed 21 and failed three pre-existing tests expecting the retired global parameters catalogue. Those failures are not storage-proof failures, but the suite is not green. The delta diagnostic suite passed 146 tests; the final chain diagnostic suite passed 59, including duplicate-target and row-plus-sidecar ownership refusals. Malformed sidecars produce an explicit diagnostic limitation rather than a grounding claim.

The authority artifact was regenerated through the owning pipeline (exit 0, 58 modelos). That command currently uses structural compilation, not full conformance; publication does not discharge grounding or filing obligations. The full compile, delta/chain aggregate screens and exclusive lineage seeder were not duplicated in this evidence-standardization pass.

Remaining work is substantive or separately owned: adjudicate unknown continuity using official evidence, repair obsolete global-parameter fixtures, and run actual export scenarios once their input/provider issues are resolved. Further root changes and reference lifting require their own proof. This reduction is not a claim of an absolute minimum encoding or registry-wide filing completion.

The feature metadata check reports 44 pre-existing execution-mapping problems (retired per-step records and a separate closed S65 without ledger evidence). S70 is recorded through the current consolidated ledger with 21,455 mechanical path rows. No historical execution records were deleted to suppress those findings.
