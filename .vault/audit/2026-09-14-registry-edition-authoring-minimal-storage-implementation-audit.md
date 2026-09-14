---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:65883c222ad12316c18d494f72dc4f646300e4dd629882029710a967d8efec3e'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-edition-authoring with a kebab-case feature tag, e.g. #foo-bar.
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

# `registry-edition-authoring` audit: `Minimal registry storage implementation`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Minimal registry storage implementation | {level} | {summary}

     followed by a paragraph carrying the detail. Minimal registry storage implementation is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

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

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
