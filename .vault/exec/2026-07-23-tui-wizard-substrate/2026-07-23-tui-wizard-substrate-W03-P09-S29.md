---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S29'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S29 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Run the docs build and documented-command conformance gates green, with owner triage recorded for any unrelated peer failures and ## Scope

- `docs/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the docs build and documented-command conformance gates green, with owner triage recorded for any unrelated peer failures

## Scope

- `docs/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Regenerate apidocs stubs in the retirement commit (two stale stubs removed, wizard and tui toctrees refreshed); `scaffold --check` clean.
- Run the documented-command and JSON-schema conformance gates: green (independently re-verified at pushed HEAD, 501 passed at integration scope).
- Run the full docs build gate (`dev/docs/tests/test_docs_build.py`) with complete on-disk log capture: 8 failed, 15 passed.

## Outcome

Every substrate-owned docs surface is green: the apidocs tree matches the module tree, no orphan stubs, conformance gates pass, and the wizard/flows/tui reference pages build. The docs build gate is red only on peer-owned in-flight work (see Notes); no failing surface belongs to this campaign.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- Owner triage: all 8 docs-build failures reduce to ONE signature — `CadrumoError subclass cadrumo.application.auth._apoderado.ApoderadoRepresentedNifInvalidError is missing a declared ErrorCode registry entry`, raised by the `cli-sequence` directive on every build variant (nitpicky, user-scope, es/ca/hu localized, site-identity, sequence-widget). The class exists only in a peer campaign's uncommitted working-tree edits to the auth/apoderado files; the registry row lands with their commit. The gate's own message anticipates exactly this concurrent-process state.
- The step stays open until the docs build is re-run green after the peer lands; the substrate side is complete.
