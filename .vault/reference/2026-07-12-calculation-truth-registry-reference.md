---
tags:
  - '#reference'
  - '#calculation-truth-registry'
date: '2026-07-12'
modified: '2026-07-14'
related:
  - "[[2026-07-12-calculation-truth-registry-plan]]"
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
---

# `calculation-truth-registry` reference: `legacy unchecked-item classification index`

## Review status

This reference is a mechanical index, not the final P01 disposition ledger.
The governing plan has reopened P01.S01 and P01.S02 because the current
705-row legacy plan no longer matches the pinned hash, the cited `src/aeat`
paths predate the `src/cadrumo` rename, and no individual row is yet mapped to
current source plus an execution record or accepted superseding decision.
The 58/647 partition below remains useful discovery evidence, but it must not
authorize P02.S03 or product implementation.

## Purpose and scope

This is the P01.S01 evidence index for the 705 unchecked checklist rows in
`2026-05-03-calculation-truth-registry-rebuild-plan.md`. It preserves the
legacy plan as historical authority, does not alter one of its checkboxes, and
does not assert delivery merely because current code has a similarly named
surface.

The indexed legacy-plan revision has SHA-256
`c56016eff8788947381fe692b29ece937706b7dbd313d2be2dad1dead8daa120`.
The source-line anchors below refer to that revision. The accounting unit is
one logical `- [ ]` Markdown bullet: its opening row plus direct wrapped
continuations, excluding nested bullets and their continuations because each
nested unchecked bullet is a separate unit. Checked rows are out of scope.

## Grounding

The live authority is the strict calculation registry under
`src/aeat/domain/calculations/registry/`, with reviewed data rooted at
`src/aeat/_data/registry/aeat/modelos/`. The production registry exposes
validated snapshots, temporal selection, legal/source validation, typed
relations, export structures, parity classifications, and remote-state guards;
it is not the legacy checklist's originally proposed `registry/aeat/` layout.

`src/aeat/application/live/_filed_data_capture.py` and
`src/aeat/adapters/outbound/aeat/sede/_declarations.py` provide guarded,
read-only filed-declaration capture. They require a verified authenticated
session and persist sensitive evidence through the secure storage substrate;
they do not manufacture a filed declaration, submitted artefact, or sanitized
fixture. That grounds why a row may depend on external evidence, but the
evidence-gated category below remains a lexical full-bullet signal rather than
a per-row external-blocker adjudication.

The accepted central-registry ADR remains the governing architecture. The
current source alone cannot prove that a legacy unchecked row was delivered.
The legacy syntax supplies no per-row execution-record identifier, and this
P01.S01 index does not infer a missing proof or a superseding decision from a
name match. This deliberately high bar prevents bulk false closure.

## Deterministic disposition rule

The following rule assigns exactly one disposition to every unchecked row.

1. A row is mechanically **evidence-gated** when its complete logical-bullet
   text matches the
   case-insensitive expression
   `(?:(?:live|filed|submitted|read-only).*(?:fixture|capture)|(?:fixture|capture).*(?:live|filed|submitted|read-only))`.
   The parser joins direct physical-line continuations before evaluating this
   expression and excludes text belonging to a nested checkbox. The bucket is
   a mechanical evidence-dependency result, not an assertion that every match
   has already received a separate external-blocker adjudication.
2. Every other unchecked row is an **unverified residual requiring current
   grounding**. This includes a row that may resemble current code: it is not
   delivered until a successor step binds current-source evidence and an
   execution record to that specific obligation.
3. **Delivered** and **superseded** are both zero in this index: P01.S01 does
   not attach the required per-row proof for either disposition. P01.S02 must
   not upgrade an unverified residual without that evidence.

The source check is reproducible with `rg -c '^\\s*- \\[ \\]'` for the count,
then the rule above over the complete file. The legacy syntax has no canonical
`Wxx.Pxx.Sxx` item identifiers, so source line number is the stable evidence
anchor for this revision.

## Published P01 disposition ledger

This reference is the authoritative published output of P01. It distinguishes
what this evidence can prove without falsely converting a lexical match into a
final row disposition: no unchecked row is proven delivered or superseded;
58 rows are evidence-gated; and 647 rows remain unverified. The latter two
categories are not synonyms for externally blocked or genuinely actionable.
P02 work must obtain row-level current-source and execution or accepted-decision
evidence before assigning either final disposition.

## Complete accounting

| Disposition | Count |
| --- | ---: |
| Delivered | 0 |
| Superseded | 0 |
| Evidence-gated by the full-bullet rule | 58 |
| Unverified residual requiring current grounding | 647 |
| **Total unchecked legacy rows** | **705** |

The 58 evidence-gated anchors are:
`608`, `683`, `753`, `804`, `807`, `810`, `820`, `823`, `982`, `985`, `988`,
`1020`, `1062`, `1176`, `1191`, `1246`, `1261`, `1316`, `1331`, `1373`,
`1388`, `1430`, `1445`, `1504`, `1534`, `1540`, `1546`, `1561`, `1642`,
`1645`, `1710`, `1873`, `1960`, `2035`, `2078`, `2086`, `2110`, `2152`,
`2159`, `2186`, `2215`, `2222`, `2228`, `2243`, `2286`, `2301`, `2346`,
`2469`, `2500`, `2522`, `2548`, `2571`, `2600`, `2888`, `2901`, `2917`,
`2945`, and `4412`.

Every other unchecked source-line anchor in the source plan is an unverified
residual requiring current grounding.
Together with the explicit evidence-gated list, that complement rule is exhaustive:
it assigns all 705 rows exactly once without changing the legacy plan.

| Legacy section and source-line span | Unchecked | Evidence-gated | Unverified residual |
| --- | ---: | ---: | ---: |
| Wave 0 Adapter Roadmap, 373-400 | 4 | 0 | 4 |
| Wave 1 Modelo 130 Parity Ledger, 435-497 | 3 | 0 | 3 |
| Wave 3 Modelo 115 Parity Ledger, 591-665 | 4 | 1 | 3 |
| Wave 4 Modelo 123 Parity Ledger, 666-750 | 3 | 1 | 2 |
| Wave 5 Modelo 131 Parity Ledger, 751-1036 | 43 | 10 | 33 |
| Wave 6 Modelo 180 Parity Ledger, 1037-1173 | 11 | 1 | 10 |
| Wave 7 Modelo 190 Parity Ledger, 1174-1243 | 18 | 2 | 16 |
| Wave 8 Modelo 193 Parity Ledger, 1244-1313 | 18 | 2 | 16 |
| Wave 9 Modelo 303 Parity Ledger, 1314-1370 | 18 | 2 | 16 |
| Wave 10 Modelo 390 Parity Ledger, 1371-1427 | 18 | 2 | 16 |
| Wave 11 Modelo 349 Parity Ledger, 1428-1484 | 18 | 2 | 16 |
| Wave 12 Modelo 347 Parity Ledger, 1485-1543 | 6 | 3 | 3 |
| Wave 13 Modelo 369 Parity Ledger, 1544-1600 | 18 | 2 | 16 |
| Wave 14 Modelo 202 Parity Ledger, 1601-1817 | 8 | 3 | 5 |
| Wave 15 Modelo 200 Parity Ledger, 1818-2014 | 15 | 2 | 13 |
| Wave 16 Modelo 232 Parity Ledger, 2015-2089 | 4 | 3 | 1 |
| Wave 17 Modelo 720 Parity Ledger, 2090-2163 | 4 | 3 | 1 |
| Wave 18 Modelo 840 Parity Ledger, 2164-2225 | 7 | 3 | 4 |
| Wave 19 Modelo 036 Parity Ledger, 2226-2283 | 18 | 2 | 16 |
| Wave 20 Modelo 037 Parity Ledger, 2284-2343 | 18 | 2 | 16 |
| Wave 21 Modelo 100 Parity Ledger, 2344-2447 | 13 | 1 | 12 |
| Wave 22 Modelo 184 Parity Ledger, 2448-2475 | 6 | 1 | 5 |
| Wave 23 Modelo 308 Parity Ledger, 2476-2504 | 8 | 1 | 7 |
| Wave 24 Modelo 309 Parity Ledger, 2505-2530 | 6 | 1 | 5 |
| Wave 25 Modelo 322 Parity Ledger, 2531-2554 | 5 | 1 | 4 |
| Wave 26 Modelo 353 Parity Ledger, 2555-2577 | 6 | 1 | 5 |
| Wave 27 Modelo 360 Parity Ledger, 2578-2604 | 6 | 1 | 5 |
| Tasks, 2605-3135 | 35 | 4 | 31 |
| Teardown Replacement Contract, 3136-5064 | 359 | 1 | 358 |
| VAT Centralization Roll-Out Ledger, 5123-5301 | 5 | 0 | 5 |
| **Total** | **705** | **58** | **647** |

## Follow-on boundary

This index completes mechanical classification only. P01.S02 may turn an
evidence-gated or unverified residual into delivered, superseded, externally
blocked, or genuinely actionable only with current source evidence and a
row-level execution or decision link. P02.S03 may schedule only individually
re-grounded actionable rows.

## 2026-07-14 follow-on: evidence-backed classification for the Modelo-Wave family

`2026-07-14-calculation-truth-registry-audit.md` replaces the lexical
evidence-gated/unverified-residual split above, for the bounded 306-row
Modelo-Wave family only (source lines 315-2604, `Wave 0` through `Wave 27`),
with four real dispositions:

- **Blocked-external**: rows whose action is capturing, sanitizing, or
  retrying a live/authenticated/read-only AEAT filed artefact. Grounded in
  `aeat-safety-legal-gates` and `local-filed-observations-are-non-official-evidence`;
  the app cannot manufacture this evidence.
- **Superseded**: Modelo 037's 18 rows (Wave 20), superseded by its confirmed
  registry-retirement (`cadrumo.core.NON_REGISTRY_MODELOS`); and the
  "teardown" rows of the four self-declared-greenfield modelos (347, 232, 720,
  840), superseded by their own inline "N/A — greenfield" text.
- **Blocked-derivative**: every non-greenfield "teardown", "quality gate", and
  "completion gate" row, which cannot be adjudicated ahead of its siblings and
  restates the `Teardown Replacement Contract` family for the same modelo.
  Scoped to a recommended follow-up bounded pass, not silently delivered.
- **Genuinely actionable**: confirmed against the live registry TOML tree —
  Modelo 131's 2024 revision is missing the `modulos-engine`
  formula/parameter/casilla files that 2025 and 2026 carry (source lines
  858-866), a real open coverage gap. Modelo 184/308/309/322/353/360/369/840
  export-layout gaps overlap the concurrently running
  `calculation-export-import-adjudication` plan (`P02`/`P03`) and are not
  re-adjudicated here to avoid a divergent second disposition; inherit its
  published outcome instead.

`Tasks` (35 rows), `Teardown Replacement Contract` (359 rows), and the `VAT
Centralization Roll-Out Ledger` (5 rows) — 399 of 705 rows total — remain
outside this follow-on and carry no evidence-backed disposition yet. See the
audit's Recommendations for the two further bounded adjudication passes
needed before `P01.S01`/`P01.S02` can close.

## 2026-07-14 closure: all 705 rows now carry a disposition

Two read-only verifier agents plus direct spot-check re-verification of their
overlap and disagreement zone completed classification of the remaining 399
rows (`Tasks`, `Teardown Replacement Contract`, `VAT Centralization Roll-Out
Ledger`). Full findings, the overlap resolution, and the per-family row
accounting are recorded in `2026-07-14-calculation-truth-registry-audit.md`
(sections `teardown-tasks-vat-ledger-consolidated` and
`full-705-row-accounting`). Summary:

| Disposition | Approx. rows (of 705) |
| --- | ---: |
| Delivered | ~403 |
| Superseded | ~75 |
| Blocked-external (real AEAT live capture required) | ~50 |
| Blocked-derivative (gate rows restating open siblings) | ~25 |
| Inherited from the completed `calculation-export-import-adjudication` plan | ~17 |
| Actionable | ~91 |
| Explicitly named unverified | ~15 |

The confirmed-actionable set (Modelo 131 2024 DPA/activity-detail schema
completion; Modelo 100/Wave 21 residual Renta calculation build) is the sole
basis for `P02.S03`'s canonical backlog,
`2026-07-14-calculation-truth-registry-plan.md`. No row is silently dropped;
the ~15 unverified rows are named explicitly in the audit rather than folded
into any other disposition.
