---
tags:
  - "#plan"
  - "#justificante-reframing"
date: "2026-04-21"
modified: '2026-07-17'
body_hash: 'sha256:eb49e825b84e849500300d5eedc5e2eb75c172f5eb9ae75242df2e86f71c4399'
related:
  - "[[2026-04-21-justificante-reframing-adr]]"
  - "[[2026-04-21-justificante-reframing-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - '[[2026-07-12-justificante-reframing-audit]]'
---
# `justificante-reframing` plan

> **Reconciled 2026-07-12 â€” superseded, not active.** The proposed narrative page and `aeat filing import --from-*` workflow were superseded by the accepted bucket-scoped filing-record and modelo-reconcile architecture. These rows are resolved as retired work, not as instructions to revive legacy flags. Evidence is recorded in `2026-07-12-justificante-reframing-audit`.

## Goal

Bring the narrative layer (docs, EPIC titles, docstrings) in line with the pdf-taxonomy vocabulary locked in cluster A. Ship alongside cluster A or immediately after.

## Step 1 â€” `docs/concepts/aeat-pdfs.md`

Shared deliverable with cluster A; this cluster owns the content. One H1 + six H2 sections + a short "not an import source" subsection. ~400 words.

**Checklist**:

- [x] H2 *Justificante de presentaciÃ³n* â€” what it is, when Kent gets it, consumed by `aeat filing import --from-justificante`.
- [x] H2 *DeclaraciÃ³n (copia de la declaraciÃ³n)* â€” what it is, consumed by `aeat filing import --from-declaracion` (future, cluster D).
- [x] H2 *Borrador* â€” what it is, primarily Renta, consumed by `aeat filing import --from-borrador` (future, cluster F).
- [x] H2 *PredeclaraciÃ³n / simulaciÃ³n* â€” what it is, consumed by `aeat filing import --from-predeclaracion` (future, cluster F).
- [x] H2 *Datos fiscales* â€” not an import source; may feed `aeat filing build` later.
- [x] H2 *Datos personales* â€” not an import source; identity lives in `AutonomoProfile`.
- [x] Cross-links to `.vault/adr/2026-04-21-pdf-taxonomy-adr.md`.

## Step 2 â€” EPIC #233 hygiene

- `gh issue edit 233 --title "Umbrella: Kent can import a past filing he made outside the tool"`
- `gh issue comment 233 --body "<cross-ref to EPIC #305 and the canonical vocabulary ADR>"` â€” same comment as already posted from cluster A's execution; if already present, reuse.

## Step 3 â€” Docstring refinements

Run: `rg -n "justificante" src/aeat/ --type py` â€” review each hit. Keep occurrences where "justificante" means the receipt (most of them). Rephrase occurrences where "justificante" means "past filing" in general. Expected < 10 edits; no behavioural change.

## Step 4 â€” Add one regression assertion

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

## Step 5 â€” Quality gates

- `uv run ruff check docs/ src/aeat/domain/justificante/` â€” clean.
- `uv run ty check src/aeat/domain/justificante/` â€” clean.
- `uv run pytest -m unit src/aeat/domain/justificante/` â€” green (adds 1 test).

## Kent UX roleplay

- Kent opens the new `docs/concepts/aeat-pdfs.md`. He reads "Justificante de presentaciÃ³n: the receipt AEAT emails you after a filing â€” it has your CSV and totales but does not list every casilla." He stops being confused about why his imported draft has empty casillas.
- Kent running `aeat filing import --help` sees all four `--from-*` flags listed once the downstream clusters ship; the concept doc is linked in the help footer.

## Non-goals

- No Python rename.
- No CLI rename.
- No changes to `SubmittedFiling` fields.
- No translation work.
