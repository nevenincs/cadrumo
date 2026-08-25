---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fad88d51e6767fce58960c372100e2717972d823cea7d9cc60d70f9358e9e4b1'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
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

# `deadline-window-revision-authority` audit: `s50 cli calendar parity`

## Scope

Audit the S50 CLI payload and all-profile rendering diff for thin-adapter boundaries, canonical overview ownership, schema fidelity, resolver reuse, and regression-test integrity.

## Findings

The repair deletes the competing compact calendar DTOs, validates application-built entries and events through the already-existing complete transport payloads, and uses the existing action resolver for warning remedies. No calculation, registry selection, filing-evidence merge, status, or cadence logic is introduced at the CLI boundary.

### warning-action-json | high | Resolved warning action required JSON-mode serialization

The first review found that a resolved Pydantic action had been inserted directly into a mapping passed to standard-library JSON encoding. The implementation now serializes that already-resolved action with `model_dump(mode="json")`; the finding is resolved.

### warning-action-envelope | high | Resolved warning action was one wire level too shallow

Clean detached verification showed that raw `ResolvedNoticeAction` JSON did not preserve the established declared-action envelope. The follow-up uses typed transport composition over canonical `ActionReference` and `ResolvedActionArgument` primitives, resolves once through the existing catalogue path, and emits the required nested identity plus sibling live CLI path. Both affected real-CLI cases pass and formal re-review accepted the repair; the finding is resolved.

## Recommendations

Accept S50. The two clean-verification regressions now pass; retain the seven-case targeted CLI set as the parity gate.
