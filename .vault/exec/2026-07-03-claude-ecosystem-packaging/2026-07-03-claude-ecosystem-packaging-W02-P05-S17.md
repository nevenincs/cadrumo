---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S17'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Make the four aeat app registry verification verbs refuse instructively when the companion is required and absent and ## Scope

- `src/aeat/entrypoints/cli/registry.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make the four aeat app registry verification verbs refuse instructively when the companion is required and absent

## Scope

- `src/aeat/entrypoints/cli/registry.py`

## Description

- Add `guard_corpus_companion` to the registry corpus CLI module and wire it into the five verification surfaces: registry verify, workbooks verify, parity run, parity replay, and manuals verify — each refuses with `CliRefusedBoundaryError` naming the capability and the exact `aeat[corpus-sources]` install command when the companion is required and absent.
- Add the `cli.registry.errors.capability.*` and `corpus_companion_absent` locale keys across en/es/ca/hu.
- Export the companion vocabulary through the registry package facade.
- Add `test_registry_corpus_companion_guard.py` (2 passed).
- Commit `5ed126e524`.

## Outcome

- The CLI gate is instructive, never a silent black hole: split-install users are told exactly what capability is missing and how to install it.

## Notes

The executing agent's session was terminated by the account rate limit AFTER writing the implementation but BEFORE gating and committing. The coordinator verified the working-tree WIP (guard test 2 passed; locale `scaffold --check` ok across all four catalogues; JSON-schema conformance 116 passed; ruff clean), separated the S17 hunks from entangled peer WIP in the four locale files (an unrelated diagnostics campaign's uncommitted keys plus serialiser reflow), and landed the commit via a temp-index build with a compare-and-swap HEAD guard so neither the shared index nor the peer working-tree WIP was touched. Four pre-existing conformance failures observed during gating (`REFUSED_DOMAIN_RETENTION_FLOOR` citing a not-yet-registered `profile erase` verb, and related suggestion-conformance reds) were attributed to peer commit `3e5abe8190` (GDPR retention campaign) — outside this step's surface, not absorbed, reported per full-tree-gate-must-distinguish-owner.
