---
tags:
  - "#research"
  - "#justificante-reframing"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-12-justificante-parser-adr]]"
  - "[[2026-04-20-pdf-import-adr]]"
---

# justificante-reframing research

## Problem

The module name `aeat.domain.justificante` is technically correct (it parses *justificantes de presentación*) but colloquially "importing a justificante" has been used as shorthand for "importing a past filing" — which is a broader operation than what the receipt enables. The pdf-taxonomy ADR (cluster A) locked a canonical vocabulary that disambiguates receipt from declaración. This cluster handles the soft consequence: making sure existing docs, issue titles, and developer narrative follow the new vocabulary without breaking any shipped contract.

## Observed uses of "justificante" today (evidence)

Grepping the repo turns up four classes of reference:

- **Correct** — code that actually reads receipts: `src/aeat/domain/justificante/` module, `Justificante` pydantic record, `parse_justificante`, CLI `aeat filing import --from-justificante`, `SubmittedFiling.justificante_csv` / `justificante_pdf_path`. These stay.
- **Overloaded** — docs / issue titles using "justificante" as a synonym for "past filing":
    - EPIC #233 title uses "justificante" but scopes all import backends.
    - `docs/coverage/kent-capabilities.md` mentions "import from justificante" as a wall.
    - ROADMAP-era commentary around past-filing import.
- **Amendment-baseline dependency** — `_resolve_original_metadata` in `src/aeat/application/filing/_complementaria.py` reads `original.justificante_csv` / `original.justificante_pdf_path` when resolving an original filing's CSV for an amendment. This coupling stays — the amendment engine correctly consumes the receipt.
- **Doctor-surface language** — none today.

The overloaded uses are the only real targets of this cluster. Code-level references are already correct.

## Cluster-A ADR already resolved most of this

The pdf-taxonomy ADR (`2026-04-21-pdf-taxonomy-adr`) locks:

- Module keeps its name (`aeat.domain.justificante`).
- Public surface unchanged.
- CLI flag unchanged (`--from-justificante`).
- New siblings `aeat.adapters.inbound.declaracion` / `aeat.adapters.inbound.borrador` / `aeat.predeclaracion` come with their clusters.

What cluster A did **not** address: docs, concept pages, issue titles, public narrative. That's this cluster's narrow scope.

## What changes

- A concept doc explaining the six PDF classes (cluster-A plan already lists this as step 5 under cluster A — this cluster restates and commits to delivering it as part of the "reframing" work).
- EPIC #233 title / description edit (cluster-A plan step 6 — already queued; this cluster is the one that actually does it).
- Any in-code docstrings or `# comment`s that mis-use "justificante" for "past filing" are tweaked.

## What does NOT change

- `aeat.domain.justificante` module name, exports, error hierarchy (`JustificanteError` just moves under `PdfFilingImportError` per cluster A).
- `Justificante` pydantic record shape.
- `parse_justificante` signature.
- `aeat filing import --from-justificante` command.
- `SubmittedFiling` fields referencing the justificante.
- `_complementaria._resolve_original_metadata` behaviour.

## Risks

- **Doc drift** — if this cluster lands the concept doc, future contributors must keep the vocabulary when adding PDF-class modules. Cluster D's plan must reference the concept doc.
- **Historic issue titles** — cleaning up EPIC #233 is safe; changing individual child issue titles may break external links. Only change titles when the new one is strictly more precise.
