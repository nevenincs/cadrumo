---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S23'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S23 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Close the code-review findings on the remediation itself by promoting the one-sided link direction to a core enum consumed by the domain record and the operator payload, carrying typed rows into the notice builder instead of serialised mappings, and cross-linking the concrete repository parameters in the linking docstring, gated on the docstring core-struct module returning green and ## Scope

- `src/cadrumo/core/_invoice_link.py`
- `src/cadrumo/domain/invoices/_service.py`
- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `src/cadrumo/application/invoices/_linking.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Close the code-review findings on the remediation itself by promoting the one-sided link direction to a core enum consumed by the domain record and the operator payload, carrying typed rows into the notice builder instead of serialised mappings, and cross-linking the concrete repository parameters in the linking docstring, gated on the docstring core-struct module returning green

## Scope

- `src/cadrumo/core/_invoice_link.py`
- `src/cadrumo/domain/invoices/_service.py`
- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `src/cadrumo/application/invoices/_linking.py`

## Description

- Declare the one-sided link direction as a closed enum in the innermost core ring, replacing the inline two-token literal the domain record carried, so one taxonomy serves the domain, the operator payload, and the tests.
- Consume the enum in the domain consistency record and at both construction sites, and re-point the four test modules that asserted the raw tokens at enum members.
- Type the operator payload's direction field as the same enum instead of a bare string, and project typed payload rows at the check verb rather than serialised mappings.
- Take the typed consistency rows into the notice builder instead of a mapping bag, so identifiers and the closed axis stay typed up to the envelope.
- Add an Args section to the linking writer's docstring cross-linking both concrete repository parameters, which the core-struct docstring gate requires once the parameters name anchor types.

## Outcome

The closed direction axis is now typed from the domain record through to the operator envelope, and the docstring core-struct module is green again.

Strict payload validation caught a real defect during this step rather than after it: projecting the rows through a JSON dump produced a bare string for the enum field, which the strict model refused, so the verb exited non-zero. The fix was to construct the typed payload rows directly. Had the payload field stayed a bare string, the same dump would have passed silently and the downgrade would have shipped.

## Notes

Three findings arrived from review after the earlier Steps had closed, all on the remediation rather than the campaign's original scope. They are tracked here as one Step instead of reopening closed records.

The docstring gate red was mine and self-inflicted: narrowing the two parameters from the domain protocols to the concrete adapters made them anchor types, which obliges the function docstring to cross-link them. A pre-existing method role naming the same class does not satisfy the gate, because the role regex captures only the final path segment.

The core facade and its generated API stub both carried a concurrent campaign's uncommitted additions. Rather than commit their work under this change, both files were staged as HEAD-anchored own-edits-only patches through the index, leaving their working-tree state untouched, and the staged set was verified to carry none of their markers before the commit.
