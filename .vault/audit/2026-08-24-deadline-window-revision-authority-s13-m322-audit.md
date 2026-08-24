---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:19db19246b0c5db61b9a6cabf9b45158f78d73fc2f91ed62f8233abca120abe5'
related:
  - '[[2026-08-24-deadline-window-revision-authority-plan]]'
  - '[[2026-08-24-deadline-window-revision-authority-W02-P04-S13]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `deadline-window-revision-authority` audit: `s13 m322`

## Scope

Independently review W02.P04.S13 for primary-source fidelity, exact canonical ownership, authority multiplicity, citation closure, direct-debit restraint, test bite, and absence of redeclared deadline architecture.

## Findings

No findings. The official AEAT 2022 calendar confirms M322 presentation closes for periods 01 through 11, and the bundled 2023 calendar confirms period 12 closes on 30 January 2023. The 2022 domiciliation table names monthly Modelos 303 and 353 but not 322, supporting the explicit absence of `payment_cutoff_on` for every M322 row.

All twelve coordinates occur only beneath revision `2008-2022`; `select_revision` chooses that owner for every month, and `ValidatedRegistryAuthority.deadline_windows` returns exactly twelve ordered rows. Construct membership and source closure are complete. The bundled PDF byte count and SHA-256 match its catalogue record. Thirteen focused tests and Ruff passed.

Vaultspec RAG semantic searches for `M322 monthly filing deadline windows canonical revision ownership` and `deadline window revision authority M322 monthly materialization`, followed by exact-symbol confirmation, found the existing `select_revision`, `ValidatedRegistryAuthority.deadline_windows`, core `Period` and `registry_period_kind`, and `resolve_filing_window` authorities. The engine method with the same public noun delegates read-only to the registry authority. No selector, resolver, cadence authority, period parser, deadline catalogue, or source map was redeclared.

## Recommendations

None.
