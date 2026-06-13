---
tags:
  - "#plan"
  - "#justificante-reframing"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-justificante-reframing-adr]]"
  - "[[2026-04-21-justificante-reframing-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
---

# `justificante-reframing` plan

## Goal

Bring the narrative layer (docs, EPIC titles, docstrings) in line with the pdf-taxonomy vocabulary locked in cluster A. Ship alongside cluster A or immediately after.

## Step 1 — `docs/concepts/aeat-pdfs.md`

Shared deliverable with cluster A; this cluster owns the content. One H1 + six H2 sections + a short "not an import source" subsection. ~400 words.

**Checklist**:

- [ ] H2 *Justificante de presentación* — what it is, when Kent gets it, consumed by `aeat filing import --from-justificante`.
- [ ] H2 *Declaración (copia de la declaración)* — what it is, consumed by `aeat filing import --from-declaracion` (future, cluster D).
- [ ] H2 *Borrador* — what it is, primarily Renta, consumed by `aeat filing import --from-borrador` (future, cluster F).
- [ ] H2 *Predeclaración / simulación* — what it is, consumed by `aeat filing import --from-predeclaracion` (future, cluster F).
- [ ] H2 *Datos fiscales* — not an import source; may feed `aeat filing build` later.
- [ ] H2 *Datos personales* — not an import source; identity lives in `AutonomoProfile`.
- [ ] Cross-links to `.vault/adr/2026-04-21-pdf-taxonomy-adr.md`.

## Step 2 — EPIC #233 hygiene

- `gh issue edit 233 --title "Umbrella: Kent can import a past filing he made outside the tool"`
- `gh issue comment 233 --body "<cross-ref to EPIC #305 and the canonical vocabulary ADR>"` — same comment as already posted from cluster A's execution; if already present, reuse.

## Step 3 — Docstring refinements

Run: `rg -n "justificante" src/aeat/ --type py` — review each hit. Keep occurrences where "justificante" means the receipt (most of them). Rephrase occurrences where "justificante" means "past filing" in general. Expected < 10 edits; no behavioural change.

## Step 4 — Add one regression assertion

New test `src/aeat/domain/justificante/test_vocabulary_stable.py`:

```python
def test_justificante_public_surface_is_frozen() -> None:
    """Guards against accidental renames in aeat.domain.justificante."""
    from aeat import justificante
    expected = {
        "Justificante",
        "JustificanteCsvNotFoundError",
        "JustificanteError",
        "JustificanteParseError",
        "JustificanteParserBackend",
        "JustificanteVerificationError",
        "parse_justificante",
        "verify_csv",
    }
    assert set(justificante.__all__) >= expected
```

Explicit lock so cluster-A's re-home of `JustificanteError` under `PdfFilingImportError` can't accidentally remove any symbol.

## Step 5 — Quality gates

- `uv run ruff check docs/ src/aeat/domain/justificante/` — clean.
- `uv run ty check src/aeat/domain/justificante/` — clean.
- `uv run pytest -m unit src/aeat/domain/justificante/` — green (adds 1 test).

## Kent UX roleplay

- Kent opens the new `docs/concepts/aeat-pdfs.md`. He reads "Justificante de presentación: the receipt AEAT emails you after a filing — it has your CSV and totales but does not list every casilla." He stops being confused about why his imported draft has empty casillas.
- Kent running `aeat filing import --help` sees all four `--from-*` flags listed once the downstream clusters ship; the concept doc is linked in the help footer.

## Non-goals

- No Python rename.
- No CLI rename.
- No changes to `SubmittedFiling` fields.
- No translation work.
