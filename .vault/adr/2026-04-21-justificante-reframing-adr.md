---
tags:
  - "#adr"
  - "#justificante-reframing"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-justificante-reframing-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
---

# `justificante-reframing` adr: `keep-the-name-narrow-the-docs-correct-the-narrative` | (**status:** `accepted`)

## Problem Statement

Across docs, issue titles, and contributor-facing commentary, "importing a justificante" has been used as shorthand for "importing a past filing" — an operation that strictly requires a receipt plus (depending on intent) a declaración / borrador / predeclaración. Cluster A's ADR fixed the code-level vocabulary. This ADR commits the same vocabulary to the narrative layer.

## Considerations

- `aeat.domain.justificante` is a correctly-scoped module. Renaming breaks the amendment-baseline path (`#271`, `_complementaria._resolve_original_metadata`). The code stays.
- The name is Spanish, per project mandate ("Spanish is the default output language and authoritative AEAT terminology baseline"). Anglicising or Englishing the module name would regress that mandate.
- EPIC #233's title reads "Kent can import a past filing he made outside the tool" and lists three backends: `--from-justificante`, `--from-aeat`, `--from-spreadsheet`. The umbrella EPIC #305 adds `--from-declaracion`, `--from-borrador`, `--from-predeclaracion`. Neither title is wrong, but #233 reads like the universe of past-filing imports when in fact it originally scoped the three specific backends listed. A small title polish + description comment makes the relationship explicit.
- Kent needs one place to learn which PDF class is which. `docs/concepts/aeat-pdfs.md` (already queued in cluster A's plan) is that page.

## Constraints

- **No code rename.** `aeat.domain.justificante` stays.
- **No public-API change.** `Justificante`, `parse_justificante`, `JustificanteError`, `SubmittedFiling.justificante_csv`, `SubmittedFiling.justificante_pdf_path` all keep their names.
- **No CLI rename.** `aeat filing import --from-justificante` stays.
- **No amendment-engine regression.** `_resolve_original_metadata` behaviour preserved.
- Everything this ADR changes is **documentation and narrative**; no `.py` edits beyond a handful of docstring refinements.

## Implementation

### 1. Lock terminology doc

`docs/concepts/aeat-pdfs.md` (shared with cluster A; cluster G owns the content):

- One paragraph per class from the pdf-taxonomy ADR §1 table.
- Each paragraph explicitly states: what Kent sees, where it comes from, which import backend consumes it (if any).
- A "not an import source" subsection for *datos fiscales* and *datos personales*.
- Cross-links to the per-class module under `src/aeat/<class>/` (when they exist).

### 2. EPIC hygiene

- Edit EPIC #233: prepend "Umbrella: " to its title; first line of its body says "This EPIC tracks every `aeat filing import --from-*` backend; see #305 for calc-verified real-PDF import."
- Add a comment on EPIC #305 (already opened) cross-linking to #233.
- No individual child-issue titles change.

### 3. Docstring refinements

Run a grep for occurrences of the word "justificante" in docstrings where it might mean "past filing" rather than "receipt" and refine. Expected small-touch: 3–8 comment / docstring edits. None change behaviour.

### 4. Out of scope

- `SubmittedFiling` field rename. `justificante_csv` and `justificante_pdf_path` are correctly named — the receipt is the artefact persisted there.
- `aeat.domain.justificante` module rename, export rename.
- CLI flag rename.
- Any translation of the Spanish module names to English.

## Consequences

- One-stop documentation page tells every future contributor what each PDF class is.
- EPIC #233 cleanly scopes its three original backends; the new real-PDF backends have a separate, visible home in #305.
- The word "justificante" in docs and issues now consistently means "receipt" — matching what the code actually does.
- Zero code churn; zero behavioural change; zero risk to `#271` shipping contracts.
