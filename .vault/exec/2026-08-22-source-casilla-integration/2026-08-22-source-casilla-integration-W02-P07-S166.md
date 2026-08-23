---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3c5d0bd91f25e442ad126e8d812ac4fdcaef1689774184d64accb2ddc885f29d'
step_id: 'S166'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S166 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The replace bare closing-stock authority with a provenance-bearing physical-closing observation and prior-closing continuity contract and ## Scope

- `src/cadrumo/domain/contribuyente/inventory` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# replace bare closing-stock authority with a provenance-bearing physical-closing observation and prior-closing continuity contract

## Scope

- `src/cadrumo/domain/contribuyente/inventory`

## Description

- Replace bare ledger closing authority with immutable, evidenced physical-closing observations.
- Bind authority decisions, prior-year continuity, conflicts, and resolutions through canonical tamper-sensitive fingerprints.
- Enforce activity, year, date, cents, valuation-basis, evidence-role, temporal-causality, and selected-value invariants.
- Retain competing physical observations and conflict diagnostics regardless of the selected authority.
- Remove premature projection composition so S168 remains the sole projection owner.
- Hard-cut the domain `closing_stock` field without compatibility defaults.
- Add mutation, substitution, forgery, continuity, and provenance-retention tests.

## Outcome

The inventory domain now exposes a provenance-complete closing-authority contract. A physical observation carries closed evidence roles and content digests; a decision binds the exact observation and reviewer provenance; prior continuity binds the immediately preceding authoritative closing; and the resolution retains every contributing fingerprint and any valuation conflict. Both physical-selected and movement-selected decisions fail closed when their decision predates the named observation.

Focused verification completed with 50 passing inventory-domain tests, clean Ruff and type-checker runs, and an independent formal review reporting zero findings at every severity.

## Notes

S167 must remove or strictly refuse the still-present CLI `InventoryLedgerPayload.closing_stock` input shape while propagating the new physical-closing authority and continuity evidence through secure ingress. S166 intentionally does not expand into that application and CLI ownership. Projection composition remains assigned to S168.
