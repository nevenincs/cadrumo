---
tags:
  - '#audit'
  - '#aeat-verify'
date: '2026-04-26'
modified: '2026-04-26'
related:
  - "[[2026-04-25-aeat-verify-plan]]"
  - "[[2026-04-25-aeat-verify-adr]]"
  - "[[2026-04-25-aeat-verify-research]]"
  - "[[2026-04-25-pdf-sanitizer-plan]]"
  - "[[2026-04-25-pdf-sanitizer-adr]]"
  - "[[2026-04-25-pdf-sanitizer-research]]"
  - "[[2026-04-24-aeat-verify-reference]]"
---



# `aeat-verify` audit: `modelo-100-w1-pipeline-status`

## Scope

W1 (Modelo 100 IRPF anual) pipeline-phase audit per the per-modelo
9-phase loop locked in the parent ADR. This audit records the
state at the moment the `pdf-sanitizer` sub-feature reached
plan-phase 8 (every security-load-bearing test passing) and the
end-to-end pipeline was validated against a real Modelo 100 capture.

The audit does not record W1 P9 as `done`. The sanitiser
infrastructure is ready; the *fixture commit* itself remains
operator-gated because exhaustive enumeration of every PII surface
in a Modelo 100 declaration (~80-86 casilla monetary values, plus
free-text fields) is beyond what the autonomous run can responsibly
land without operator review of every cleartext-to-synthetic edit.

## W1 phase-by-phase outcome

### P1 — Discover

`done`. Three live IRPF expedientes enumerated (2021, 2022, 2023)
during the original 2026-04-24 capture round and re-confirmed
2026-04-25 after the worktree recovery. Discovery covers a single
modelo (100); the full cross-wave P1 enumeration sweep against
Kent's account is still pending Cl@ve re-authentication.

### P2 — Capture

`done`. Three raw PDFs at:

- `scratch/recon-corpus/20260424T184450Z/irpf-2021/justificante.pdf`
  (~316 KB, 6 pages, iText 2.1.4 producer, legacy column-split layout)
- `scratch/recon-corpus/20260424T184450Z/irpf-2022/justificante.pdf`
  (5 pages, AEAT OVCT-IPDF/OVCT-XPDF producer, modern layout, PDF/A-1B
  XMP claim)
- `scratch/recon-corpus/20260424T184450Z/irpf-2023/justificante.pdf`
  (5 pages, structurally identical to 2022)

CSV identifiers: `FNBB57PE9KZ5TN4R` (2021), `MZRSYDRL5JMPJPRT` (2022),
`TUD4V9XAUV7QJ8QV` (2023). Captures are byte-identical across rounds;
the AEAT-side state for these filings is stable.

### P3 — Justificante metadata parse

`done`. `aeat.domain.justificante.parse_justificante` extracts a valid
`Justificante` from each captured PDF. The 2021 legacy column-split
layout required a regex extension (`_PRESENTED_AT_ANNUAL_INVERTED_RE`,
`_NRC_IMPORTE_RE`) that landed in the discovery-driven rewrite
ahead of this audit; the 2022/2023 modern layouts parse against the
canonical regex set without further extension.

### P4 — Sanitise to fixture

`partially complete`. The sanitiser infrastructure (the
`pdf-sanitizer` sub-feature) is fully built: `aeat.adapters.inbound.sanitizer`
subpackage with strict-frozen pydantic v2 records, the 8-step
order-of-operations pipeline, the `aeat sanitize` CLI bridge with
all four verbs, and the three load-bearing security gates
(adversarial-absence, round-trip, no-write-surface). 120 unit
tests pass; lint + ty clean.

End-to-end pipeline validation against the 2022 IRPF capture:

- Source SHA-256: `98eb8c0da6350237…`
- Output SHA-256: `9cdb729fb55fa5cb…` (deterministic — re-running
  the sanitiser produces byte-identical output)
- Replacements applied: 19 (multiple occurrences of NIE, name,
  CSV, expediente id, NRC, presentation id, address, catastral
  reference, date of birth)
- `aeat sanitize verify` exits 0: no listed `real:` value occurs in
  the output bytes or decompressed content streams.

The fixture commit step is **not** complete. The sanitised PDF
still contains:

- ~80-86 individual monetary casilla values per declaration
  (income, expenses, tax credits, etc.) which my mapping does
  not currently enumerate.
- Free-text fields (employer name, activity descriptions) that
  may carry incidental PII.
- The catastral reference of Kent's residence (mapped) but not
  any other property references.

The `aeat sanitize verify` command only checks against values
listed in the mapping — anything not enumerated survives. To land
fixtures responsibly, the operator must review every page of the
sanitised PDF against the mapping and add missing entries until
no PII surface survives. That review is operator-bounded, not
autonomous-AI-bounded.

### P5 — Declaración deep parse

`done`. The `aeat.adapters.inbound.declaracion._parsers.modelo_100` extractor was
built during the prior discovery-driven rewrite and lands 83-86
casillas/year across the `2021.legacy`, `2022.modern`, and
`2023.modern` template revisions. Regression tests assert field
counts and known-value spot-checks for NIF, name, totals.

### P6 — Cumulation invariant

`na`. Modelo 100 is the consumer in every aggregator relationship
(100 ← 130 + 111 + 115 + 123). Cumulation invariants run only after
the input waves' P5 lands. None of those waves have been processed
yet.

### P7 — Live reconcile dry-run

`pending`. Requires (a) Cl@ve session active and (b) a synthetic
APPROVED `FilingDraft` built from a sanitised fixture. The fixture
work is gated on the same operator review that gates W1 P4 final
commit. Once a fixture lands, the live reconcile is a single
`aeat filing reconcile --modelo 100 --period 0A --ejercicio 2022`
invocation against the captured expediente.

### P8 — Write-guard re-verify

`done`. Per-subpackage `test_no_write_surface.py` covers
`aeat.adapters.outbound.aeat.sede`, `aeat.application.filing.reconciliation`, `aeat.entrypoints.cli.filing._reconcile`,
and the new `aeat.adapters.inbound.sanitizer` + `aeat.entrypoints.cli.sanitize`. No public symbol
in the new sanitiser surface carries a forbidden mutation verb
(`submit`, `send`, `commit`, `enviar`, `presentar`, `firmar`,
`radicar`, `remitir`, `modificar`, `anular`, `cancelar`, `rechazar`).
Apparent forbidden-verb call sites (`.<verb>(`) are absent.

### P9 — Vault audit record

This document. Status `partial` — the audit captures W1's current
end-state (sanitiser infrastructure ready; fixture commit pending
operator review) rather than declaring W1 closed.

## Findings

### Sanitiser infrastructure delivery

The `pdf-sanitizer` sub-feature (issue #239 sub-scope) ships:

- `src/aeat/adapters/inbound/sanitizer/` — package with 12 source files, 5 test
  files, 91 unit tests passing.
- `src/aeat/entrypoints/cli/sanitize/` — CLI bridge with 4 verbs (`pdf`,
  `prepare-map`, `verify`, `check`), 23 unit tests.
- `pyproject.toml` — adds `pikepdf>=10.0.0` as a hard runtime
  dependency.
- `.vault/research/2026-04-25-pdf-sanitizer-research.md`,
  `.vault/adr/2026-04-25-pdf-sanitizer-adr.md`,
  `.vault/plan/2026-04-25-pdf-sanitizer-plan.md` — full vaultspec
  triad locking the architecture.

The sub-feature plan reached P8 of 9; P9 (the integration-into-W1
step) is conditionally complete: pipeline runs end-to-end on a
real IRPF capture, but committing the fixture into git is gated
on operator-driven enumeration of every PII surface in each
declaration.

### Real-world end-to-end validation

The 2022 capture validation produced:

- 19 content-stream rewrite edits across the document body.
- Every named PII surface (NIE, name, CSV, expediente, NRC,
  presentation id, address, catastral reference, date of birth)
  removed from both the raw output bytes and the decompressed
  content streams.
- All eight DocInfo keys wiped (`Title`, `Subject`, `Author`,
  `Keywords`, `Creator`, `Producer`, `CreationDate`, `ModDate`).
- The XMP packet wholesale dropped along with its PDF/A-1B
  conformance claim.
- The OpenAction JS handler removed before the content rewrite.
- Determinism verified by re-running the sanitiser and asserting
  byte-equal output.

### Pre-existing parent-feature deliverables (still green)

The discovery-driven rewrite remains the load-bearing W1
infrastructure:

- `aeat.adapters.outbound.aeat.sede` walker (Expediente, JustificanteRef, SedeCapture,
  walk_expedientes_tree, capture_justificante, find_expediente,
  fetch_notifications_query, fetch_notifications_summary).
- `aeat.adapters.inbound.declaracion._parsers.modelo_100` deep extractor (83-86
  casillas/year, three template revisions).
- `aeat.application.filing.reconciliation` comparator with
  `FilingDivergenceKind` enum and `ReconciliationStatus` triad
  (MATCH / DIVERGENT / NOT_YET_FOUND).
- `aeat sede` and `aeat filing reconcile` CLI surfaces, both
  read-only on AEAT.

## Recommendations

### Immediate (W1 closure)

1. **Operator-driven mapping enumeration.** For each of the three
   IRPF captures, the operator runs `aeat sanitize prepare-map`,
   fills in the cleartext for every PII surface (including every
   monetary value, every free-text field, every catastral
   reference), then runs `aeat sanitize pdf` and
   `aeat sanitize verify` in sequence. Only when verify exits zero
   does the fixture commit.
2. **Update `aeat.adapters.inbound.sanitizer.fixtures.SANITIZED_SHAS`** with the
   SHA-256 of each committed sanitised PDF.
3. **Run W1 P7 live reconcile dry-run** once a fixture exists.
   `aeat filing reconcile --modelo 100 --period 0A --ejercicio
   2022` against the live (Cl@ve-authenticated) sede must return
   MATCH (the fixture's synthetic values are guaranteed to differ
   from the live values, but the *structural* parse should land
   on the same casilla shape — verify that the reconciliation
   correctly classifies the result).

### Cross-wave (the next round)

4. **Cross-wave P1 enumeration sweep.** `aeat sede list-expedientes
   --json` (no `--modelo` filter) against the live account so the
   plan's wave statuses can transition from `ready` to `running` /
   `na` based on actual data.
5. **W2 (Modelo 130) and W3 (Modelo 303) waves.** These are the
   highest-volume autónomo modelos and the inputs to W4 (390)
   and W6 (190) cumulation tests.

### Sanitiser improvements (lower priority)

6. **Mapping-template generator.** A per-modelo helper that emits
   a more comprehensive scaffold YAML pre-populated with every
   monetary-shaped string from the parsed declaration, leaving
   only the synthetic values to fill in. Reduces the operator
   burden in step (1) above without compromising verifiability.
7. **Fuzz the sanitiser against random PDFs.** Generate a corpus
   of synthetic PDFs with adversarial-shape content streams
   (multi-encoding mix, deeply-nested form fields, embedded
   thumbnails, complex StructTrees) and assert the sanitiser
   either succeeds or refuses cleanly, never silently leaks.

## Open issues

- **The 2021 legacy layout's monetary value extraction was not
  exercised by the validation run.** The 2022 capture was the only
  one taken end-to-end through the sanitiser. The 2021 layout
  uses `iText 2.1.4` and a different column shape; a full P9 run
  on the 2021 capture is needed to confirm the sanitiser handles
  literal-only Tj operands as well as the mixed literal+hex shape
  the 2022/2023 captures use.
- **The `aeat sanitize prepare-map` scaffold's `nif:` synthetic
  inherited the parser's `tax_id` field which sometimes contains
  the literal string `PRESENTADOR` rather than the actual NIE.**
  Operator must hand-correct this in every scaffold today; a
  parser-aware scaffolder upgrade is tracked under
  `Recommendations §6` above.
- **No live reconcile dry-run has been run against any sanitised
  fixture.** The P7 step is structurally ready but operationally
  pending.
