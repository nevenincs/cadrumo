---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:080ff84fa99ddd606e7c5f80538a7d1f266c31bcb7434cb7fa07edffbfddc46f'
step_id: 'S247'
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
     The S247 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Resolve changed-surface Ruff import order and partition every remaining type diagnostic to its owning implementation or fixture until the scoped global proof is clean and ## Scope

- `src/cadrumo/ and src/cadrumo-harness/ and dev/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Resolve changed-surface Ruff import order and partition every remaining type diagnostic to its owning implementation or fixture until the scoped global proof is clean

## Scope

- `src/cadrumo/ and src/cadrumo-harness/ and dev/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Trace campaign quality ownership with Vaultspec RAG, the W06.P12 plan scopes, execution records, and the exact Python paths changed by their commits.
- Run Ruff and ty over the broad product, harness, and developer-tool trees to partition current diagnostics by campaign and concurrent owner.
- Prove the exact 41-file campaign surface, including profile custody, observability, sequence parsing and comparison, CLI action census, and harness MCP paths.
- Narrow masked sequence envelopes through runtime mapping checks before structural comparison.
- Narrow schema-derived regex metadata through a runtime string check before returning it from the parser test helper.
- Declare every campaign census AST visitor override explicitly through the standard typing contract.
- Run focused behavioral suites and submit the bounded repair for independent formal review.

## Outcome

The exact 41-file W06.P12 Python surface passes Ruff and ty with no diagnostics. Sequence comparison now proves both recursively rebuilt mask results remain mappings at runtime before canonicalisation and path diffing, while the schema-pattern test proves Pydantic metadata supplies a string before returning it. Every campaign-owned AST visitor override is explicitly declared without casts, ignores, configuration exclusions, or diagnostic baselines. The focused behavioral lanes pass 91 tests.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- A broad diagnostic inventory over `src/cadrumo`, `src/cadrumo-harness`, and `dev` reported 22 Ruff findings and 942 ty diagnostics. Ruff findings belong to the active uncommitted TUI-secret relocation; the remaining ty inventory spans unrelated repository fixtures, entrypoints, registry, and agent-evaluation surfaces. None is on the exact campaign file set after this repair.
- The reproducible surface is the sorted, existing `.py` union from `git show --pretty= --name-only` over campaign implementation commits `67b72d4afd`, `022da104e0`, `2ec2921fd1`, `f7694d3ae2`, `98f34aa7b01`, `2be1f36529`, `6e9b859b3f`, `c3ecef84dd`, `c890ecea4b`, and `a2393b74ee`. This yields 41 files. The commits respectively own S237 harness guidance, S238 profile deletion, S239 golden masking, S240 parser/result expectations, S241 comparison, S245 quality/harness recovery, and S246 watchdog lifecycle.
- The shared worktree commit `04ea7186d0` captured three S247 implementation files alongside independently owned CI and locale work while verification was running. This is recorded as concurrent split provenance; the closing commit owns the corrected S240 parser-test narrowing and S247 lifecycle records and does not rewrite or revert the shared commit.
