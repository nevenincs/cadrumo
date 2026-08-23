---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:fa0804766420062f05a1a0245f350447903647e321bf5131bd227c225e3f7c06'
step_id: 'S168'
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
     The S168 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The produce the strict complete 0177, 0181, and 0182 inventory domain projection and ## Scope

- `src/cadrumo/domain/contribuyente/inventory` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# produce the strict complete 0177, 0181, and 0182 inventory domain projection

## Scope

- `src/cadrumo/domain/contribuyente/inventory`

## Description

- Add a strict source-owned 2025 inventory projection for casillas 0177, 0181, and 0182.
- Reuse the canonical closing-authority resolver and retained continuity and conflict provenance.
- Derive purchase totals and fingerprints from canonically ordered complete acquisition-cost movements.
- Refuse missing, unreadable, out-of-period, inconsistent, and caller-overridden projection state.
- Add increase, decrease, equality, authority-selection, conflict, ordering, continuity, and forgery tests.

## Outcome

The inventory ledger now produces one complete activity-scoped projection. Casilla 0181 equals the admitted complete acquisition cost; casillas 0177 and 0182 are the mutually exclusive positive split of authoritative closing against opening. The result carries the selected authority, decision, continuity, physical observation, conflict, and acquisition fingerprints needed by the downstream resolver without accepting caller-authored outputs.

The projection revalidates the persisted ledger, requires the ledger-owned closing-authority record, calls the canonical authority resolver, and refuses incomplete purchase acquisition facts. Semantically equal movement orderings produce identical acquisition provenance. Nonzero acquisition totals require a nonempty unique fingerprint set.

Verification completed with 52 passing inventory-domain tests, clean Ruff and type-checker runs, and an independent formal review reporting zero findings.

## Notes

Semantic discovery was unavailable because the installed `vaultspec-rag` client was version 0.4.1 while the running service was 0.4.2; targeted ADR and source inspection supplied the required grounding. Review found and resolved result-provenance forgery gaps, insertion-order fingerprint drift, an accidental closing-decision field collision, divergent physical-value conflict omission, and empty or duplicate acquisition fingerprints for nonzero totals.

