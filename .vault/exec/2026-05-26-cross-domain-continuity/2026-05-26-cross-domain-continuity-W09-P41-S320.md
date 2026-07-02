---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S320'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S320 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The G4 retroactive violation in commit c27f35398  -  added iva_category_help and counterparty_eu_member_state_help keys by hand to en/es/ca/hu.yml without scaffold evidence and ## Scope

- `re-scaffold these four keys via python -m aeat.locales scaffold then verify their structural shape matches the canonical pattern`
- `per architect standing-gate enforcement`
- `src/aeat/locales/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# G4 retroactive violation in commit c27f35398  -  added iva_category_help and counterparty_eu_member_state_help keys by hand to en/es/ca/hu.yml without scaffold evidence

## Scope

- `re-scaffold these four keys via python -m aeat.locales scaffold then verify their structural shape matches the canonical pattern`
- `per architect standing-gate enforcement`
- `src/aeat/locales/`

## Description

- Ground the retroactive locale-scaffold row with `vaultspec-rag` code search for `iva_category_help` and `counterparty_eu_member_state_help`.
- Inspect the plan row, the four locale catalogues, and the live `aeat.locales` scaffold and audit CLI surface.
- Run `uv run --no-sync python -m aeat.locales scaffold` to re-normalize the locale catalogues through the project CLI.
- Run `uv run --no-sync python -m aeat.locales scaffold --check` and `uv run --no-sync python -m aeat.locales audit`.
- Verify the two requested help leaves remain present in `en.yml`, `es.yml`, `ca.yml`, and `hu.yml`.

## Outcome

- Closed the retroactive compliance gap through the locale CLI.
- `scaffold` produced real catalogue canonicalization diffs in the four locale files, but did not need to add the two target help leaves; those leaves were already structurally present in every locale.
- `scaffold --check` reported `ca.yml: ok`, `en.yml: ok`, `es.yml: ok`, and `hu.yml: ok`.
- `audit` reported `ca.yml: ok`, `en.yml: ok`, `es.yml: ok`, and `hu.yml: ok`.

## Notes

- The shared worktree was already dirty before this step, including existing `.vault/index` changes. This step did not intentionally edit generated index files.
- Residual risk is limited to unrelated locale canonicalization churn emitted by the authoritative scaffold command while closing the requested retroactive evidence gap.
