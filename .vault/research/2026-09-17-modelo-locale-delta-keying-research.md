---
tags:
  - '#research'
  - '#modelo-locale-delta-keying'
date: '2026-09-17'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:63eadf02f57c7e2681208b8b45d83558a03361c79545fd4a0ed146a46033b9ec'
related: []
---

# `modelo-locale-delta-keying` research: `modelo locale catalogue repetition and gap census`

The Modelo registry stores casilla declarations as deltas (an edition states only what changed, inherited rows are materialised), but the Modelo locale catalogues under `src/cadrumo/locales/<locale>/modelo/schema/` are keyed and populated per materialised edition. This census measures the consequences through the production resolver chain on the published generation (2026-09-17, 58 modelos, 146 editions, 31,199 casilla occurrences, 12,901 modelo/casilla identities). Measurement scripts: `var/test-iter/label_audit.py`, `var/test-iter/label_audit2.py`; per-occurrence rows in `var/test-iter/label_audit/rows.json`.

## Findings

### The resolver already inherits; the key universe and catalogue do not

- Resolution walks own occurrence key, then the stating edition's occurrence key for an inherited row, then the continuity key, then Spanish (`src/cadrumo/domain/calculations/registry/modelo_localization.py:244`, `dev/registry/compiler/loader_materialisation.py:1715`). This is the inheritance the edition-authoring decision requires.
- The key universe emits a label and a help key for every casilla of every materialised edition plus the continuity key (`dev/registry/compiler/loader.py:365`), and the scaffold fills every emitted key. Inherited rows therefore receive catalogue entries of their own.
- Spanish catalogue, casilla keys: inherited rows carry 17,191 label values, 707 null labels, 16,537 help values and 1,361 null helps; stated rows carry 12,633 label values, 668 null labels, 11,547 help values and 1,754 null helps. English has the same shape.
- One runtime consumer bypasses the chain and reads the raw occurrence key: `src/cadrumo/application/modelo/workspace.py:723`.

### Repetition

- 14,270 Spanish occurrence values restate the same casilla's text under another edition (100: 6,650; 200: 2,764; 390: 1,057; 303: 874).
- 6,012 occurrence values are byte-identical to the continuity value they shadow.
- 11,191 values repeat across editions whose continuity key is empty; they are collapsible onto one key.
- 489 repeat on casillas without `continuidad_id`; about 5,200 occurrences carry no `continuidad_id` (220/2024: 1,699; each Modelo 100 edition 260-460).
- 345 identities change `continuidad_id` between editions.

### Derived help text

About 26,000 of 28,000 Spanish help values are generated from the label, not authored:
- 18,411 read "Indique o revise «label» para completar esta autoliquidación."
- 6,733 read "Consulte la información correspondiente a la casilla: label".
- About 1,060 read "Dato del modelo N, ejercicio Y…", "Información de la casilla…", or the garbled "Información fiscal sobre información fiscal de la casilla …" (144).

Helps carrying distinct text number about 4,100. The only runtime reader treats help as optional (`src/cadrumo/domain/calculations/registry/schema_surfaces.py:439`, `src/cadrumo/domain/calculations/registry/queries.py:1189`).

### Placeholder and wrong text

- 181 Spanish occurrences resolve to a scaffold placeholder such as "Casilla iva.repercutido.general: iva cuota repercutida general", introduced by commit `1d06155ad4`.
  - Where: 303/2023-2025 (96), 210/2023-2024 (62), 193/2022-2023 (14), 131/2026, 190/2022-2023, 303/2026.
  - 98 are occurrence keys shadowing a real same-box sibling label; 43 continuity keys hold placeholder text and serve 83 occurrences.
  - Copies exist in en (128), hu (129) and ca (24).
- Same casilla, same box, different Spanish text across editions: 1,723 identities.
  - 1,606 differ in wording (100: 963; 200: 422; 303: 121); these are candidate genuine overrides or drift and need source review.
  - 68 are placeholder against real text; 49 differ only in case or punctuation.
- Identity divergence: 7 identities change both text and box number; 86 keep the text while the box number changes.

### Gaps

- Before in-flight work, 671 occurrences (516 identities) had no Spanish label: inherited rows of 220/2025, 222/2023-2024, 345/2022-2024, 189/2023-2024, 136, 200/2024, 182, 188, 151, 296 and 309, with empty continuity keys.
- An uncommitted change fills 516 Spanish continuity labels:
  - 454 are copied from the same box in a sibling edition, 11 from a sibling with a different box, and 51 are new text.
  - It also adds 23 garbled helps and unaccented forms (Codigo 6, razon 6, identificacion 2, Cuantia 1, Numero 1).
- en, ca and hu lack the same 671 occurrences; 597 have a same-box sibling translation and 74 need new translation.

### Storage overrides discard label inheritance

- Editions hydrated from a `casilla_storage_baseline` patch inherited rows through `casilla_overrides`.
- Any patched row loses its label origin (`dev/registry/compiler/loader_materialisation.py:1293`, `:1204`), so it resolves only through its own occurrence key and the continuity key. This is why those editions need restated labels, and it is the cause of the 671-occurrence gap.
- 14,937 overrides are authored. Most patch provenance only: `continuidad_origin` 3,429; `continuidad_origin`, `continuidad_evidence` and `source_refs` 3,343; `source_refs` 2,727; `legal_refs` and `source_refs` 1,069; plus other provenance-only combinations.
- A few hundred change identity (`id`, `number` or `continuidad_id`), which is the only case where the stated edition's text may no longer apply.

### Constraint on collapse: the locale barrier

Moving a non-Spanish value to a less specific tier while Spanish keeps a more specific override would let a locale render a lineage-wide text where Spanish renders an edition-specific one. The current chain exhausts the requested locale across every tier before falling back to Spanish (`modelo_localization.py:244`), so collapse requires that a locale may not resolve below the tier at which Spanish resolves.

## Sources

- `src/cadrumo/domain/calculations/registry/modelo_localization.py:244`
- `dev/registry/compiler/loader_materialisation.py:1715`
- `dev/registry/compiler/loader.py:232`
- `dev/registry/compiler/loader.py:365`
- `src/cadrumo/application/modelo/workspace.py:723`
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py:439`
- `dev/locales/revision_label_restatement.py`
- `dev/locales/casilla_label_derivation.py`
- commit `1d06155ad4`
