---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:7a930cc550764b0e5f10ca9e9f23f8a7232457a731421dbcb24750a762430ab9'
step_id: 'S01'
related:
  - "[[2026-08-05-arch-remediation-registry-format-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-registry-format with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-08-05-arch-remediation-registry-format-plan placeholders are machine-filled by
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
     The Correct the parity-gate claim in the rule source so it enumerates only the enforced assertions, and add the paragraph stating casilla section is ungated presentation and ## Scope

- `.vaultspec/rules/modelo-export-mirrors-official-structure.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Correct the parity-gate claim in the rule source so it enumerates only the enforced assertions, and add the paragraph stating casilla section is ungated presentation

## Scope

- `.vaultspec/rules/modelo-export-mirrors-official-structure.md`

## Description

- Verify the premise before editing: count section assertions in the workbook parity gate.
- Correct the rule's enforced-assertion list to the three properties the gate actually carries.
- Add a paragraph stating casilla section order is ungated presentation, with the reason.

## Outcome

The rule claimed the parity gate asserts "registry-declaration section order". It
never has. The gate carries no section assertion of any kind; what it enforces is
manifest-required casilla coverage matched on number and segmento, a number-format
facet on every numeric casilla, and a live formula on every computed casilla.

The claim is now the three enforced properties, followed by an explicit statement
that section order is deliberately ungated. Section is presentation - the plan emits
section headers so a human can read the workbook - while what must mirror the
official modelo is the casilla set and its numbering, both of which are gated.

An overclaiming rule is worse than a silent one: it sends a reader looking for
enforcement that is absent, and invites them to trust an unchecked property.

## Verification

The premise was measured, not assumed, before the rule was touched:

    grep -ciE 'section' src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_parity.py
    0

Zero section-related lines in the whole gate module, against a rule sentence
naming section order as enforced.

## Notes

The correction direction matters and is recorded in the rule itself: the claim was
corrected to match the gate rather than the gate extended to satisfy the claim. If
section order later earns enforcement, the assertion lands first.
