---
tags:
  - '#adr'
  - '#renta-savings-income-source'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:92e70276297b655752a7348b6a16a6ecd1eeef0d17859301c984b517dd9e8f78'
related:
  - "[[2026-11-11-renta-savings-income-source-adr]]"
  - "[[2026-11-12-renta-savings-income-source-reference]]"
---
# `renta-savings-income-source` adr: `Place the savings detail rows in the Modelo 100 XML export from the hydrated official design` | (**status:** `accepted`)

Accepted 2026-11-12 10:59 by CADRUMO-PRIME as written at lane/calculators 82b6ed73aa, under the operator's delegation, with four conditions written into Constraints. It amends `2026-11-11-renta-savings-income-source-adr`, section "Rows". Until it lands, the export ruling of CADRUMO-PRIME of 2026-11-12 10:55 governs: a typed export refusal for a return that holds savings positions or position-linked rows.

## Problem Statement

The accepted record says each position gives one `RegistroB11` or `RegistroB13` occurrence and that these rows reach the XML through the existing row-grain path. They do not. The Modelo 100 XML export renders from one dictionary per edition, the declaration dictionary named by the layout's `dictionary_source_ref` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/export_layouts/0001-declarations.toml:4`, and the edition overrides at `revisions/2021/revision.toml:6997`, `2022/revision.toml:7542`, `2023/revision.toml:8255`, `2024/revision.toml:8654` and `2025/revision.toml:8497`). That dictionary family (`01-100`, `04-100` to `08-100` under `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/`) has no `IMP1DB11`, `IMP2DB11`, `IMP3DB11`, `IMP1DB13`, `IMP2DB13` or `IMP3DB13` entry. The input dictionaries (`02-100`, `09-100` to `13-100`) and every XSD (`03-100`, `25-100` to `29-100`) carry them. So 0027, 0029 and 0037 now compute from records, but the per-position rows behind them cannot be placed.

## Considerations

- Official design, every edition 2020 to 2025: `B11` and `B13` are optional (`minOccurs="0" maxOccurs="1"`), `RegistroB11` and `RegistroB13` repeat up to 20 times (`minOccurs="0" maxOccurs="20"`), and each `IMP1`, `IMP2` and `IMP3` element is optional (`minOccurs="0" maxOccurs="1"`). Locators: 2025 `03-100-esquema-xsd-…xsd:4396-4437`; 2024 `29-100-…xsd:4173-4214`; 2023 `28-100-…xsd:3916-3957`; 2022 `27-100-…xsd:3702-3743`; 2021 `26-100-…xsd:3447-3488`; 2020 `25-100-…xsd:3092-3133`.
- The records sit under `/DatosEconomicos/TomaDatosAmpliada/RdtoCapitalMobiliario/RdtoCapitalMobiliarioAhorro/` (2025 input dictionary `02-100-…properties:237-246`). `TomaDatosAmpliada` itself is required (`minOccurs="1" maxOccurs="6"`, 2025 XSD line 1858), and its `RdtoCapitalMobiliario` child is optional (line 1786). The declaration dictionary already addresses other `TomaDatosAmpliada` paths, so the exporter writes into that block today.
- No rule found ties the totals to the rows. The XSD has no assertion relating 0027 or 0029 to their detail records, and neither dictionary states one. Absence of a rule in these files is not proof that AEAT's validation accepts totals without rows. So the coordinator ruled out exporting the totals alone (option b below) until the official design shows it.
- Every edition has its own registered input-dictionary source: `aeat-dr-100-2020-input-dictionary` to `aeat-dr-100-2025-input-dictionary`.
- Project rule: export layouts derive record order, positions, repetitions and conditions from the selected official design through the hydrated registry layout (`.claude/rules/09-filing-and-live-state.md`, export invariants). A hand-kept list of element paths is not admitted.
- No persona holds savings positions, position-linked rows or capital-mobiliario payer records (checked 2026-11-12), so no green persona row depends on this.

## Considered options

- (a) The XML layout hydrates the repeated savings records from the edition's input dictionary, checked against the XSD, and places one occurrence per position and detail record. Chosen.
- (b) Export the totals 0027, 0029 and 0037 without their detail records and serve a limitation. Rejected by the coordinator's ruling of 2026-11-12 10:55: nothing in the official design shows that totals may go without their records.
- (c) Refuse the export for a return that holds savings positions or position-linked rows, with served words. This is the interim state the ruling put in place now. It is not a resolution, because a saver can never export.
- (d) A hand-kept table of the six element paths per edition. Rejected: it duplicates the official design and breaks the export invariant.

## Constraints

- The row placement is derived from the official design through the hydrated registry layout for every admitted edition. No element path, record name or occurrence bound is written in Python, and no year appears in any key, id, field or parameter.
- One mechanism serves every edition in the support envelope. An edition override exists only where the official design differs, and today none does.
- The XSD is the authority for structure and bounds. An entry from the input dictionary that the edition's XSD does not admit is refused at layout validation, not at export.
- More occurrences than the XSD admits are refused at export, through the existing bound (`src/cadrumo/application/filing/export_xml_dictionary.py:883-897`).
- The occurrence values are the ones the savings source family computes (gross, withholding and expenses per occurrence). The exporter computes nothing.
- Acceptance condition 1: a path that both dictionaries carry with different definitions is refused at layout validation. The declaration dictionary is never overridden.
- Acceptance condition 2: more positions than the occurrence bound is a typed export refusal with served words. Rows are never merged or dropped to fit.
- Acceptance condition 3: proof per admitted edition, enumerated from the registry envelope, and no regression in any existing Modelo 100 export.
- Acceptance condition 4, order: the interim refusal (c) hands over first and alone; then the frontend record-group read and the unmasked profile-persistence reds; then this change.
- The interim refusal (c) stays until this lands. It is removed in the same change that places the rows, and both hand over together if any persona ever holds savings positions.

## Implementation

We will let an XML-dictionary export layout name, besides its declaration dictionary, the edition's input dictionary as a second source, admitted only for repeated records that the XSD declares and the declaration dictionary does not carry. The savings source family emits one row value per occurrence, and the existing row-grain renderer places them under `B11` and `B13`.

- The layout gains an optional second dictionary reference, declared once at the earliest edition and inherited. Layout hydration merges its entries for repeating XSD elements only and validates each against the XSD.
- The savings bindings gain row columns for `IMP1`, `IMP2` and `IMP3` of each record, in the shape the `activity_asset_disposal` family uses (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml`, row columns).
- The renderer checks that the occurrences' gross sums equal 0027 and 0029 and that their expenses equal 0037 (`_require_value_stated_by_rows`, `export_xml_dictionary.py:906`).
- Tests: every edition in the envelope places the rows. The manual's worked examples round-trip through the XML parser. A 21st occurrence is refused. An input-dictionary entry outside the XSD is refused at layout validation.
- Hypotheses that may change: the layout field name for the second dictionary, and whether the merge lives in layout hydration or in the dictionary entry reader.

## Rationale

Option (a) is the only one that both places what the official design asks for and keeps a single source of structure. The XSD admits the records and the input dictionary names them, so hydrating from those two official files keeps the layout derived rather than authored. Option (b) rests on an unproven reading of AEAT validation, and option (d) adds a second structural source.

## Consequences

- A saver's return exports with its per-position detail records, and the interim refusal disappears.
- The XML layout can carry a second official dictionary. Other repeated records that only the input dictionary names can later use the same path.
- Reconsider if AEAT publishes these records in the declaration dictionary, or if a later XSD changes `RegistroB11` or `RegistroB13`.
