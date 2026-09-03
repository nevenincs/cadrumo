---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v1'
body_hash: 'sha256:7665a587b014a046d082abf8e2c76ca222a9d22af0d3f5f71e4bbaa17533964b'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
  - '[[2026-09-02-unreachable-capability-tui-homepage-product-design-research]]'
---

# `tui-architecture` audit: `w08 p26 s373 review`

## Scope

Independent review of `W08.P26.S373` across `src/cadrumo/entrypoints/tui/devtools/home_candidates.py` and `src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` against the accepted navigation decision, Home product-design research and the exact compositor-measurement plan row. The review covered the four supported sizes, two themes, four shipped locales, all seven fixture states, horizontal and vertical scroll ownership, focus targets, compact launcher detail reach, keyboard cost, semantic restoration, projection-only authority and test integrity.

The dense compositor matrix contains exactly sixty-four live Textual frames: two candidates by four sizes by two themes by four locales. The state-floor matrix contains fourteen further live frames: two candidates by seven scenarios at `80x24`. Each matrix reads composed widget geometry rather than a screenshot proxy. Current implementation keeps every table at zero horizontal scroll, permits at most one visible vertical-scroll owner and restricts that owner to the candidate's outer content scroll. The due-driven candidate has exactly three visual-order focus targets, while the launcher has one chooser target and no more than five rows.

## Findings

### localized-copy-proof | high | A title marker did not prove genuine shipped-locale copy

The initial locale test established only that four complete frames differed and that each contained a translated Home title marker. That witness remained green while localized frames exposed English phrases in Ledger counts, declaration detail and stale timestamps. It therefore did not prove the requirement that Spanish, English, Catalan and Hungarian carry genuine interface copy while retaining invariant semantic row keys.

### launcher-keystroke-detail-proof | medium | The launcher traversal assertion was vacuous

The initial compact-launcher test bounded `row_count` at five and then asserted `row_index + 1 <= 5`, a consequence of the same bound. It did not establish that each Down key reached the next expected semantic identity or that detail copy changed with the live cursor. Broken arrow navigation or a permanently stale detail panel could therefore pass while the test claimed every preview was reachable within five keystrokes.

### semantic-restoration-proof | medium | Cached target equality did not prove the restored cursor location

The initial resize and reorder test compared `highlighted_target` with the requested restoration value and required only a non-null focused widget. The restoration helper itself assigned that cached target, so the assertion did not inspect the actual focused table row. A cursor restored by row index, a wrong table focus, or an off-viewport target could pass despite the semantic-restoration claim.

### final-localized-copy-disposition | low | Complete rendered copy now rejects the reproduced English leaks

The final locale test collects all rendered widget copy for both candidates, keeps semantic row identities invariant across locales, and rejects the reproduced English interface phrases in every non-English frame. Ledger count nouns, declaration-detail wording and stale timestamps now use locale-safe copy. `localized-copy-proof` is closed.

### final-launcher-disposition | low | Live cursor identity and distinct detail now prove bounded traversal

The final compact-launcher test derives the expected identities from the chooser's ordered live rows. Before every key transition it compares the actual DataTable cursor row and the screen's semantic highlight with the expected identity, records non-empty distinct detail for every target, and verifies the detail remains inside the terminal viewport. At most four Down keys plus Enter reach every one of at most five rows. `launcher-keystroke-detail-proof` is closed.

### final-restoration-disposition | low | Resize and reorder checks now inspect the actual semantic cursor

The final restoration test selects a non-first action, checks the focused DataTable's current row identity, resizes from compact to wide, and proves that same identity remains under the live cursor and visible. It reconstructs each candidate with reversed action order and proves the restored focused table cursor, rather than only cached screen state, still names that semantic identity and remains in the viewport. `semantic-restoration-proof` is closed.

## Recommendations

1. Preserve the live compositor denominator: sixty-four dense candidate/size/theme/locale frames and fourteen candidate/state floor frames.
2. Keep locale assertions over complete rendered widget copy and semantic row identities; a localized title alone is not evidence of localized interaction copy.
3. Keep keyboard and restoration gates bound to the DataTable's current semantic row key and visible region, not cached screen properties or arithmetic derived from row count.
4. Final focused Pytest reports 84 passing tests with every lane enabled. Ruff and ty pass; Basedpyright reports zero errors and zero warnings. No critical, high or medium finding remains open. `W08.P26.S373` may close.
