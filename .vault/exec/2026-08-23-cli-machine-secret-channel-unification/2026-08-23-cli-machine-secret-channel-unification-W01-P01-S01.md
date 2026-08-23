---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d07ca58678d75bd1532519f59bd2307fb12c3192873edf4eabd2d3049e1a1474'
step_id: 'S01'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-machine-secret-channel-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-08-23-cli-machine-secret-channel-unification-plan placeholders are machine-filled by
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
     The Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and build the shared strict frozen payload base, reusable Typer option annotations, typed selection result, conflict-before-read selector, and bounded one-shot reader while retaining fd0, refusing negative descriptors and fd1/fd2, and deleting old helpers atomically after migration and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_secure_input.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and build the shared strict frozen payload base, reusable Typer option annotations, typed selection result, conflict-before-read selector, and bounded one-shot reader while retaining fd0, refusing negative descriptors and fd1/fd2, and deleting old helpers atomically after migration

## Scope

- `src/cadrumo/entrypoints/cli/_config/_secure_input.py`

## Description

- Ground the transport boundary in semantic code and accepted-ADR discovery, then confirm every live consumer by exact-symbol search.
- Introduce `MachineSecretPayload` as the single strict, frozen base for command-owned payload models.
- Declare reusable Typer annotations for the two globally uniform machine-secret flags.
- Separate conflict-before-read channel selection from bounded payload materialisation with typed immutable selection state.
- Preserve the existing bounded stdin reader and one-shot descriptor reader, including local closure, fd 0 support, and negative/fd 1/fd 2 refusal.
- Retain the delegating `resolve_secrets_channel` wrapper until the command migration Steps remove its remaining consumers atomically.

## Outcome

The shared module now exposes one canonical capability for payload strictness, option declaration, side-effect-free channel selection, and bounded channel reading. The selector represents stdin, inherited descriptor, or absence explicitly and refuses a dual-channel invocation before reading either source. Existing callers remain functional while later Steps migrate them to the typed API.

## Notes

Focused Ruff, `ty`, import, shared-option materialisation, and secure-input tests passed. Project-configured BasedPyright reported no diagnostic for the changed module; invoking it directly against one file surfaced two pre-existing unnecessary-ignore diagnostics in the Windows-only console probe because that invocation bypasses the project scope/configuration.

Comprehensive parser and descriptor lifecycle coverage belongs to S02. The old public stdin/fd readers and `resolve_secrets_channel` are intentionally deferred: live commands still consume them, so deleting them here would violate the plan's atomic-migration requirement. S06 through S10 must move those consumers before S12 removes the wrappers and obsolete exports.
