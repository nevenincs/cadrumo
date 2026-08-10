---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:65feb1e53adced76643063ef2740c56050440752239b02e7febf240e455a775d'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace cli-action-envelope-hardening with a kebab-case feature tag, e.g. #foo-bar.
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

# `cli-action-envelope-hardening` audit: `S18 refusal boundary action projection`

## Scope

Independent read-only review of `W03.P05.S18`: the shared CLI refusal boundary
that carries the already-typed S17 policy projection into JSON and text error
output. The review checked the accepted decision records, S16/S17 evidence,
the current boundary, root handoff, wire/error models, and the delta from
`550e1f619f`. It verifies transport only: exhaustive storage-policy assertions
remain S19 work and real recovery/retry remains S20 work.

## Findings

No critical, high, medium, or low S18 defect was found. A valid typed S17
projection replaces the root or group callback identity only with its preserved
requested leaf, then carries the same strict resolved action DTO through the
canonical JSON error member and deterministic text fields. The complete
condition, evidence, action, bindings, missing names, conditionality, and
no-recovery shape is emitted without reconstructing command or recovery prose.

Malformed projection markers raise rather than degrade to an untyped refusal.
Absent markers preserve unmigrated `CliRefusedBoundaryError` behavior for the
later W04/W05 producer slices. No suggestion compatibility field was restored.
The function-local handoff import avoids a CLI transport cycle; error-context
redaction and sandbox notice handling remain on the existing shared path.

The focused S18 and S17 integration modules passed 16 tests. Scoped Ruff,
format, and BasedPyright checks for the S18 files passed. The repository-wide
BasedPyright lane currently has 19 diagnostics in unrelated shared-worktree
files and none in the reviewed S18 files; this is a recorded verification
boundary, not an S18 defect.

## Recommendations

- S18 may close. Retain the malformed-marker and untyped-refusal regressions so
  future producer waves cannot silently widen this boundary.
- Keep exhaustive condition and binding assertions in S19, and recovery/retry
  dispatch proof in S20; neither is a prerequisite for this transport slice.
