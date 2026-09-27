---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:2f8e457e88426220c021c1be6b7a480852feb9c9ea7b2f168fddf3a79402c4cc'
related:
  - "[[2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research]]"
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-07-11-article-20-uno-26-correction-adr]]"
  - "[[2026-09-09-registry-edition-authoring-adr]]"
---
# `export-parity` adr: `m390 adquisiciones interiores exentas` | (**status:** `proposed`)

## Problem Statement

Modelo 390 box [230] "Adquisiciones interiores exentas" has no binding on any revision. It is a manual casilla that nobody fills. An autonomo's exempt insurance premiums, loan interest and similar acquisitions therefore reach the annual fichero as zeros, and only a non-blocking `unrouted_declarable_quantity` advisory says otherwise. The box is ledger-derived: Modelo 303 has no equivalent box, and DGT V2503-16 says exempt acquisitions go to [230] and never to the 303. The ledger already produces the observations. The binding is missing, and so is a trustworthy way to tell exempt purchases from not-subject ones. Grounding: `2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research`.

A decision is needed now. The export-parity lanes export Modelo 390 for 2022 to 2025 over a seed that holds an exempt premium every year, and two other efforts are about to edit the same 390 revision files.

## Considerations

- The official definition covers art. 20 exempt acquisitions of goods and services, plus 0 % acquisitions in the 2024 and 2025 editions. The 2022 and 2023 editions are not in hand (research, "official definition").
- In the supported designs, a 0 % interior purchase has no deducible-base box, so in 2024 and 2025 [230] is its only annual home (research, same finding).
- Not subject is not exempt. RETA quotas, taxes and owners' community dues stay out (research, "Not subject is not exempt").
- The ledger records an exempt purchase with an unreduced base but with the `zero` rate tier. A 0-rate row without an explicit category is read as a taxable 0 % purchase. The expense catalogue's only IVA hint merges exempt with not subject and is consumed by no code (research, "Cadrumo records an exempt purchase today").
- An empty match resolves to 0, so the value alone cannot separate "none" from "unclassified" (research, "No binding draws the base today").
- The accepted silent-zero boundary lets a bounded mirror of an existing ledger aggregation ship through registry wiring alone, and requires an ADR for a new classification axis (`2026-06-19-silent-zero-base-aggregation-adr`). The binding is the mirror. The classification repair is the ADR-scale part.
- One aggregation mechanism per calculation type (`2026-06-10-calculation-aggregation-taxonomy-adr`). The exemption-article discriminator is governed by `2026-07-11-article-20-uno-26-correction-adr`. Authoring is edition-relative, with deltas against a storage baseline (`2026-09-09-registry-edition-authoring-adr`).

## Considered options

- **Population years.**
  - A, exempt only in every year: rejected. It drops 0 % purchases that have no other 2024 or 2025 box.
  - C, exempt plus 0 % in every year: rejected. It asserts wording for 2022 and 2023 that no captured source shows.
  - B, exempt in every year plus 0 % where the captured edition says so: kept.
- **Data source.**
  - A `previous_filing` fold of the 303: impossible, because the 303 has no box.
  - Keeping [230] manual: rejected. It is the silent zero this record exists to remove.
  - `ledger_iva_aggregation`: kept, as the one mechanism the 390's other ledger boxes use.
- **Rate tier.**
  - Change the ledger so that `domestic_exempt` resolves to the `exempt` tier before binding: deferred as a separate correctness fix.
  - Admit `zero` and `exempt` in the selector, as Modelo 303 casillas 59 and 60 do: kept.
- **Exemption-article filter on the binding.** Rejected. [230] takes every art. 20 exemption, and the vocabulary is mislabelled and unset by any surface.
- **Classification of inputs.**
  - Operator declaration only, plus an advisory: rejected on its own. It leaves the misreading of a bare 0 rate in place.
  - Model inference: rejected. It is a filing-bound default without legal authority.
  - Typed category hints with registry-declared defaults and refusals: kept.
- **Amount under partial business use.**
  - Business share only: rejected. It needs a second base quantity.
  - The unreduced base the observation already carries: kept, open to the operator.
- **303 residual advisory.** Reclassifying it in Python as "declared on the annual return" was rejected, because it couples the modelos outside the registry. The advisory stays accurate and unchanged.

## Constraints

- Filing-grade grounding (`aeat-calculation-grounding`):
  - The exempt half rests on LIVA art. 20, on the record designs' label in every supported year, and on DGT V2503-16.
  - The 0 % half is grounded only where an edition that says "o a tipo cero" is captured in the corpus. Before promotion, the 2024 and 2025 instruction PDFs must enter the corpus (see Implementation).
  - DGT consultas have no source kind in the legal catalogue.
- Missing, unclassified and zero stay distinct (`no-silent-under-declaration`, `aeat-registry-bindings`). The binding adds no zero coercion beyond the family's existing empty-match semantics.
- Registry authority flow (`aeat-registry-authority-flow`):
  - Delta authoring only, against the 2022 storage baseline.
  - The construct's positional `sequence_order` vectors in 2023, 2024 and 2025 must be recomputed through the canonical converter, never hand-edited.
  - One writer for the 390 revision, bindings, casillas and constructs files, sequenced with the `S13` conformance rectification in `2026-09-26-export-parity-plan` and with the sibling investment-goods binding work.
- Ledger contract (`aeat-ledger-contract`): amounts stay non-negative magnitudes, and a refund must be a typed rectification, never a negative base.

## Implementation

Proposed, and not to be executed before operator acceptance. It is layered, so the binding can land before the classification repair, provided the candidate advisory lands with it.

**L1, grounding.**
- Capture the two official instruction PDFs through the corpus route used for `aeat-modelo-190-instructions-2025`:
  - the 2025 edition, `Instrucciones_modelo_390-2025.pdf`;
  - the 2024 edition, `instr390.pdf`.
- Place them under `corpus/aeat_official/instructions/modelo_390/files/`, enroll them in `src/cadrumo/_data/registry/aeat/legal/iva.toml` as `aeat-modelo-390-instructions-2025` and `-2024` with receipts and applicability, and generate their text sidecars.
- Capture the 2022 and 2023 editions if the operator can supply them.

**L2, binding.**
- Add one binding, `modelo-390-especificas-adquisiciones-interiores-exentas-base`, to the 2022 bindings fragment. Its provider:
  - kind `ledger_iva_aggregation`;
  - categories `domestic_exempt`;
  - rate kinds `zero` and `exempt`;
  - flow `soportado`;
  - fact `base_amount_sum`;
  - observation role `settlement`;
  - the same three cash-accounting treatments as its siblings;
  - no `applied_rates`, and no `exemption_articles` filter.
- Its value is money, aggregated by `sum`. Its legal refs are `ley-37-1992:art-20`, `rd-1624-1992:art-71` and `orden-eha-3111-2009:art-1`.
- The native 2022 casilla row gains `input_kind = "bound"` and the binding. The construct `modelo-390-iva-resumen-anual` gains the casilla and the binding. The derived completeness manifest is regenerated.
- 2023 inherits unchanged.
- The first edition with captured "o a tipo cero" wording, 2024 today, carries a `family_overrides` patch on that binding. The patch adds `domestic_zero` to its categories and cites that edition's instructions. 2025 inherits it and adds only its own source identity.
- If a captured 2022 or 2023 edition shows the same wording, the patch moves down to that edition instead.
- The change goes through `dev.registry.edition_delta_migration` and `registry_collapse_verification`. The page-7 export targets are regenerated and checked. Authority is published only when the operator asks.

**L3, visibility.**
- The ledger IVA resolver emits a durable, non-blocking source issue: an exempt-acquisition candidate that is unclassified, whenever a received business row in an exempt-hinted expense category did not reach [230]. Three cases trigger it:
  - the row settled under another category;
  - the row was refused by a missing-fact gate;
  - in an edition without the 0 % wording, the row is a `domestic_zero` purchase.
- The issue names the modelo, revision, casilla 230, binding, ledger id, category and reason. It rides the existing `CalculationSourceIssue` channel to verification, export and the calculation report.
- The 390 `unrouted_declarable_quantity` advisory stops for exempt bases and keeps reporting not-subject bases. The 303 advisory is unchanged.

**L4, classification.**
- Split the `exempt_or_non_subject` hint in fact 0064 into typed hints: `exempt`, `exempt_conditional` and `not_subject`. Each `exempt` category carries a registry-declared default art. 20 sub-article. Correct the dietas hints and assign the categories as the research reads them.
- In the shared ledger application service, used by the CLI and the TUI:
  - A received business row with a 0 rate and no explicit IVA category in an `exempt` category settles as `domestic_exempt` with the default article, carrying visible "expense-category default" provenance.
  - In an `exempt_conditional` or `not_subject` category, the same row is refused with a message naming the category to declare.
  - An explicit category that contradicts the hint raises an advisory, not a refusal.
- Add `--exemption-article` to the ledger commands that accept `--iva-category`. It is validated against fact 0098 and refused unless the category is `domestic_exempt`.
- Extend and correct the fact 0098 vocabulary: fix the labels of 8º and 14º, and add 1º, 3º, 9º, 10º, 12º, 16º, 18º, 22º and 23º. This stays a provenance axis; no box routes on it.
- New messages go through `dev.locales` for every supported locale.

**L5, rectification (follow-on).** A typed rectification identity for cuota-less received rows, with a linked ledger id and a signed evidence amount under the contract's direction field, so a refund nets inside the same aggregation. Until it exists, the candidate issue covers any refund the operator cannot record.

**Export and surfaces.**
- The fichero writes the bound value at page 7, offset 13. The field is signed type N, so a net negative takes the design's "N" prefix. The layout itself does not change.
- The offline XLSX, the CSV casilla table and the calculation-summary PDF show [230] with its binding provenance, the matched ledger ids and any candidate issues through the existing report builder.
- The CLI and TUI calculate, explain and export surfaces need no new command. The new surfaces are ledger-side only (L4).

**Tests.** All run over the real compiled registry and resolver, with synthetic data only.
- Hand arithmetic for 2025:
  - A 480.00 premium (`domestic_exempt`, 16º), 120.00 of loan interest (`domestic_exempt`, 18º), twelve RETA quotas of 300.00 (`operacion_no_sujeta`), 250.00 of IBI (`domestic_not_subject`), a 200.00 + 42.00 taxable purchase (`domestic_general`), and a 1,000.00 exempt sale on the issued side.
  - Result: [230] = 600.00, the soportado base stays 200.00, and the exempt sale reaches neither [230] nor any soportado box.
- A 2024 case adds a 50.00 purchase at 0 %, dated in the first half of the year: [230] = 650.00. The same row in 2023 stays out of [230] and raises the candidate issue.
- Exclusion cases, each alone yielding [230] = 0.00 with provenance:
  - not subject, RETA, a deductible taxed purchase;
  - an intra-Community acquisition at 0 %, a REAGP compensation;
  - an issued exempt sale, a PERSONAL row.
- Missing-data cases:
  - an exempt-hinted row lacking its taxable base yields the gate issue plus the candidate issue;
  - a 0-rate row without a category in a conditional category is refused at the CLI.
- A genuine-zero year with every purchase classified and none exempt yields 0.00 and no candidate issue.
- 303-to-390 parity: the exempt bases of the four 303 quarterly observation sets sum to the 390 [230] total from the same ledger, and every 303 quarter declares none of it.
- The existing test that asserts no box draws the premium on either form is rewritten to the new truth. The fichero page-7 parse round-trips 600.00. Locale completeness covers the new keys.

## Rationale

The binding reuses the one aggregation family and the observations the ledger already builds, so the 303 and 390 read identical rows with no second summation path. That is the bounded-mirror case in `2026-06-19-silent-zero-base-aggregation-adr`. Option B is the only population rule that neither asserts unseen evidence nor drops 0 % purchases that have no other home. It keeps the unproven years advisory rather than guessed. Admitting both rate tiers follows an existing selector precedent and needs no ledger migration.

The classification layer is justified because the value is only as good as the category the operator records. Today a bare 0 rate becomes a taxable purchase, and the expense hint that could catch it merges exempt with not subject (research, "Cadrumo records an exempt purchase today").

## Consequences

- The annual fichero declares exempt acquisitions for every supported year. The quarterly 303 keeps its accurate advisory.
- Taxpayers with 0 % purchases in 2022 and 2023 see a candidate issue instead of a value until those editions are captured.
- The construct and edition edits collide with two concurrent 390 efforts, so the work waits for a single writer.
- L4 changes operator-facing ledger behaviour: some previously accepted 0-rate rows are now refused. Rows already stored are surfaced by L3 rather than rewritten.
- The same mechanism opens [109], [113], [523] and [654] to [657], and the supply-side [105], as follow-ons. [231] and [232] need new ledger quantities first.
- Open for the operator:
  - Can you supply the 2022 and 2023 instruction editions? Otherwise option B's advisory stands for those years.
  - Full base or business share when a row has partial business use?
  - Do embedded taxes such as the insurance premium tax belong in the amount?
  - Defaults with provenance for `exempt` categories, or refusal everywhere?
  - Should the candidate issue block filing-grade verification?
  - Is the L5 refund model acceptable?
  - Should a new source kind admit DGT consultas to the corpus?
  - Does a dwelling let partly used as an office keep the 23º.b exemption?
  - Should the fact 0098 correction stand under this record, or amend `2026-07-11-article-20-uno-26-correction-adr`?
