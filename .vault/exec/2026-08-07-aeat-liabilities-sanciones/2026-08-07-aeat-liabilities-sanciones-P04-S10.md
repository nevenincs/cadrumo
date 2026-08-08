---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:0408720e7b9dead1e80080339985618b0a6d8c9286b531d72e6c6814df089540'
step_id: 'S10'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-liabilities-sanciones with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-08-07-aeat-liabilities-sanciones-plan placeholders are machine-filled by
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
     The Add the deudas CLI entrypoint and its list, view and latest payload models as new OutputSchema subclasses in the existing _app_live_payloads module, mirroring the expedientes payload shapes. Introduces tr help keys, so this row and S11 and S12 land as ONE unit with P07.S23 rather than independently: the codebase-to-locale parity gate is tree-wide and immediate, so the moment a tr key exists in source it must exist in all four catalogues and ## Scope

- `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py`
- `src/cadrumo/entrypoints/cli/_app_live_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the deudas CLI entrypoint and its list, view and latest payload models as new OutputSchema subclasses in the existing _app_live_payloads module, mirroring the expedientes payload shapes. Introduces tr help keys, so this row and S11 and S12 land as ONE unit with P07.S23 rather than independently: the codebase-to-locale parity gate is tree-wide and immediate, so the moment a tr key exists in source it must exist in all four catalogues

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py`
- `src/cadrumo/entrypoints/cli/_app_live_payloads.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
