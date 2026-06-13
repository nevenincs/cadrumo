---
tags:
  - '#research'
  - '#aeat-verify'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-24-aeat-verify-research]]"
  - "[[2026-04-24-aeat-verify-reference]]"
  - "[[2026-04-25-aeat-verify-audit]]"
  - "[[2026-04-25-pdf-sanitizer-research]]"
  - "[[2026-04-25-pdf-sanitizer-adr]]"
  - "[[2026-04-25-pdf-sanitizer-plan]]"
---



# `aeat-verify` research: `modelo-pipeline-per-wave`

Light research note formalising the per-modelo verify pipeline observed
during the discovery-driven rewrite. The architectural decisions, the
captured ground truth, and the rewritten codebase are already captured
in the prior research, reference, and audit artefacts; this note's job
is to (a) name the per-modelo loop explicitly so it can be tracked in
the vaultspec pipeline as a recurring unit of work, (b) document the
aggregator-cumulation relationships that motivate phase 6 of the loop,
and (c) record the empirical observations that were not in the previous
research pass.

## Why this is research, not just plan execution

The prior research artefact described the discovery of the post-auth
sede surface for **one** modelo (Modelo 100, IRPF). Generalising that
finding to a per-modelo loop applied across the catalogue surfaces a
handful of architectural questions that are not pre-decided:

- The sanitisation surface (phase 4) requires PDF text-stream
  redaction, which the project has never done before. The
  technique, the tooling, and the failure modes are research items.
- The aggregator-cumulation phase (phase 6) introduces a cross-modelo
  invariant that needs a structural shape. Research finding: every
  Spanish tax aggregator we ship today is the **arithmetic sum** of
  its quarterly inputs, modulo published reconciliation rules — but
  there are exceptions worth documenting before locking the
  architecture.
- The empirical "which waves actually have data" question can only be
  answered by running phase 1 against the live account first;
  research identifies the enumeration sweep as a self-contained
  preflight.

## Empirical findings since the prior research pass

The 2026-04-24 capture round produced live ground truth for exactly
one modelo (Modelo 100). The 2026-04-25 recovery round (re-captured
after the worktree was restored) produced byte-identical PDFs for the
same three IRPF expedientes (Kent's 2021 / 2022 / 2023 returns), with
the same CSVs (`FNBB57PE9KZ5TN4R`, `MZRSYDRL5JMPJPRT`,
`TUD4V9XAUV7QJ8QV`). AEAT-side state for those filings is stable, so
the existing extractor regression suite has a stable golden corpus.

The reference document records the navigation graph + detail-page
shape; the prior research records the auth flow, the
DialogoRepresentacion handshake, the idle-TTL behaviour, and the
per-year endpoint pattern for IRPF. Those findings transfer to every
other modelo wave without re-research, because the sede walker is
modelo-agnostic on the listing side.

What is **not** transferred without further capture:

- The justificante-PDF body shape per modelo. Modelo 100's body
  parses against three template revisions (2021 legacy column-split,
  2022 modern, 2023 modern); other modelos have layouts we have not
  observed yet.
- The aggregator-cumulation invariants per (annual, quarterly inputs)
  pair. AEAT publishes the rules, but they are modelo-specific and
  not all reduce to a clean sum.

## Aggregator-cumulation map (preliminary)

Hypothesis tested by the plan's phase 6. The numerator-denominator
shape on each row should hold within `Decimal("0.01")` tolerance per
Kent-visible figure unless a published exception applies.

- **Modelo 100 (IRPF anual)** ← Modelos 130 (4× pagos fraccionados),
  111 (retenciones trabajo / actividades), 115 (retenciones
  inmuebles), 123 (retenciones capital mobiliario). Pagos fraccionados
  and retentions credit against final IRPF cuota.
- **Modelo 390 (IVA anual)** ← Modelo 303 (4× quarterly). Sum of
  trimestral IVA repercutido / soportado / cuota a ingresar with
  reconciliation lines for arrastres del año anterior.
- **Modelo 200 (Sociedades anual)** ← Modelo 202 (3× pagos
  fraccionados). Pre-paid IS deducted from final cuota.
- **Modelo 190 (Resumen anual retenciones trabajo / actividades)** ←
  Modelo 111 (4× quarterly). Sum of retentions practiced.
- **Modelo 180 (Resumen anual retenciones inmuebles)** ← Modelo 115
  (4× quarterly). Sum.
- **Modelo 193 (Resumen anual retenciones capital mobiliario)** ←
  Modelo 123 (4× quarterly). Sum.
- **Modelo 349 (operaciones intracomunitarias)** is itself an
  aggregator over the project's invoice catalogue, not over other
  modelos. Phase 6 for 349 reduces to "sum of intra-EU invoices".
- **Modelo 347 (operaciones con terceros)** likewise aggregates
  internal invoice data; no AEAT-side input.

Modelos that participate in **no** aggregator relationship and so have
phase 6 marked N/A: 036, 037 (census), 131 (alternative to 130, not
both filed), 232 (informativa anual on related-party operations), 369
(IVA OSS — separate VAT regime), 720 (foreign assets — informativa),
840 (IAE).

## Sanitisation strategy options

Phase 4 (PII strip on captured PDFs before committing as fixtures) is
the riskiest new code in the wave plan. Research alternatives:

- **Token replacement in PDF content streams** (pikepdf-based). Walks
  every content stream of the PDF, finds tokens matching configured
  PII regexes, replaces them in-place with deterministic synthetic
  values (e.g. a synthetic NIE canary -> `Y0000001S`, the named taxpayer ->
  `APELLIDO APELLIDO NOMBRE`, the NRC and CSV → fixture-stable
  placeholders). Preserves layout, font, page count. Failure mode:
  variable-width replacement (`9.876,54` → `1.000,00`) breaks visual
  alignment but not text extraction.
- **PDF re-render from parsed Justificante**. Take the parsed
  metadata + casilla map, regenerate a synthetic PDF using reportlab
  with the same field layout. Preserves no AEAT styling. Failure
  mode: every test that asserts against PDF text positions becomes
  brittle on the synthetic side.
- **Hybrid**. Token-replace for the Justificante metadata page;
  synthesise the body pages (where casilla extraction operates).
  Probably overkill for v1.

The plan locks token-replacement (option 1) as the v1 sanitiser. The
ADR captures the decision and lists the failure modes the
implementation must handle.

## Open questions parked in the plan, not the research

- Which modelos exist on Kent's account beyond Modelo 100 — answered
  by phase 1's enumeration sweep on first auth.
- Whether each captured PDF parses through the existing
  metadata-only justificante regex set — answered by phase 3's
  per-modelo run.
- Whether per-modelo deep extractors converge on a shared scanner
  shape (the way Modelo 100's three revisions share `_scanner.py`) or
  diverge per modelo family — answered empirically across waves 2-N.
- Whether published aggregator reconciliation rules have additive
  exceptions large enough to require a per-rule allowlist — open
  until live data lands.

## What the plan should NOT re-derive

These decisions live in the prior ADR and reference, and the plan
treats them as binding inputs:

- Read-only mandate, the five-layer write guard, and the structural
  marker `mode: Literal["read"]` on every boundary record.
- Sede walker public API (`walk_expedientes_tree`,
  `find_expediente`, `capture_justificante`,
  `fetch_notifications_query`, `fetch_notifications_summary`).
- Justificante / Declaración / FilingDraft / ReconciliationReport
  pydantic v2 strict-frozen records.
- Cl@ve-móvil as the sanctioned auth path with user-in-loop 2FA.
- Idle-TTL refresh via `aeat auth whoami` between long phases.
- Tests skip cleanly when `scratch/` captures are absent (CI-safe
  pattern).

## Inputs to the ADR

The ADR locks:

- The exact per-modelo phase list (P1-P9), each with one Kent-visible
  outcome and one skip rule.
- The wave ordering by Kent-impact (W1 already in flight, W2-W12
  blocked on enumeration outcomes).
- The sanitiser tooling choice (pikepdf token-replacement) and its
  fallback (skip the wave's commit-fixture step if sanitisation
  produces an unreadable PDF).
- The cumulation tolerance (`Decimal("0.01")`), shared with the
  existing reconciliation tolerance.
- The vault-record-per-wave discipline so each wave produces a
  discoverable audit doc.
