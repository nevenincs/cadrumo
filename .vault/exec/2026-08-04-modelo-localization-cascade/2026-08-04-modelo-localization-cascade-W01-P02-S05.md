---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:b30d5844bf205fbdf0322c3ce615e69bf0b30f842cd149860b05e1f3256182c7'
step_id: 'S05'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-localization-cascade with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Emit a sealed source manifest and unresolved review register with hashes, drift fields, and leaf state and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit a sealed source manifest and unresolved review register with hashes, drift fields, and leaf state

## Scope

- `dev/registry/migration`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Re-ground the manifest boundary with `vaultspec-rag`, the accepted ADR, and both localization research records.
- Bind S05 to the immutable S01 corpus fingerprint and S04 structural classification, then read the real public registry loader.
- Index each schema casilla source and loader-winning locale leaf without writing registry data or migration output.
- Record raw values, old resolved values, fallback state, source scope/path/hash, normalized value hashes, existing leaf states, drift fields, review status, and an empty emitted target.
- Seal the complete observation stream and derive the unresolved continuity-candidate review register without promoting provisional identity.
- Add the open pre-emission review gate for placeholder deletion and year-parameterized label decisions before W02 staging.

## Outcome

Implemented the deterministic, read-only S05 source evidence boundary in `dev/registry/migration`.

The real bundled corpus produces:

- 126,192 sealed source observations: 144 grounded, 32,008 revision-exact, and 94,040 continuity candidates.
- 94,040 unresolved review observations across 2,354 migration-only candidate groups.
- 12,944 distinct schema/locale source files bound to the pinned corpus fingerprint.
- Leaf states of 84,084 absent, 32,607 authored, 9,453 mirrored, and 48 key-echo values.
- Stable manifest and unresolved-register SHA-256 seals, with no emitted targets.

The plan now carries open `W01.P02.S18` before W02 to adjudicate placeholder debt as
delete-versus-migrate and to decide whether year-embedded label families require an
explicit parameterized-label ADR amendment. No parameterized-label outcome is encoded
by S05.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The first pre-cache full-corpus probe exceeded the 15-minute tool limit and is treated as
unverified. After indexing schema ownership once per source file, the bounded real-corpus
probe completed in 92.9 seconds. The focused S05 test initially exposed two fixture path
assumptions; both were corrected against real source ownership, and the focused file then
passed 2 tests in 120.24 seconds.

No production schemas, locale data, readers, live registry, or migration output were
modified. The next review gate must complete before any emitter or catalogue staging is
implemented.
