---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9da55c79c984c0bfcf8339e299f8f666f431907d43b85ea48c0562ead1b83da4'
step_id: 'S257'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S257 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Route CLI and manager censal apply through the canonical user-profile.censo-review operation, preserving one acquisition, encrypted reviewed operand, exact baseline, resume-without-reread, and apply_cotejo sole-writer authority and ## Scope

- `src/cadrumo/application/user_profile/_censal_operation.py and src/cadrumo/entrypoints/cli/_config/ and src/cadrumo/adapters/inbound/tui/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Route CLI and manager censal apply through the canonical user-profile.censo-review operation, preserving one acquisition, encrypted reviewed operand, exact baseline, resume-without-reread, and apply_cotejo sole-writer authority

## Scope

- `src/cadrumo/application/user_profile/_censal_operation.py and src/cadrumo/entrypoints/cli/_config/ and src/cadrumo/adapters/inbound/tui/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Trace the accepted censo-review operation, frontend callers, encrypted operand, baseline, resume path, and writer authority with semantic discovery and exact caller inventory.
- Route CLI apply and manager/TUI apply through one shared submit, start, project, respond, and settle driver.
- Present the exact typed review projection once and preserve the durable reviewed operand across continuation and restart.
- Validate successful terminal condition, declared effect, and typed censal outcome before a frontend reports success.
- Remove the direct censal writer bypass and enforce the surviving `apply_cotejo` caller set with an AST gate.
- Exercise real CLI/TUI presentation, encrypted application apply and rejection, post-response failure honesty, stale-baseline refusal, and restart without reread.

## Outcome

CLI `censo pull --apply` and the manager action now enter the canonical `user-profile.censo-review` operation. The operation performs one acquisition, persists its reviewed operand through encrypted operation custody, binds the exact profile baseline, and applies only through `apply_cotejo`. Rejection leaves the record unchanged, stale or failed continuation is never rendered as success, and restart resumes from the durable operand without another live read.

Scoped verification passed: 29 CLI, TUI, facade, and executor tests; five restart, operand, and stale-baseline tests; three real frontend apply, reject, and terminal-failure tests; two real TUI review tests; Ruff; and scoped ty. The structural gate parses production ASTs, rejects any `apply_censal_read` declaration, and pins the exact `apply_cotejo` caller inventory.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The first formal review rejected the temporary foreclosure because it did not implement ADR D9 and because its redeclaration proof was lexical. The second review confirmed full canonical routing but found terminal-state ambiguity and S257-owned hygiene debt; both S257 findings were corrected before final review.

The final independent review approved S257 with no remaining critical, high, or medium findings.

Concurrent shared-worktree activity created commit `916fc9517e`, which captured the main censo routing while this Step was executing, and later advanced HEAD with peer changes. Remaining whole-tree import-hygiene failures belong to an in-progress peer TUI relocation and unrelated test-debt changes; this Step did not rewrite, revert, or absorb those files.
