---
tags:
  - '#research'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:408cae695b236f2425857cd5ef9dfd47d887523b57da8802aa00390085b9b511'
related:
  - "[[2026-09-30-modelo-editor-workbench-reference]]"
---

# `modelo-editor-workbench` research: `Casilla row and state language`

What does one casilla look like in the editor, what closed state and progress vocabulary does it speak, and which Textual architecture renders it at modelo 200 scale? The evidence favours a two-axis state vocabulary (origin plus overlay) rendered as glyph and words, locale-formatted values, a docked help band, and one virtual list per page anchored by casilla id rather than a widget per row. Measured on 2026-09-30 against the live tree and the published authority; probe scripts ran in session scratch and were not retained, so every figure names the code or data it was measured from.

## Findings

Scope: the rich casilla row (`[num] [label] [value] [state] [edit] [help]` plus a
description line), the closed state vocabulary, progress language from field to
form, the Textual widget architecture that carries it at modelo-200 scale, the row
keyboard model, and theme/glyph fitness. Measured on 2026-09-30 in worktree
`Y:\code\cadrumo-worktrees\tui` (Textual 8.2.8, Rich 15.0.0, Python 3.13, Windows).

Discovery note: `vaultspec-rag` code search refused (`index_unverifiable`), so code was
located by targeted grep and full reads. Registry figures come from the worktree's
published authority (`.authority/`, read through `bundled_indexed_authority()` with
`CADRUMO_AUTHORITY_ROOT` pointed at it) and from the committed locale catalogues.
Nothing under `Y:\` was written; all scripts, prototypes and screenshots live in
`(session scratch, not retained)`
(abbreviated `agent-b\` below).

---

#### 1. Findings

##### 1.1 What the operator gets today

- The only edit control is a bare `Input` per writable casilla or manual-input binding,
  placeholder = casilla id, no label, value, type, help or state

- Apply reads every input as a raw string and submits only non-empty ones
  (`overview.py:360-369`). A blank box therefore means "no intent": the operator cannot
  clear a value, and cannot tell "I left it" from "I emptied it". Combined with the
  executor rebuilding inputs only from the submitted intents (reference
  `2026-09-30-modelo-editor-workbench-reference`), what the operator sees and what is
  persisted diverge after the second edit.
- The inputs page prints values with `str(scalar.value)` (`inputs.py:106-109`), so a money
  value shows as `1234.50` in every locale, including Spanish where the reader expects
  `1.234,50 €`. Rows are grouped by record family, not by modelo section
  (`inputs.py:187-216`).
- There is no state column at all; the only per-row provenance on screen is the declared
  `input_kind` in words (`inputs.py:66-86`, `models.py:286-288`).

##### 1.2 What the application already knows per row (and what it does not)

`ModeloWorkReviewCasilla` (`src/cadrumo/application/modelo/work_review.py:109-145`)
carries everything the row needs **except** three facts:

| Needed by the row | Where it is today | Carried by the review? |
|---|---|---|
| declared input kind | `declared_input_kind` (`work_review.py:125`) | yes |
| realised provenance | `realised_kind` (`work_review.py:129`), classifier `_work_review_assembly.py:259-300` | yes, but lossy (below) |
| proven non-applicability | `absent_by_design` (`work_review.py:131-138`) | yes |
| override of an import | `origin_anomaly == OPERATOR_OVERRIDE` (`_work_review_assembly.py:274-275`) | yes |
| which source | `concrete_bindings[].source/resolved` (`work_review.py:70-76`) | yes |
| formula | `concrete_formula.operand_refs` (`work_review.py:79-84`) | yes (ids only) |
| verification blocker | `blocked_by[]` (`work_review.py:145`) | yes (axis + code + facts) |
| **required** | `CasillaDefinition.required` (`schema_surfaces.py:344`) | **no** |
| **entered by the operator** | `CalculationRevision.input_values_by_casilla_id` (`calculation_revision.py:176`) | **no** |
| **editable** | `ModeloEditPermittedSurfaceEntryV1` (`edit_admission.py:134-190`) | no (separate admission) |
| localized label/help | `CasillaDefinition.get_label/get_help(locale)` (`schema_surfaces.py:435-442`) | label only, Spanish only (`work_review.py:122`, `_work_review_assembly.py:375`) |
| staged (changed, not applied) | TUI edit session (ADR D4) | TUI-local by design |

Lossy classification, measured by reading the classifier:

- Any manual casilla with an observation is `LITERAL` (`_work_review_assembly.py:268-270`):
  an operator-entered value and a materialised default are indistinguishable.
- `ModeloValueKind.DEFAULT` (`src/cadrumo/domain/filing/schema.py:54`) is never emitted by
  any non-test source (grep), so "default" has no producer.
- A computed casilla with no observation is flagged `BROKEN_CALCULATION_CHAIN` even when
  there is no revision at all (`_work_review_assembly.py:296-299`, the flag is set at `:298`); only the
  review-level `calculation_revision_id` (`work_review.py:216`) separates "not calculated
  yet" from "broken".
- The report layer is ahead of the TUI: `CalculationReportValueState`
  (`calculation_report.py:114-129`) already keeps VALUE / ABSENT / NOT_APPLICABLE
  separate, and `CalculationReportRowRole` (`calculation_report.py:132-160`) already
  classifies INPUT / COMPUTED / SUBTOTAL / RESULT / INFORMATIONAL / PROJECTION_ONLY from
  registry data only. The row should consume the same two enums rather than re-derive them.

##### 1.3 Locale-aware formatting already exists — in the PDF summary

- `NUMBER_FORMATS` (`src/cadrumo/application/modelo/calculation_summary_presentation.py:135-145`):
  es/ca `.` + `,`; en `,` + `.`; hu no-break space + `,`. `format_summary_value`
  (`:248-265`) groups thousands, keeps every fractional digit, and renders booleans
  through catalogue words.
- Absence words already exist in all four locales:
  `application.modelo.calculation_summary.value_absent` ("no data" / "sin dato" /
  "sense dada" / "nincs adat"), `value_not_applicable` ("n/a · not applicable"),
  `value_true/false` (es `application.yml:894-897`, en `:811-814`, ca `:893-896`,
  hu `:856-859`).
- `core/decimal/formatting.py` is fixed-point only (not locale-aware); input parsing
  lives in `core/decimal/coercion.py` and `core/decimal/grammar.py`.
- The prototype reuses `NUMBER_FORMATS` directly (`agent-b\proto\vocab.py`): the hu
  frame shows `12 345,67 €` with a no-break space and `4,00 %`, es shows `12.345,67 €`.

##### 1.4 The product's existing field-editing and state language

- Profile manager: present/absent glyphs `●`/`○`, required mark `*`
  (`src/cadrumo/entrypoints/tui/profile/overview.py:95-102`); fold titles
  `flows.manager.onboarding.section_done` = `✓ {title} - {present}/{total}` and
  `section_pending` = `✖ {title} - {missing} required` (en `flows.yml:101-102`, es
  `:102-103`, ca `:103-104`, hu `:103-104`); a docked help panel capped by
  `$cadrumo-help-max-height` (`overview.py:503-511`); what/why/where headings
  (`flows.manager.help.*`, en `flows.yml:80-82`); `FieldEditScreen` modal with typed hint,
  refusal line and explicit Clear (`overview.py:173-310`).
- `RequirementStatus` glyphs `✖ ✓ ? ○ —` (`components/widgets.py:326-349`), workspace
  disposition glyphs `✓ — ✖ ?` (`modelo/view/models.py:75-94`), notice glyphs `ⓘ ⚠`
  (`widgets.py:263-266`, `components/status.py:24`).

##### 1.5 Glyph support in the pinned font (measured)

Method: render each candidate with the committed
`docs/_static/readme/fonts/CascadiaMono-Regular.ttf` via PIL and compare against the
font's `.notdef` mask — the same test `dev/tui/_raster.py:143-154` uses; cell width from
`rich.cells.cell_len` (what Textual lays out by). Script `agent-b\glyphs.py`,
`agent-b\glyphs2.py`.

- **Missing** (renders as tofu in the visual review, and falls back to another font in
  Windows Terminal, whose default font is Cascadia Mono): `✖ ✔ ✗ ✘ ⚠ ⓘ ℹ ✎ ✏ ⚑ ⚐ ∅ ⊘ ⊗
  ⊕ ↻ ↺ ⟳ ↳ ⤷ ⇒ ⇐ ⬇ ⇩ ⋯ ⋮ ★ ☆ ☐ ☑ ☒ ✕ ⚙ ⌫ ↵ ⎘ ✚ ✱ ✳ ✦ ⁎ ∗ ※ ①` and the wide `⌛ ⛔`.
- **Present, one cell**: `✓ ○ ● ◉ ◌ ◐ ◑ ◆ ◇ ■ □ ▣ ▪ ▫ • · … ↓ ⇣ ← → ↑ ↕ ≠ ≈ = Σ ∑ ƒ Δ △ ▲ ▼ ▸
  ▾ ▹ ▿ ◂ ▶ ◀ « » ‹ › € ‰ × − – — ± ≤ ≥ ¬ ∞ √ ◎ ◯ ⬤ ⬚ ▢ ◍ ▬ ▮ ▯ ◧ ◨ ⏎ ¡ ¿ ‼ ¦ §`.
- Consequence: three glyphs the product already ships (`✖`, `⚠`, `ⓘ`) are not in the
  pinned font (see Bugs B1). Every glyph in the vocabulary proposed below is in the
  "present" set; rasterising all 12 prototype frames through `dev/tui/_raster.py`'s
  `rasterise` reported `missing_glyphs=()` for every frame.

##### 1.6 Labels and help: what a row has to fit (measured)

Catalogue census over `src/cadrumo/locales/{es,en,ca,hu}/modelo/schema/*.yml`
(`agent-b\catalogue_census.py`, output `agent-b\catalogue_census.json`), widths in cells:

| locale | labels | median | p75 | p90 | p99 | max | > 56 cells | help entries |
|---|---|---|---|---|---|---|---|---|
| es | 16,400 | 84 | 136 | 188 | 267 | 603 | 11,511 | 5,102 |
| en | 16,394 | 79 | 132 | 180 | 267 | 586 | 10,685 | 5,102 |
| ca | 16,339 | 81 | 133 | 180 | 260 | 572 | 10,959 | 5,100 |
| hu | 16,396 | 82 | 134 | 181 | 286 | 544 | 11,176 | 5,102 |

Per live revision (published authority, `agent-b\census.py` → `agent-b\census.json`;
es / hu label median and p90; `req` = `required=True`):

| modelo · revision | casillas | manual / bound / computed / info+proj | req | full-path sections (max rows) | es med/p90 | hu med/p90 | help (es) |
|---|---|---|---|---|---|---|---|
| 303 · 2026-y-siguientes | 220 | 72 / 52 / 33 / 63 | 2 | 72 (45) | 63 / 111 | 70 / 122 | 206 |
| 130 · 2019-y-siguientes | 20 | 5 / 3 / 12 / 0 | 1 | 7 (7) | 28 / 52 | 23 / 51 | 20 |
| 111 · 2019-y-siguientes | 30 | 19 / 9 / 2 / 0 | 0 | 10 | 58 / 73 | 59 / 79 | 0 |
| 390 · 2025 | 414 | 241 / 152 / 19 / 2 | 2 | 15 (156) | 88 / 116 | 86 / 117 | 336 |
| 100 · 2025 | 2,249 | 1,979 / 52 / 216 / 2 | 7 | 169 (128) | 53 / 130 | 54 / 131 | 224 |
| 200 · 2025-y-siguientes | 3,463 | 3,450 / 3 / 10 / 0 | 1 | 708 (111) | 135 / 203 | 133 / 213 | 281 |

- A single-line label column (≈50 cells at 80 columns, ≈60 at 120) truncates the median
  label everywhere except 130; the row must wrap to a second line or disclose the full
  label on focus. Both are in the design.
- Help is thin and partly boilerplate: of 5,102 es help entries only 2,023 are distinct
  after masking digits, and 1,011 are one of three templates such as
  `Casilla N del modelo N, ejercicio N.` (`agent-b\helpq.py`). 111 and 115 have no help;
  100 has help for 224 of 2,249 casillas. The help surface therefore has to be
  synthesised from structure (source, formula, legal basis) and not depend on the
  `help` key.
- Label quality: 24 es labels contain `Npct`, 6 contain ` ops `, 9 contain ` RG `
  (e.g. `IVA devengado RG tipo super-reducido 4pct - Base imponible`); some labels carry
  implementation notes (`… (LIVA art 84.Uno.2 + art 92; parte de la casilla oficial 29)`
  on `iva.autorepercutido.interior.deducible`).
- Sibling-prefix elision (drop the common prefix a section's labels share, up to a
  ` - ` / `, ` boundary; full label kept in the help band): 200 es median 135 → 61 cells,
  p90 203 → 120; 200 en 136 → 66; 390 88 → 87; 303 and 100 essentially unchanged
  (`agent-b\prefix.py`). Worth it for 200 only.
- `number` is not always a box number: 38 of 220 rows in 303 and 50 of 414 in 390 carry a
  semantic id as `number` (`iva.repercutido.general`, 60 cells long); only 1 and 3 of
  those carry `form_number` (`agent-b\census3.py`). They are mostly bound feeder figures
  that are not boxes on the official form. Numeric numbers are 2-3 chars (303/390),
  4 (100), 5 (200).

##### 1.7 Scale and cost

- Review assembly for the whole revision (`build_modelo_work_review_casillas`,
  `revision=None`): 303 172 ms (first call, includes warm-up), 390 96 ms, 100 466 ms,
  200 450 ms. The projection must run off the UI thread and be paged per section.
- The largest single full-path section is 156 rows (390), 128 (100), 111 (200), 45 (303).
  Mounting one full-path section at a time bounds the page to ≤156 rows today.

##### 1.8 Widget cost in Textual (measured, headless)

Scratch benchmark (`agent-b\proto\bench.py`, `bench2.py`, `navbench.py`; logs
`agent-b\bench.log`, `bench2a.log`, `bench2b.log`, `navbench.json`): mount N synthetic rows
into a `VerticalScroll` inside `App.run_test(size=(120, 36))`, dark Cadrumo theme, time
from widget construction to two settled `pilot.pause()`; median of 3 runs unless noted.
Per-row widgets scale super-linearly and a literal "row of buttons" is unusable past a
single small section; a single Line-API widget is flat. Full table in 2.7.

---

#### 2. Proposed design

##### 2.1 Row anatomy

One casilla = one focusable row. Left to right:

| column | width | content |
|---|---|---|
| cursor | 1 | `▸` on the focused row (non-colour focus cue), else blank |
| attention | 1 | `Δ` staged or `▲` blocked, else blank — a change bar, like an editor gutter |
| gap | 1 | |
| number | 2–5 (+1) | official box number, muted; `·` for a semantic-id row with no `form_number`; `form_number` when present |
| label | fill (≥ 8) | localized label, wraps to a second line in comfortable density, ellipsis beyond two lines; capped at 72 cells from 150 columns up so the value stays near its label |
| value | 17, right-aligned | formatted value, or an absence word (2.3) |
| gap | 1 | |
| origin glyph | 1 | always present |
| state words | 26 (≥ 110 cols) | origin in words on line 1; attention in words, else the source, on line 2 |
| detail | 30 (≥ 150 cols) | formula (`= [07] × [08] / 100`) or source name |

Line 2 (comfortable density only, and only when needed): label overflow, or the
description (formula / source / first help sentence) on the left; at < 110 columns the
state in words sits right-aligned under the value. A row with a one-line label, no
attention and a state column is one line tall even in comfortable density.

Row edit/help "buttons" are not per-row widgets: they are keys on the focused row,
advertised in the footer and in the help band (the composite button row measured 3.75 s to mount 300 rows —
2.7). Mouse: click focuses, double-click or click on the value edits.

**80 × 24, compact** (default below 30 rows or 100 columns; `agent-b\shots\row-page-en-light-80x24-compact.svg`):

```
 Modelo 303 · 1T 2026 · VAT
 Required 2/3 · ! 1  ● 6  ↓ 1  = 7  Δ 1  ▲ 1
▾ ! Accrued VAT · general regime · 1 required missing   Δ 1 not applied
    01  Accrued VAT, general regime super-reduced 4% rate -…     1,250.00 € ●
    02  Accrued VAT, general regime super-reduced 4% rate -…         4.00 % =
    04  Accrued VAT, general regime reduced 10% rate - Taxa…       no data !
    06  Accrued VAT, general regime reduced 10% rate - Tax …             … ◌
▸▲  07  Accrued VAT, general regime standard 21% rate - Tax…    12,345.67 € ↓
    10  Accrued VAT on intra-Community acquisitions of good…         0.00 € ●
    11  Accrued VAT on intra-Community acquisitions of good…         0.00 € =
 Δ  12  Accrued VAT on other reverse-charge transactions ex…     1,200.00 € ●
    14  Adjustment of taxable bases and amounts, accrued VA…       no data ○
    16  Equivalence surcharge at 1.0% - Taxable base                   n/a —
────────────────────────────────────────────────────────────────────────────
 07 · Accrued VAT, general regime standard 21% rate - Taxable base
 ↓ Imported · VAT ledger totals   ▲ Blocked: ledger total differs from the
 imported base
 Legal basis: Ley 37/1992, art. 90
 ⏎ Edit  ? Help  x Clear  n Next to review  / Search  d Density
```

**80 × 24, comfortable** (`row-page-en-light-80x24.svg`, `row-page-es-light-80x24.svg`, `row-page-hu-light-80x24.svg`):

```
    01  Accrued VAT, general regime super-reduced 4% rate -       1,250.00 € ●
        Taxable base                                           Entered by you
▸   04  Keletkezett ÁFA, általános rendszer csökkentett          nincs adat !
        10%-os kulcs - adóalap                             Kötelező · hiányzik
```

**120 × 36** (`row-page-en-light-120x36.svg`, `row-page-es-dark-120x36.svg`):

```
▾ ! IVA devengado · régimen general · faltan obligatorias: 1   Δ 1 sin aplicar
    01  IVA devengado RG tipo super-reducido 4pct - Base imponible      1.250,00 € ● Introducida por ti
    04  IVA devengado RG tipo reducido 10pct - Base imponible             sin dato ! Obligatoria · falta
    06  IVA devengado RG tipo reducido 10pct - Cuota                             … ◌ Sin calcular aún
 ▲  07  IVA devengado RG tipo general 21pct - Base imponible           12.345,67 € ↓ Importada
                                                                                   ▲ Bloqueada
▸Δ  12  IVA devengado otras ops inversión sujeto pasivo excl intracom   1.200,00 € ● Introducida por ti
        - Base                                                                     Δ Cambiada · sin aplicar
    16  Recargo equivalencia tipo 1.0pct - Base imponible                      n/a — No aplicable
    36  IVA deducible adquisiciones intracomunitarias corrientes - Base   sin dato ⇣ Sin importar aún
                                                                                   Totales del libro de IVA
```

**160 × 48** (`row-page-en-light-160x48.svg`, `row-page-hu-dark-160x48.svg`):

```
    02  Accrued VAT, general regime super-reduced 4% rate - Rate percentage      4.00 % = Calculated          = parameter: super-reduced rate
    03  Accrued VAT, general regime super-reduced 4% rate - Tax amount          50.00 € = Calculated          = [01] × [02] / 100
▸▲  07  Accrued VAT, general regime standard 21% rate - Taxable base        12,345.67 € ↓ Imported            VAT ledger totals
                                                                                        ▲ Blocked
    28  Deductible VAT on domestic current transactions - Tax base           8,000.00 € ≠ Your value          replaces: VAT ledger totals
  IBAN  Bank account (IBAN) for direct debit                               ES91 ···· 1332 ● Entered by you
```

Section header row (a `DisclosureGroup` title, so folding and the section gap come
free): `▾ ✓ Deducible · 4/4` / `▾ ! Devengado · faltan obligatorias: 2   Δ 1 sin aplicar   ▲ 1 bloqueada`.
At 80 columns the header truncates the title before the counts, never the counts.

Emphasis from `CalculationReportRowRole`: RESULT rows bold with a rule above; SUBTOTAL
bold; INFORMATIONAL / PROJECTION_ONLY muted label. Semantic-id feeder rows (number `·`)
sit in a collapsed "Working figures (not on the form)" fold at the end of their section.

##### 2.2 Value formatting (per data type, per locale)

All numbers through one shared formatter built on `NUMBER_FORMATS` (move it out of the
PDF module into a presentation-level home — lens A/C decide where). Minus is `−`
(U+2212, present in the font), right-aligned; money always two decimals; the unit is
inside the cell so a copied value is self-describing.

| data type | es / ca | en | hu | notes |
|---|---|---|---|---|
| money | `12.345,67 €` | `12,345.67 €` | `12 345,67 €` (NBSP) | widest `−99.999.999,99 €` = 16 cells → value column 17 |
| ratio | `21,00 %` | `21.00 %` | `21,00 %` | registry stores percent points (see B5); scale must be declared, not guessed |
| decimal | `1.234,5678` | `1,234.5678` | `1 234,5678` | keep every stored fractional digit |
| integer | `1.234` | `1,234` | `1 234` | |
| boolean | `Sí` / `No` | `Yes` / `No` | `Igen` / `Nem` | catalogue `value_true/false` |
| date | `31/03/2026` | `31/03/2026` | `2026. 03. 31.` | |
| year / period_code | `2026` / `1T` | same | same | tokens are data, never translated |
| nif / nif_iva | `00000001R` | same | same | full; sensitive-display rule (D8) may mask third-party NIFs |
| iban | `ES91 ···· 1332` | same | same | masked in the row, full only inside the editor |
| enum / codes (country, ccaa, province…) | code + name when the catalogue has one: `ES · España` | | | left-aligned, truncated |
| text / name | left-aligned in the value column, `…` truncation, full text in help band | | | |

##### 2.3 The five absences look different

| situation | value cell | origin glyph + words | derivation |
|---|---|---|---|
| nothing entered, required | `sin dato` (muted) | `! Obligatoria · falta` | manual/bound, `realised_kind == EMPTY`, `required` |
| nothing entered, optional | `sin dato` (muted) | `○ Opcional · vacía` | as above, not required |
| proven zero (engine/import) | `0,00 €` (normal) | `= Calculada` or `↓ Importada` | `realised_kind` COMPUTED / INHERITED with value 0 |
| zero you entered | `0,00 €` (normal) | `● Introducida por ti` | manual, casilla id in `input_values_by_casilla_id` |
| not applicable by design | `n/a` (muted) | `— No aplicable` | `absent_by_design` |
| not calculated yet | `…` (muted) | `◌ Sin calcular aún` | computed, EMPTY, review `calculation_revision_id is None` |
| could not calculate | `…` (muted) | `× No se pudo calcular` | computed, EMPTY, revision present (`BROKEN_CALCULATION_CHAIN`) |

The words for "no data" and "n/a" reuse `application.modelo.calculation_summary.value_absent`
and `value_not_applicable` so the TUI and the PDF summary never disagree.

##### 2.4 Closed state vocabulary

Two axes. Every row has exactly one **origin** and at most one **attention** overlay.
Glyph + words always travel together; colour is reinforcement only. All glyphs are in the
pinned font and one cell wide. Colour role → theme variable: `error` → `$error`,
`warning` → `$warning`, `entered` → `$success`, `staged` → `$accent`, `imported` →
`$foreground`, `muted` → `$secondary` (not `$text-muted`: through component classes it
resolved to near-invisible on the light background in the first prototype pass).

| # | state | derivation (first match wins, top to bottom) | glyph | words en | words es | colour | derivable today? |
|---|---|---|---|---|---|---|---|
| O1 | not applicable | `absent_by_design` | `—` | Not applicable | No aplicable | muted | yes |
| O2 | your value replaces the import | `origin_anomaly == OPERATOR_OVERRIDE` | `≠` | Your value · replaces import | Tu valor · sustituye la importación | warning | yes (review); not producible from the TUI (B7) |
| O3 | calculated | `realised_kind == COMPUTED` | `=` | Calculated | Calculada | muted | yes |
| O4 | not calculated yet | `declared_input_kind == COMPUTED`, EMPTY, review has no revision | `◌` | Not calculated yet | Sin calcular aún | muted | yes, with review context |
| O5 | could not calculate | as O4 but a revision exists | `×` | Could not calculate | No se pudo calcular | error | yes, with review context |
| O6 | for information | `declared_input_kind ∈ {INFORMATIONAL, PROJECTION_ONLY}` | `◇` | For information | Informativa | muted | yes |
| O7 | required · missing | EMPTY and `required` | `!` | Required · missing | Obligatoria · falta | error | **needs `required` on the review** |
| O8 | imported (+ source) | `BOUND`, not EMPTY; source = first resolved binding | `↓` | Imported · VAT ledger totals | Importada · Totales del libro de IVA | imported | yes (source words exist: `flows.modelo_review.filter.option.binding_source.*`) |
| O9 | not imported yet (+ expected source) | `BOUND`, EMPTY | `⇣` | Not imported yet | Sin importar aún | muted | yes |
| O10 | optional · empty | `MANUAL`, EMPTY, not required | `○` | Optional · empty | Opcional · vacía | muted | yes (required = false by default) |
| O11 | default · check it | `MANUAL`, LITERAL, **not** in `input_values_by_casilla_id` | `◐` | Default · check it | Por defecto · revísala | warning | **needs entered-flag on the review** |
| O12 | entered by you | `MANUAL`, LITERAL, in `input_values_by_casilla_id` | `●` | Entered by you | Introducida por ti | entered | today only as "LITERAL" (O11 and O12 collapse) |
| A1 | changed · not applied | edit session dirty address (D4) | `Δ` (gutter) | Changed · not applied (was 1,000.00 €) | Cambiada · sin aplicar (era 1.000,00 €) | staged | TUI-local |
| A2 | blocked | `blocked_by` non-empty | `▲` (gutter) | Blocked: {finding message} | Bloqueada: {mensaje} | error | yes (message from `finding_message`, `models.py:301`) |

Rules:

- Attention precedence: `Δ` over `▲` (a staged change may resolve the finding, which
  belongs to the pre-edit revision); the help band shows both.
- Read-only is not a state of its own: O3–O6 and O8–O9 explain *why* the row is not
  editable, and the help band adds the admission reason (`ModeloEditNonWritableReason`:
  `computed_by_formula`, `schema_declared_read_only`, `capability_unavailable`).
- Glyph uniqueness: 12 origin glyphs and 2 attention glyphs are pairwise distinct, so a
  greyscale screenshot and a colour one read the same (the accepted D8 rule). Keep a
  totality guard like `models.py:96-104` over the vocabulary table.
- `✓` stays reserved for "section/form complete"; `●`/`○` keep the profile's
  present/absent meaning; `—` keeps its "not applicable" meaning from `RequirementStatus`.
- Unsupported data type → the ADR's renderer-refusal view: value cell `?` + words
  "Cannot show this value type", never a text box.

##### 2.5 Progress language

One grammar at four levels, all glyph + words, all counts from the vocabulary:

- **Field**: the origin glyph + words (2.4).
- **Section** (fold title): `✓ {title} · {filled}/{total}` when nothing required is
  missing; `! {title} · faltan obligatorias: {missing}` otherwise; then optional
  `Δ {n} sin aplicar`, `▲ {n} bloqueada(s)`. `{filled}/{total}` counts input-bearing rows
  (manual + bound) that hold a value; computed/informational rows are not denominators.
  Put the count after a colon (`faltan obligatorias: 1`) because the catalogue has no
  plural support and `{missing} obligatorias` reads "1 obligatorias" (B4).
- **Page** (a destination such as "IVA devengado"): same as section, aggregated.
- **Form** (strip under the banner): ≥ 110 columns
  `Obligatorias 2/3 · Introducidas 6 · Importadas 1 · Calculadas 7   Δ 1 sin aplicar   ▲ 1 bloqueada`;
  < 110 columns the glyph strip `Obligatorias 2/3 · ! 1  ● 6  ↓ 1  = 7  Δ 1  ▲ 1`, which
  doubles as a legend (the `?` key on the strip opens the full legend). The calculation
  manifest's `ModeloWorkProgress` (`work_review.py:181-203`) is shown separately as
  "Calculated {materialised}/{target}" and never merged with the input counts.
- Profile alignment: same `✓`/`!` leading glyph and `{title} · counts` shape as
  `flows.manager.onboarding.section_done/section_pending`, with `!` replacing `✖`
  (missing from the font) in both surfaces.

##### 2.6 Help band (the `[help]` of the row)

Docked at the bottom, `max-height: $cadrumo-help-max-height` (6), follows focus like the
profile manager's `#manager-field-help`. Content, in priority order so the cap cuts the
least useful line:

1. `{number} · {full label}` (bold) — the disclosure of any truncated label.
2. `{origin glyph} {state words}` + attention words (`Δ … was 1.000,00 €`, `▲ Blocked: {finding}`).
3. **Comes from**: source words (`docs.modelo.*.binding_source` phrasing:
   "desde sus apuntes de IVA") or **Formula**: `= [07] × [08] / 100` rendered from
   `operand_refs` with box numbers.
4. **What it is**: the `help` key when it is not boilerplate; else omitted.
5. **Legal basis**: `legal_refs` rendered as citations.

`?`/F1 expands the band into a scrollable panel (full what/why/where, all operands with
their current values, every blocker with its action). Key hints live in the footer, not in
the band (the first prototype pass lost the key line to the 6-line cap at 80×24).

##### 2.7 Widget architecture and measured performance

Five candidates were built and measured (1.8). All render the same cells through one
shared `row_lines()` formatter, so the comparison is the container, not the content.

| architecture | mount 50 | mount 300 | mount 1,000 | mount 3,400 | DOM nodes @300 | key-step latency @300 / @1,000 | re-render one value @300 / @1,000 |
|---|---|---|---|---|---|---|---|
| composite row (`Horizontal` + label/value/badge `Static` + Edit/? `Button` + description) | 610 ms | 3,751 ms | not run (> 12 s extrapolated) | — | 2,701 | — (two buttons per row in the focus chain) | 309 ms / — |
| `CasillaRow` render-only widget per casilla in `VerticalScroll` | 323 ms | 1,149 ms | 5,141 ms | 19,879 ms (1 run) | 301 | 112 / 197 ms (Tab) | 47 / 100 ms |
| `ContentDataTable` with Rich `Text` cells | 184 ms | 177 ms | 369 ms | 666 ms | 2 | 65 / 65 ms | 47 / 62 ms |
| `OptionList` with multi-line `Text` prompts | 89 ms | 131 ms | 367 ms | — | 2 | 74 / 77 ms | 70 / 208 ms |
| Line-API `ScrollView` (`CasillaVirtualList`, renders visible lines only) | 99 ms | 85 ms | 82 ms | 93 ms | 2 | 83 / 94 ms | 32 / 43 ms |

Latency numbers include Pilot's own settle time per press, so they are comparable to each
other, not to a human perception threshold. The first bench's navigation column
(`bench.log`) used `focus_next()` for rows and key presses for the rest and is superseded
by `navbench.json`.

**Recommendation.** Render the page body as **one Line-API widget per bounded page**
(`CasillaList(ScrollView)`), with the cursor held as a casilla id:

- flat mount (82–99 ms from 50 to 3,400 rows) means the ADR's bounded-mounting rule stops
  constraining the design: a section, a page, or 390's 407-row top-level group all open
  in under 0.1 s, and paging becomes a navigation choice rather than a performance crutch;
- it keeps the free-form two-line row, the gutter change bar, right-aligned values and
  per-segment colour roles that a column grid fights;
- one focusable widget with an internal cursor gives a deterministic keyboard order
  (D8) and makes "focus by casilla id" a dict lookup;
- cost: hit-testing for mouse, `refresh_lines` for a single-row update, and a
  screen-reader-friendly label for the focused line must be written (Textual gives them
  free to real widgets). Section headers become lines inside the same list (fold state in
  a TUI-local set), so the whole page is still one widget.

Fallback if the custom widget is not wanted: `ContentDataTable` (already in the design
system) with 4–5 columns and `add_row(height=None)` — 0.2–0.7 s mounts, best key latency —
accepting a grid look and the width-policy cost noted in Risks. Reject per-row widgets
above ~100 rows (1.1 s at 300, 5.1 s at 1,000, 19.9 s at 3,400) and reject the composite
button row outright (2,701 DOM nodes and 3.75 s for 300 rows). The `CasillaRow` widget in
the prototype remains the right primitive for small fixed surfaces (a modal's context
line, the 130/111/115 forms of 5–30 rows), sharing `row_lines()` with the list.

The application projection itself (1.7: up to 466 ms for 100) runs in a worker; the
list shows the section skeleton immediately and fills values when the worker returns.

##### 2.8 Keyboard model and focus anchoring

| key | action | condition |
|---|---|---|
| `↑` `↓` / `k` `j` | previous / next row | |
| `PgUp` `PgDn` `Home` `End` | page / ends | |
| `[` `]` | previous / next section (fold headers) | |
| `Enter`, double-click | open the editor (lens C) | editable; otherwise the help band states why not |
| `?`, `F1` | expand / collapse full help | |
| `x`, `Delete` | stage `CLEAR_DECLARED_VALUE` (Δ appears) | entered rows only |
| `u` | revert this row's staged change | row has Δ |
| `n` / `N` | next / previous row needing attention (`!`, `▲`, `Δ`, `◐`, `×`) | |
| `s` | go to the source of an imported value (lens D) | O8/O9/O2 |
| `f` | show the formula trace (provenance destination) | O3–O5 |
| `/` | search labels, numbers and values | |
| `r` | toggle "required and attention only" filter (profile's required-only switch) | |
| `d` | toggle density compact / comfortable | |
| `F3` | appearance (existing) | |

Focus is anchored by casilla id, never by index: widget id = the one-to-one encoding
already in `edit_control_id` (`overview.py:136-151`), e.g. `casilla-iva_2e_…`. On any
rebuild (refresh, locale switch, filter, section change) the screen records the focused
casilla id and re-focuses it; if the casilla is filtered out it focuses the nearest
following row in registry order, then the section header. After the editor modal closes,
focus returns to the same id (D8 "focus return by semantic identity"). In a virtual list
the cursor is stored as a casilla id and mapped to an index through a dict on every
rebuild.

##### 2.9 Prototype and screenshots

Prototype: `agent-b\proto\vocab.py` (vocabulary, derivation from real
`ModeloWorkReviewCasilla` records, formatting over `NUMBER_FORMATS`),
`agent-b\proto\row.py` (`CasillaRow`, `SectionHeader`, `HelpBand`, `FormProgress`, and the
benchmark-only `CompositeCasillaRow` and `CasillaVirtualList`), `agent-b\proto\fixtures.py`
(synthetic 303 rows built as real review records; labels from the committed catalogues),
`agent-b\proto\showcase.py`, `agent-b\proto\bench.py`, `agent-b\proto\navbench.py`.
Themes via `install_cadrumo_themes`, CSS via `tokenised` and `BASE_CSS`.

Screenshots (SVG from `save_screenshot`, PNG repainted with the pinned font; every frame
`missing_glyphs=()`), in `agent-b\shots\`:

- `row-page-en-light-80x24.svg` / `row-page-en-dark-80x24.svg` — comfortable, 80×24
- `row-page-en-light-80x24-compact.svg` — compact, 80×24
- `row-page-en-light-120x36.svg` / `row-page-en-dark-120x36.svg`
- `row-page-en-light-160x48.svg` / `row-page-en-dark-160x48.svg`
- `row-page-es-light-80x24.svg`, `row-page-es-dark-120x36.svg`, `row-page-es-light-120x36-compact.svg`
- `row-page-hu-light-80x24.svg`, `row-page-hu-dark-160x48.svg`

Each has a `.png` twin for quick viewing. Prototype limits: the footer shows only `n Next to review` because the row's own
bindings are declared hidden; formula texts and section titles are hand-written stand-ins for
what lens A must supply; rows `110`/`71` fall back to `Casilla N` because their catalogue
label is not under the continuidad key the fixture reads. The frames show all 12 origin states and both
attention overlays on one page (03 proven zero vs 10 entered zero vs 16 n/a vs 14 empty vs
06 not calculated; 07 imported+blocked; 12 staged with "was"; 28 override; 44/65 default;
45 could not calculate; 110 informational; IBAN masked; boolean; NIF).

---

#### 3. Suggestions, ranked by user value vs effort

| rank | suggestion | value | effort |
|---|---|---|---|
| 1 | Carry `required`, `entered_by_operator` (from `input_values_by_casilla_id`) and localized label/help on the review row (or on lens A's form model). Unlocks O7/O11/O12 and a locale-correct label. | very high | small (application projection) |
| 2 | Shared locale value formatter (money/ratio/decimal/int/bool/date/iban-mask) lifted from `NUMBER_FORMATS`; use it on the inputs page now (fixes B2) | very high | small |
| 3 | `CasillaRow` render-only widget + the closed vocabulary table with a totality/uniqueness guard; section-at-a-time mounting | very high | medium |
| 4 | Docked help band with synthesised what/from/formula/law; skip boilerplate help | high | small–medium |
| 5 | Replace `✖` with `!` (and `⚠`/`ⓘ` with `▲`/`·` or ASCII `i`) product-wide; add a glyph-in-font gate over every glyph constant and catalogue string | high (tofu today) | small |
| 6 | Section/form progress strips; `n` next-to-review; required/attention filter | high | small |
| 7 | Semantic-id feeder rows into a "working figures" fold; `form_number` for the number column | medium | small |
| 8 | Density toggle (compact auto below 30 rows / 100 cols) | medium | small |
| 9 | Line-API virtual list for sections/pages above ~300 rows (none today; 390's top-level page is 407) | medium | medium |
| 10 | Sibling-prefix elision for 200 (median label 135 → 61 cells) with the elided prefix in the section header | medium (200 only) | medium |
| 11 | Catalogue clean-up: `Npct`, `ops`, `RG` abbreviations, legal notes inside labels, boilerplate help | medium | medium (catalogue/CLI workflow) |

---

#### 4. Bugs noted (not fixed)

- **B1 — Shipped glyphs missing from the pinned font.** `✖` (`widgets.py:345`,
  `models.py:91`, all four `flows.yml` `section_pending` at en `:102`, es `:103`, ca `:104`,
  hu `:104`), `⚠` (`widgets.py:265`, `status.py:24`), `ⓘ` (`widgets.py:264`) are not in
  `CascadiaMono-Regular.ttf` (measured, 1.5). They render as tofu in the visual review and
  depend on font fallback in Windows Terminal.
- **B2 — No locale formatting on the inputs page.** `inputs.py:109` renders `str(value)`;
  es/ca/hu operators see `1234.50`.
- **B3 — "Broken calculation chain" asserted before any calculation.**
  `_work_review_assembly.py:296-299` flags every computed row `BROKEN_CALCULATION_CHAIN`
  when `revision is None`, so a consumer reading only the row reports a fault on a fresh
  work unit.
- **B4 — No plural handling.** `flows.manager.onboarding.section_pending` renders
  "✖ Datos - 1 obligatorias" / "1 obligatòries"; the catalogue has no plural forms.
- **B5 — Ratio scale contradicts its declaration.** `CasillaDataType.RATIO` says "a
  proportion or rate expressed as a fraction" (`schema_base.py:699-700`), while registry
  values are percent points (130 parameters `value = "20"`; 303 casilla 08 is a ratio
  holding 21). A formatter that trusts the docstring prints `2.100 %`.
- **B6 — Register inconsistency in Spanish.** `tui.modelo.input_kind.manual` =
  "Lo introduces tú" (`locales/es/common.yml:2085`) vs `docs.…input_kind.manual` =
  "Lo introduce usted" (`locales/es/docs.yml:99`).
- **B7 — Override state unreachable from the TUI.** The admission makes only `MANUAL`
  casillas writable (`edit_admission.py:139-159`); a bound casilla is
  `SCHEMA_DECLARED_READ_ONLY`, so "your value replaces the import" (O2) can only arise
  from paths outside the TUI, and binding overrides address `BindingId`, not the casilla
  the operator is looking at.
- **B8 — `ModeloValueKind.DEFAULT` has no producer** (`filing/schema.py:54`; grep finds no
  non-test emitter) and `LITERAL` conflates entered and defaulted manual values
  (`_work_review_assembly.py:268-270`).
- **B9 — Orphan catalogue family.** `flows.modelo_review.filter.*` (es `flows.yml:133-217`,
  with developer words "Literal", "Heredado") has no production consumer; only
  `core/tests/test_estado_casilla_oficial.py:69` names it.
- **B10 — Blank means "no intent" in the current edit surface** (`overview.py:364,368`):
  a value cannot be cleared, and an emptied box silently keeps the old value.
- **B11 — Label content.** 24 es labels with `Npct`, 6 with ` ops `, 9 with ` RG `; labels
  embedding legal/implementation notes; 303 `dr303-71` has help but no label under
  its continuidad key (falls through to another key).

---

#### 5. Risks and open questions

- **Help band vs 80×24.** Banner 1 + progress 1 + footer 1 + band ≤ 6 leaves 15 rows;
  compact rows keep ≥ 12 casillas visible. If lens E adds a tab strip or breadcrumbs, the
  band should collapse to 2 lines on 24-row terminals.
- **State derivation lives where?** The vocabulary needs `required`, the entered flag and
  review-level `calculation_revision_id`. If lens A's form model carries a precomputed
  `origin` enum instead, the TUI only maps enum → glyph/words and the totality guard
  moves to the application. Recommended: the application owns `origin` (it has the
  facts), the TUI owns attention (Δ) and presentation.
- **Source words have two catalogues**: `flows.modelo_review.filter.option.binding_source.*`
  (short nouns) and `docs.*.binding_source` (phrases "desde sus apuntes de IVA"). Pick
  one canonical key per concept (locales rule) before the row uses either.
- **Ratio scale** (B5) must be declared per casilla/parameter before ratios are editable.
- **Variable-height rows** (1 or 2 lines) are fine for mounted per-section rows but a
  virtual list wants fixed height; the virtual variant should use fixed 2-line rows or
  a precomputed height table.
- **Sensitive display**: IBAN masking in the row is proposed; D8's list of sensitive
  values (third-party NIFs, names) needs an owner decision before the row shows them.
- **`ContentDataTable` width policy is O(rows × columns) per resize**:
  `_natural_width` walks every row (`components/widgets.py:222`, `:251-260`) on each `on_resize`;
  harmless at today's table sizes, a cost at 3,400 rows if the DataTable fallback is chosen.
- **Line-API accessibility**: a single-widget list must expose the focused row's text for
  assistive tooling itself; Textual does this per widget, not per line.
- **Measurement caveats**: timings are from Textual's headless pilot on one Windows host
  (`run_test`, three runs, median); absolute numbers will differ in a real terminal, the
  ratios between architectures are the evidence.

---

#### 6. Overlap notes

- **Lens A (form model)**: needs per row `required`, `entered_by_operator`,
  localized `label`/`help` for the active locale, `form_number` for semantic-id rows,
  `CalculationReportRowRole`, section titles (no section token has a catalogue entry),
  and a declared ratio scale. Recommend A emits a closed `origin` enum matching O1–O12 so
  the TUI renders, not classifies. Pages should be bounded by full-path section (max 156
  rows today).
- **Lens C (edit)**: the row triggers edit with `Enter`, clear with `x` (stages
  `CLEAR_DECLARED_VALUE`), revert with `u`; after the editor closes focus returns to the
  casilla id; staged rows show `Δ` and "was {old}". An unparsed lexeme stays in the
  editor (D4), so the row never shows an invalid value. Override of an imported value
  (O2) needs an admitted intent the surface does not offer today (B7).
- **Lens D (import/sources)**: the row hints source by `↓`/`⇣` + source words and `s`
  jumps to it; D should supply one canonical source-name key per `BindingSourceKind` and,
  if available, the import timestamp for the help band.
- **Lens E (page flow)**: the form strip, section folds with `✓`/`!` titles, `n`
  next-to-review and the required/attention filter are the page-level hooks; E owns where
  the help band sits relative to any tab strip, and whether the density toggle is global.

## Sources

- `dev/tui/_raster.py`
- `dev/tui/_raster.py:143-154`
- `src/cadrumo/application/modelo/calculation_summary_presentation.py:135-145`
- `src/cadrumo/application/modelo/work_review.py:109-145`
- `src/cadrumo/domain/filing/schema.py:54`

- `src/cadrumo/entrypoints/tui/profile/overview.py:95-102`
- `src/cadrumo/locales/{es,en,ca,hu}/modelo/schema/*.yml`
