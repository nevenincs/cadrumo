---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:c1566b367112e546c77757c0fc5acf1d955202cbd950142a4d18c128fceb432d'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

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

## Adjudication and resolution

The HIGH finding is retained as the review record, but its interpretation is resolved as invalid. `ApplicationLinkDefinition` defines an application link as a surface that requires registry authority; it records consumer demand and lifecycle ownership, not a positive filing-capability claim. Positive capability has one canonical owner: `revision_capability_probe`, which reads actual export layouts, completeness evidence, and extraction profiles. A FILING-grade snapshot independently enforces the requested authority rung.

For `2015`, `2016-2018`, `2019-2021`, and `2022`, the required `cadrumo.application.filing` link keeps the two declaration-header casillas within the generic lifecycle-closure contract. The capability probe reports no fixed-width or XML layout and no extractor, while the FILING snapshot refuses every epoch because its declared grade is applicability. This is the same consumer-versus-capability separation confirmed against Modelo 576's 2007 applicability-only revision. No layout, `record_design_epoch`, extraction profile, or capability-specific consumer was added.

Focused tests now assert both sides at once: the historical filing consumer remains present, and the shared probe plus FILING snapshot refuse filing capability; 2023-2024 and 2025-y-siguientes retain their parsed layouts and filing capability. The proposed removal would instead create invalid zero-casilla revision placeholders, which the generic schema correctly refuses. The recommendation is therefore closed without a production-schema change.

## Independent final adjudication

### modelo-184-historical-epoch | low | PASS -- the retained filing links are lifecycle consumers, not filing capability

Independent re-review confirms the original HIGH observation remains historically accurate but its capability interpretation is not. `ApplicationLinkDefinition` names an application surface requiring an authority snapshot, while the canonical `revision_capability_probe` derives actual capability only from declared layouts, completeness evidence, and extraction profiles. The unmodified FILING gate separately rejects a revision with an inadequate authority grade and, after a hypothetical promotion, rejects the same layoutless revision for having no export layout.

The four historical headers are deliberately minimal, source- and legal-grounded declaration metadata: two existing semantic header concepts, no coordinate, export reference, binding, extractor, continuity, or generated-layout assertion. Their retained filing consumer is required by the generic casilla lifecycle closure and does not duplicate a selector, validator, or capability implementation. Modelo 576's corrected 2007 applicability revision confirms the same separation: a filing consumer and grounded header can coexist with false capability and the generic no-layout refusal.

The focused M184 coverage is mutation-sensitive at each relevant boundary: changing the historical grade, consumer, export layout, or extractor state breaks the asserted consumer/capability/refusal tuple; changing the positive 2023-2024 or 2025-y-siguientes layout capability also breaks its dedicated assertion. The positive parsed epochs still resolve through FILING snapshots, while all four historical epochs remain false for fixed-width export, XML export, and extraction. No generic exception, alternate capability probe, or redeclared validator was introduced by the remediation. The current-head M184 focused gate passed. The Modelo 576 comparator suite had passed before the final rerun, but that final rerun is now blocked before Modelo 576 loads by an unrelated active Modelo 165 malformed revision fragment; it is mixed-worktree isolation evidence, not an M184 or Modelo 576 regression. No unresolved M184 medium-or-higher finding remains.
