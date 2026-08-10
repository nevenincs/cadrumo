---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d66e7bff7c6f49a763c76398f7be8b6b6ab6826b0b273852602fc11d7a125950'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
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

# `aeat-export-fragment-generator-authority` audit: `S11 atomic export publication code review`

## Scope

Independent S09/S10/S11 review of the internal export provenance manifest, isolated-tree validation, and atomic export-only publication. Checked the accepted generator-authority decision against the current implementation and its real-filesystem tests, including target authority isolation, manifest placement and loader exclusion, stale sibling refusal, recovery mechanics, and legacy-tree non-input constraints.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### S11 atomic export publication code review | {level} | {summary}

     followed by a paragraph carrying the detail. S11 atomic export publication code review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### legacy-target-preflight | high | First hard cutover refuses an opaque pre-generator export

`publish_validated_generated_export_tree` calls `_verify_generated_export_package` on an existing `target_export_root` before staging its rollback directory. That verifier requires and parses the new internal `_generation.provenance.json`, so the manual/legacy export tree that S11 is intended to replace cannot be published at all. This contradicts the function contract that prior export content is an opaque rollback directory and is never parsed or used as semantic input. `test_publication_replaces_only_export_and_removes_opaque_backup` constructs its old target via the current renderer, so it already contains the new manifest and cannot prove the required first-cutover case.

### revision-root-sidecars | medium | Publication persistently writes outside the export-only boundary

The transaction journal is placed at `revision_root / "._generation-publication.json"` and `exclusive_file_lock(target_export_root)` leaves the permanent `export.lock` sidecar beside `export/`, both under the revision root rather than inside the generated export tree. The stated S11 boundary is export-only and excludes revision non-export authority; the test snapshots only non-export `*.toml`, so it neither detects nor constrains these persistent/non-export mutations. Use a transaction/lock location outside the revision authority tree and add a whole-revision byte/member assertion.

### legacy-target-preflight-resolved | low | Re-review confirms the legacy target remains opaque

Resolved. The cutover no longer verifies an existing target before staging it as the registry-root rollback directory; manifest, digest, and loader checks apply only to the candidate and post-cutover target. The real-filesystem cutover test now removes the old target's internal manifest before publication and succeeds, proving the first generated replacement does not parse, copy, merge, or semantically depend on the legacy export.

### revision-root-sidecars-resolved | low | Re-review confirms transaction artifacts are outside the revision tree

Resolved. The journal and advisory lock now derive from a transaction-scoped identity under the target registry root, while rollback siblings remain there too. The cutover proof asserts that neither `export.lock` nor the journal exists under the revision root after publication; the focused publication suite passed all nine real-filesystem tests on Windows.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
    architecturally significant recommendation names the decision a
    follow-on ADR must make; the decision itself is never recorded here. -->

- For `legacy-target-preflight`, treat an existing target strictly as an opaque regular rollback tree: do not load its manifest, digests, or loader semantics; prove publication from a real legacy target without `_generation.provenance.json`.
- For `revision-root-sidecars`, move the journal and lock out of the revision tree, then prove that only the export subtree changes and that no non-export members remain after success, rollback, or recovery.
