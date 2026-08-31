---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:788f0e71dbef30676538911338f8cd87ac622e651d311e82b4ec8460f933ff06'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ci-lane-deconflation` audit: `P05 S132 independent code review`

## Scope

Independent review of P05.S132 across predecessor `06a7fbe31a`, closure `87c438dd30`, and current `87c438dd30`. Reviewed the approved CI-lane plan and ADRs, the S132 execution record, the exact 22 source and test paths, canonical import ownership, the 1,233-line cap, no-baseline claim, and the stated test evidence and S130 overlap exclusions.

## Findings

### s132-exec-record-integrity | high | The execution record is malformed and lacks the required external-failure evidence

`2026-08-05-ci-lane-deconflation-P05-S132.md` at `87c438dd30` opens with an empty delimiter at line 1, carries a complete unfrontmattered body at lines 3-42, places its metadata at lines 43-52, then repeats the complete body at lines 54-93. The governed CLI emits a PyYAML parse warning and falls back to a simple parser, so the record is not a valid execution document. It also records only the 60-test focused run and its 14/46 selected subset; it contains no executable command and literal result for the requested 80/81 source-mesh run that establishes the one external S130 failure. This prevents the required evidence from being reconciled or trusted.

Resolved by `40e5704915`: the record now has one frontmatter block and one body, and both the governed frontmatter and exec-mapping checks return no diagnostics. Its literal two-file command records `1 failed, 80 passed`, raw collection `81`, and zero deselection, names the S130-owned IVA-refusal failure, and retains the 60/0, 14/46, and size evidence.

### duplicate-operation-logger | low | The relocated operation module initializes the same logger twice

`source_resolution_operations.py` lines 36 and 38 both assign `_log = get_logger(__name__)`. The second assignment is behaviorally harmless but is newly introduced source duplication in the canonical owner.

Resolved by `40e5704915`: the canonical owner now contains one `_log = get_logger(__name__)` initialization.

## Recommendations

- Replace the S132 record with one CLI-owned valid frontmatter block followed by one body. Preserve the complete existing literal ruff, 60/0 collection and pass, 14/46 subset, and size evidence; add the exact reproducible source-mesh command, its verbatim 80/81 outcome, the named S130-owned failure, and why the overlap/core hunk exclusions do not conceal it.
- Remove the duplicate logger initialization while retaining the logger name used by the storage-degradation test.

Both recommendations are complete. The repair changed only the S132 execution record and the canonical operation module; it did not alter a plan, baseline, or S133 surface.

The source disposition is otherwise approved: all nine moved operations have exactly one definition in the public `source_resolution_operations.py`; `_source_mesh.py` retains no operation implementation; production and test consumers import the canonical module directly; no facade or cross-package private import was introduced. The semantics and ownership checks are preserved by the moved tests, the recorded focused outcomes are internally consistent, and the source cap is 1,233 against 1,250 with no S132 baseline change.

