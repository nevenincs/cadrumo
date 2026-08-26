---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:407e66f61dcca8eea18c6745a0c2a40f1a2a463e76a0b152c557234614069164'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-W02-P05-S51]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-temporal-coverage with a kebab-case feature tag, e.g. #foo-bar.
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

# `registry-temporal-coverage` audit: `Modelo 184 historical epoch implementation review`

## Scope

Independent current-HEAD review of the Modelo 184 temporal split beginning in mixed commit `cfc47d71942338c8f9854e2935b0f676ed94648e` and its subsequent M184-only additions. The review covered the M184 corpus, registry revisions, exact shared legal-catalogue source hunk, locale catalogues, and focused tests; it read the temporal plan, authority-grade ADR/reference, research, and S51 execution record.

RAG first located the canonical record-design resolver, snapshot refusal path, and application-link validator. I then read those implementations and the affected registry files in full, verified each of the five official BOE PDFs against its downloaded byte count and SHA-256, and checked the official applicability clauses. The established 2015 `form_spec` entry is byte-for-byte unchanged and remains `form_spec`; the new raw PDFs are deliberately not assigned a `record_design_epoch`. The intended revision windows select as `2015`, `2016-2018`, `2019-2021`, `2022`, `2023-2024`, and `2025-y-siguientes`; the 2023--24 layout, source links, casilla offsets, constructs, bindings, deadline windows, and all four locale catalogues were inspected.

`static_layout` parity references are legitimate documentary layout evidence here: `runner_required = false`, no historical export layout or design epoch is created, and the focused parser test proves the historical PDFs still fail strict geometry. They are not independently a filing claim. The isolated M184 suite passed (`22 passed`). The shared claimed-year layout gate remains blocked before M184 assertions by unrelated active Modelo 200 registry failures; no root-conftest failure was observed in the focused M184 run.

## Findings

### modelo-184-historical-epoch | high | Layoutless applicability revisions advertise a filing surface

The `2015`, `2016-2018`, `2019-2021`, and `2022` revisions have `authority_grade = "applicability"`, no `export_layouts`, and raw BOE `record_design` sources without `record_design_epoch`; the canonical resolver therefore cannot select them as a generated layout. Each nevertheless declares `surface = "filing"`, consumer `cadrumo.application.filing`, and `requires_snapshot = true`. `ApplicationLinkDefinition` defines that declaration as an application surface requiring the registry authority. A FILING-grade snapshot later refuses each epoch by grade, but the inspection metadata has already advertised a filing surface for a known layoutless, parser-refused era. This conflicts with the required generic refusal and creates a false filing-capability claim.

The existing focused tests correctly pin every raw BOE hash, applicability window, strict-parser refusal, authority grade, empty export layout, and the 2022-to-2023 selector-overlap mutation. They do not make the false filing-link claim red: there is no assertion that the four historical revisions have no `filing` surface or filing consumer, and no mutation proof that an application link cannot reintroduce that surface. The directly analogous Modelo 390 applicability-only parser epoch instead asserts its extractor-only surface and absence of the filing consumer.

## Recommendations

- For `modelo-184-historical-epoch`, remove the four unsupported filing application links and any data retained solely to satisfy their lifecycle requirement. Keep only a non-filing surface that a real inspection or extraction capability supports; do not add a pseudo-layout, static anchor, or source epoch to preserve a filing declaration. If applicability-only header casillas require a filing link under the current validator, make the explicitly refused historical representation valid rather than using a filing surface as a structural workaround.

- Extend the M184 focused suite with mutation-sensitive checks that each historical epoch exposes neither `filing` nor `cadrumo.application.filing`, that requesting its FILING snapshot is refused, and that adding a filing link, export layout, or `record_design_epoch` to a raw historical source turns the test red. Preserve the existing selector, hash, strict-geometry, 2023--24 offset, locale, and deadline checks.

- Re-run the isolated M184 suite and the claimed-year gate after the active Modelo 200 worktree changes are resolved. Treat the present Modelo 200 failures as mixed-worktree isolation, not as evidence for or against this M184 finding.
