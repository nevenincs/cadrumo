---
tags:
  - '#adr'
  - '#aeat-verify'
date: '2026-04-25'
modified: '2026-07-17'
body_hash: 'sha256:6afaf8ec97344a901f8a5357fff50ff5cf47a46befabe1d0d2d442384de34a2f'
related:
  - "[[2026-04-24-aeat-verify-adr]]"
  - "[[2026-04-24-aeat-verify-reference]]"
  - "[[2026-04-25-aeat-verify-audit]]"
  - "[[2026-04-25-aeat-verify-research]]"
  - "[[2026-04-25-pdf-sanitizer-research]]"
  - "[[2026-04-25-pdf-sanitizer-adr]]"
  - "[[2026-04-25-pdf-sanitizer-plan]]"
---

# `aeat-verify` adr: `modelo-pipeline-waves-and-phases` | (**status:** `accepted`)

## Problem Statement

The discovery-driven rewrite (the prior ADR) shipped a complete read
surface for AEAT (sede walker, justificante parser, reconciliation
comparator) and one fully verified modelo (Modelo 100, IRPF). The
rewrite did **not** define a repeatable per-modelo loop for moving
each remaining catalogued modelo from "infrastructure-ready" to
"end-to-end live-verified, fixture-backed, cumulation-checked".
Without that loop, every additional modelo becomes ad-hoc work with
no shared discipline. We need a binding decision on the loop's
shape, the wave ordering, and the gates that make a wave "done".

## Considerations

- The previous ADR locked the read-only mandate, the five-layer
  write guard, the strict-frozen pydantic v2 boundary records, and
  the Cl@ve-móvil sanctioned auth path. This ADR inherits all of
  them; it does not re-decide them.
- Live ground truth varies per account. Kent's snapshot held only
  Modelo 100 + a single IVA regularización; other accounts will
  carry different sets. The loop needs an "is-applicable-here?"
  gate up front so inapplicable waves stop with explicit evidence rather than
  being counted as verification.
- Aggregator-cumulation invariants (Modelo 390 ← 4× 303, Modelo 100
  ← 4× 130 + retentions, etc.) are not optional checks; they are
  load-bearing for "Kent can prove his exported numbers match
  AEAT's record" because the aggregator is what AEAT acts on.
- Real PDFs cannot enter git history. CI must run without
  `scratch/` captures present.
- Sanitisation of a real AEAT PDF before committing as a fixture is
  PDF text-stream rewriting, which the project has not done before.

## Constraints

Inherited and explicitly re-affirmed:

- **Zero writes to AEAT.** Every navigation goes through `cadrumo.adapters.outbound.aeat.sede`
  whose grep guard bans `submit/send/commit/POST/enviar/presentar/
  firmar/radicar/remitir/modificar/anular/cancelar/rechazar`. No
  exceptions per wave; the guard runs unchanged.
- **Strict-frozen pydantic v2** records, `mode: Literal["read"]`
  marker on every boundary record, `extra="forbid"`, `StrEnum` for
  closed enumerations.
- **Real live boundaries.** Cl@ve-móvil's 2FA is the sole
  human-in-the-loop. Live verification is absent from the default offline
  selection unless `CADRUMO_LIVE_TESTS_ENABLED=1`; once enabled, boundary
  failures fail the run.
- **Committed evidence only.** CI tests consume committed, sanitised,
  provenance-declared fixtures. Ephemeral `scratch/` captures are discovery
  inputs and their absence cannot turn a test into an ignored result.
- **One commit per phase per wave.** Each commit is small enough
  that a code review can land or revert it standalone.

## Implementation

### The per-modelo loop (nine phases)

Each wave executes phases in order. A phase either passes, is explicitly
not applicable with evidence, or fails. Failure stops the wave; a
not-applicable result proves only applicability, never verification.

- **P1 - Discover.** Run `aeat sede list-expedientes --modelo <N>`
  for the wave's modelo. Output: a tuple of `Expediente` records,
  empty or non-empty. **Applicability rule**: empty → wave is "not
  applicable to this account"; mark in the audit record and stop.
- **P2 - Capture.** For each expediente, call
  `cadrumo.adapters.outbound.aeat.sede.capture_justificante`. Output: raw PDF bytes +
  sha256 + the expediente detail HTML, written to
  `scratch/sede-discovery/<utc-timestamp>/<modelo>/<expediente_id>/`.
  **Applicability rule**: P1 was empty.
- **P3 - Justificante metadata parse.** Run
  `cadrumo.domain.justificante.parse_justificante` on every captured PDF.
  Output: a parsed `Justificante` per capture. **Applicability rule**:
  P2 produced no PDFs. **Failure mode**: parser misses a field
  → land regex extension under `cadrumo.domain.justificante._extract`,
  retry. Loop until green.
- **P4 - Sanitise to fixture.** For every captured PDF, run the
  per-wave sanitiser to strip PII. Output: a fixture PDF + its
  parsed-Justificante sidecar JSON committed under
  `tests/fixtures/justificantes/<modelo>/<year>-<period>.pdf`.
  Sanitisation must produce a parseable, PII-free PDF and matching sidecar.
  Failure is recorded and blocks the fixture-backed verification claim; a
  metadata-only record is not a substitute for the PDF behavior under test.
- **P5 - Declaración deep parse.** Build or extend a per-modelo
  body extractor under `cadrumo.adapters.inbound.declaracion._parsers/<modelo>/`.
  Output: a strict-typed casilla map per fixture, with regression
  tests asserting field counts and known-value spot-checks.
  **Applicability rule**: a genuinely metadata-only modelo is marked N/A with
  source evidence and continues without claiming a deep-body parse.
- **P6 - Cumulation invariant.** For aggregator modelos, sum the
  inputs and compare to the aggregator's published figures
  within `Decimal("0.01")` tolerance. Output: an integration
  test that exercises the relationship. If the aggregator inputs are not yet
  fixtured, the phase remains pending and the wave is not complete.
- **P7 - Live reconcile dry-run.** Build a synthetic APPROVED
  `FilingDraft` from the sanitised fixture's casilla values
  using the existing `cadrumo.application.filing.testing` helpers. Run
  `aeat filing reconcile --last` against live AEAT (which the
  wave already authenticated). Assert MATCH. Output: one live
  test marked `@pytest.mark.live` per wave. An expired Cl@ve session is
  re-authenticated through the same flow and retried; a repeated failure fails
  the phase.
- **P8 - Write-guard re-verify.** Per-subpackage
  `test_no_write_surface.py` plus a global grep across new files
  introduced by the wave. **Always runs.**
- **P9 - Vault audit record.** One audit doc per wave at
  `.vault/audit/2026-MM-DD-modelo-<N>-pipeline-audit.md`.
  Captures the per-phase outcome, the captured ground truth, the
  extractor coverage, the cumulation findings, the live-reconcile
  verdict, and any open issues for follow-up. **Always runs**;
  even an empty wave produces an audit record marking it N/A.

### Wave ordering

Run **P1** first across **all** waves to enumerate what exists on
the live account before deepening any single wave. Then proceed in
dependency order. Aggregator waves wait until their input waves'
P5 has landed.

The plan artefact carries the full table; the ADR locks the
**dependency rule**: an aggregator wave's P6 must not run until
every input wave has shipped P5 (or marked it N/A).

### Sanitiser

The v1 sanitiser is a `pikepdf`-based PDF content-stream rewriter
that walks every page's content stream and replaces tokens
matching a configurable PII regex set. Token mapping is fixed:

- Real NIF / NIE → `Y0000001Z`
- Real taxpayer name → `APELLIDO APELLIDO NOMBRE`
- Real expediente sequence → `9999...` keeping the year prefix +
  checksum letter so shape validation still passes
- Real CSV → `SANITIZED<modelo><period>` (deterministic per fixture)
- Real NRC → `0000000000000XXXXXXX`
- Real `IMPORTE` (cash amounts) → `1.000,00` (synthetic but
  shape-preserving)
- Real address → `CALLE CALLE 0 0 CIUDAD (PROVINCIA)`

PDF metadata `Title` is scrubbed so `pdf.metadata.get("Title")`
returns the synthetic CSV. The sanitiser is a deterministic pure
function of `(real_pdf_bytes, mapping)` for reproducibility.

**Failure mode:** if pikepdf cannot rewrite the content stream
without producing a parseable, PII-free PDF (for example, because an embedded
font lacks the replacement glyphs), P4 fails. The audit records the evidence
and the wave remains incomplete until a source-faithful sanitisation strategy
is implemented.

### Cumulation tolerance

`Decimal("0.01")` per Kent-visible figure, the same tolerance the
existing reconciliation comparator uses. Imported as
`cadrumo.application.filing.reconciliation.RECONCILIATION_TOLERANCE` (or the
local `_TOLERANCE` constant; the ADR is indifferent so long as
the value is one-cent and shared).

### Vault discipline

- The plan artefact tracks each wave as a numbered entry. Phase
  status (`done`, `not_applicable`, `pending`, `failed`) is updated in
  the plan as work progresses; the source of truth for "what's
  been done" is the plan plus the wave's audit doc.
- The audit doc per wave is mandatory even for empty waves. The
  audit's job is to make N/A states discoverable so the next
  capture round (when Kent files a new modelo) doesn't re-run
  enumeration unnecessarily.
- An exec record per wave captures the concrete files touched +
  the commit SHAs that landed each phase.

## Rationale

- **Why nine phases not three.** A coarser loop conflates
  capture, parse, sanitise, and verify, hiding which step
  actually broke when a wave regresses. Each phase has its own
  pass/not-applicable/fail criterion so failures route to the right code
  surface (regex set, extractor, sanitiser, reconciler).
- **Why P1 first across all waves.** Live AEAT enumeration is the
  cheapest way to learn which waves have data. Running P1
  upfront avoids investing P5 effort on a modelo Kent never
  filed; it also reveals modelos we did not know to expect.
- **Why one commit per phase.** Smaller commits are easier to
  revert when a sanitiser bug or extractor regression surfaces;
  the audit record can cite a specific SHA rather than "the
  wave landed somewhere in this batch".
- **Why pikepdf token-replacement and not synthetic re-render.**
  Re-rendering loses every layout cue the deep extractor relies
  on. Token replacement preserves AEAT's exact column layout so
  the extractor exercised against a sanitised fixture is
  exercised against the same shape AEAT produces live.
- **Why the cumulation phase is mandatory.** "Kent can prove his
  exported numbers match AEAT's record" is not credible if Kent's
  Modelo 100 ends up at €X but his four 130 quarterly filings
  sum to €Y where X ≠ Y - retentions. The aggregator invariant
  is the integration test for the entire produce-verify-export
  triad.

## Consequences

- The codebase grows by approximately one extractor module +
  one sanitiser invocation + one cumulation test per wave. None
  of these touch the live-write surface; the existing write guard
  scales unchanged.
- Each wave needs at least one Cl@ve 2FA push (P1's enumeration
  burn). Long waves (P2-P7) consume one session; the
  `aeat auth whoami` keep-alive pattern resets the idle TTL.
- Empty waves (modelos Kent has not filed) still cost the P1
  enumeration plus the P9 audit record. That is acceptable
  because the audit doc supplies applicability evidence to the next capture
  round without claiming the modelo has been verified.
- The plan and audit docs become the canonical place to look up
  "which modelos are end-to-end verified today". The README and
  CHANGELOG are not authoritative; the vault is.
- The sanitiser is the highest-risk new module. Its output must remain
  source-faithful, parseable, and free of PII; failure blocks fixture-backed
  verification instead of weakening the evidence contract.
