---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S16'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
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
     The Gate every Google-write verb (verify, push, probe --no-read-only) on google_export with a no-allowlist conformance test (honesty review H1) and ## Scope

- `src/aeat/entrypoints/cli/_config/_google.py`
- `src/aeat/entrypoints/cli/_config/_google_sync_calc.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Gate every Google-write verb (verify, push, probe --no-read-only) on google_export with a no-allowlist conformance test (honesty review H1)

## Scope

- `src/aeat/entrypoints/cli/_config/_google.py`
- `src/aeat/entrypoints/cli/_config/_google_sync_calc.py`

## Description

- Route `calc verify` (creates + writes a Drive spreadsheet via `apply_export_plan`), `sync push` (mirrors secure-object ciphertext to Drive), and `sync probe --no-read-only` (sentinel Drive write) through the same `resolve_active_capability(GOOGLE_EXPORT)` refusal that `calc export` uses.
- Gate `probe` only on its write arm — the read-only connectivity probe stays open.
- Add a parametrized conformance test asserting every Google-write CLI leaf refuses with the capability message when `google_export` is off; the gate fires before any Google call, so it is deterministic without credentials.
- Absorb a broken-import regression: the two CLI config files imported `resolve_active_profile` from the deleted `_profile_binding` module — corrected to the renamed `_active_profile`.

## Outcome

Closes honesty-review finding H1 (and H2 by extension): the ADR claim that "the Google export entry points check `google_export`" is now true for every entry point. 9 capability CLI tests pass (4 new H1 cases) and the CLI builds. Committed as `fe474ff1d`.

## Notes

The commit was made with a bare `git commit` (no pathspec) and, due to the shared index, swept peer-staged work (a `filing/reconciliation` package removal + regenerated api stubs) into it. The resulting tree was verified consistent: clean `pytest --collect-only` (15960 collected, no import errors), conformant `apidocs scaffold --check`, no dangling imports of the removed package. The lesson (always `git commit -- <pathspec>`) is recorded in the close audit; the bundled peer work is committed, not lost.
