---
tags:
  - '#adr'
  - '#source-jurisdiction-axis'
date: '2026-05-27'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-m210-irnr-full-engine-adr]]"
  - "[[2026-05-27-dsl-conditional-predicate-adr]]"
  - '[[2026-05-28-source-jurisdiction-axis-research]]'
---
# `source-jurisdiction-axis` adr: `ledger source-jurisdiction axis` | (**status:** `accepted`)

## Problem Statement

Operator ledger rows carried no regulatory-source attribution. The
calculation engine could not distinguish Spanish-source from foreign-
source income or expense at the per-row level, which silently broke
three regulatory regimes simultaneously:

- LIRPF Art. 8 universal-base presumption for Spanish residents: the
  resident IRPF base must aggregate worldwide income; foreign-source
  rows had no provenance for audit even though they were entering the
  base.
- TRLIRNR Art. 13.1 / Art. 24 / Art. 25 for non-residents: Art. 13.1
  determines whether income is Spanish-source, Art. 24 supplies the
  M210 base, and Art. 25 supplies the applicable rate. The engine had
  no per-row signal to enforce that territorial scope at all.
- LIRPF Art. 93.5 for impatriados (Beckham regime): Spanish-source and
  foreign-source income are treated distinctly under the Art. 93
  régimen especial; with no per-row jurisdiction signal, a Beckham
  filer's foreign-source income would silently inflate the IRPF base.

The need surfaced through the persona-driven discovery wave covering
Pedro (intra-community supplier), Olivia (UK landlord crossing
resident/non-resident), Felipe (Argentina-resident pensioner under
TRLIRNR Art. 25.1.b), and Khadija (Morocco-resident worker under the
España–Marruecos convenio). No single-axis fix sufficed: the same
field was needed at create, persistence, projection, CLI, profile-aware
refusal, and aggregation. The campaign for this work
is anchored at the cross-domain-continuity remediation plan; this ADR
substitutes for a formal research artefact under that plan's open-
ended persona-driven discovery posture (the persona testimonials and
the round-6 audit batch are the research substrate).

## Considerations

ISO 3166-1 alpha-2 vs free-form country string. Alpha-2 was chosen:
the existing UE/EEE membership check in the renta-codes module
already enumerates a closed alpha-2 set; the IRNR Art. 25 rate split
between UE/EEE and third countries uses the same codes; ECB FX
rate lookups already consume alpha-3 currency codes derived from
alpha-2 country tokens. Free-form would have required a normaliser
at every read site and re-introduced the boundary-leak problem.

CLI-create-boundary gating vs aggregation-boundary gating. The
profile-aware refusal logic could have lived on
the calculation aggregation surfaces (one site per modelo engine that
consumes ledger rows). It instead lives at the CLI create surface, in
a single helper called before the persistence-bound command is
constructed. The three reasons that drove the decision are recorded
under Rationale.

Provenance-only vs filtering at the read surface. The M130 / M100
resident-IRPF aggregation could have filtered foreign-source rows
out of the base on read; that would have under-stated the resident-
IRPF base for every cross-border resident and contradicted the
LIRPF Art. 8 universal-base presumption. The read surface
propagates the per-row jurisdiction unchanged; downstream IRNR and
Beckham engines layer their own per-row filters when authored.

Source jurisdiction is required evidence for jurisdiction-sensitive
calculations. The encrypted catalogue boundary validates the current strict
model and does not infer Spain, accept a missing value as historical truth, or
carry a pre-axis read path.

## Constraints

The current encrypted catalogue contract requires an explicit ISO 3166-1
alpha-2 source jurisdiction wherever the row participates in
jurisdiction-sensitive calculation. Missing evidence is surfaced for operator
resolution; it is never silently defaulted to Spain.

Refusal text reaching the operator surface must route through `tr()`
per the locale gate. Two refusal keys, one per regulatory branch
(IRNR and Beckham), were authored via the locale CLI scaffold cycle
across the four supported locales — never via direct yml edits.

The field validator must not couple to profile state. The
2-character alpha uppercase rule is intrinsic to the field and lives
on each strict-frozen pydantic model that exposes it. The profile-
aware refusal lives on a separate helper that
the CLI create boundary calls; the model-level validator never reads
profile state.

Test discipline: every test must derive its expected outcome from a
regulatory anchor (Art. 8, Art. 25, Art. 93.5, Art. 2, Art. 10),
never from re-running the resolver or aggregation helper to produce
its own expectations. This is the standing G6 anti-tautology gate.

## Implementation

The axis was decomposed into six sequential Step leaves. Each leaf
landed as a separate commit. The chain is:

- S381 at `b7c571297` — domain field on `Transaction`, read projection
  field on `LedgerTransactionPayload`, and anti-tautology tests for explicit
  jurisdiction roundtrip, malformed rejection, and whitespace normalisation.
- S382 at `40f3837b8` — encrypted-envelope persistence roundtrip with strict
  missing-evidence refusal. The field is propagated to
  `LedgerTransactionReviewPayload` and `LedgerExportRow`; no empty-string or
  `None` compatibility representation is authoritative.
- S383 at `d75202aab` and locale companion at `5cbd8e1c4` — write-
  side boundary closure: added the field to
  `ManualLedgerTransactionCommand` and `ManualLedgerTransactionPatch`,
  threaded `command.source_jurisdiction` through
  `_transaction_from_command`, added the `--source-jurisdiction`
  typer option on `aeat app ledger add` with `tr()`-routed help
  text, scaffolded the help-text locale across en / es / ca / hu.
- S384 at `c6e402eb3` + locale at `5a7601f89` + four patches at
  `ef3562e64` (read-projection wire), `3f7427714` (descriptor key),
  `f6c8d1028` (IRNR axis tuple), `3802591f6` (UE country
  workaround) — profile-aware refusal helper
  `_resolve_source_jurisdiction` plus four truth-table CLI
  integration tests covering the regulatory branching.
- S385a at `0a153a83c` — provenance pass-through to
  `RentaIncomeObservation` so M130 / M100 carry the per-row
  jurisdiction onto the casilla observation; two anti-tautology
  tests prove ES preservation and Art. 8 universal-base mixing
  (ES + FR both enter casilla 01).
- S386 (this document) — design consolidation.

The CLI create boundary calls the resolver immediately before the
command is constructed:

- operator value present: return verbatim (after the model-level
  validator trims and case-folds).
- `fiscal_residency` equal to `NON_RESIDENT_IRNR`: refuse with the
  IRNR-anchored `tr()` key.
- `irpf_special_regime` equal to `IMPATRIADO`: refuse with the
  Beckham-anchored `tr()` key.
- otherwise: require the operator value. Residence determines calculation
  scope, not the provenance of a particular ledger row, so it cannot justify
  manufacturing `"ES"`.

The aggregation surface (M130 / M100 income side) propagates the
field from the originating transaction to the observation; it does
not gate. The M210 IRNR ledger projection now reads the field directly
and admits only Spanish-source income under Art. 13.1, with Art. 24 as
the base authority and Art. 25 as the rate authority. Its persisted
classification, selected source mode, ledger evidence, and typed
exclusion reasons retain this decision at the filing boundary. The
M151 Beckham engine remains a separately deferred cross-domain-
continuity task.

## Rationale

CLI-create-boundary gating was preferred over per-modelo
aggregation gating for three reasons:

1. The error surfaces before the row reaches the encrypted
   catalogue. The operator gets an immediate refusal instead of a
   row that persists silently and later raises an aggregation issue
   at calculate time.
2. The refusal is operator-facing prose routed through `tr()`. A
   per-modelo aggregation gate would have produced a per-modelo
   issue surface, deferring the error and making the connection
   between the operator's input and the regulatory cause harder to
   trace.
3. Single-point-of-enforcement vs N-fold duplication. A gate at the
   create boundary applies to every persistence path. A per-modelo
   aggregation gate would have to be repeated for every modelo that
   consumes ledger rows, with the same regulatory rationale and the
   same risk of drift between sites.

The profile-aware refusal table at the create boundary follows the regulatory
branching directly. Art. 8 requires worldwide-income aggregation for a
resident but does not prove that any individual row is Spanish-source. Art. 93.5
also requires refusal for the impatriado case (the regime treats
Spanish-source and foreign-source income distinctly, so a silent ES
default would mask foreign-source income in the IRPF base). Art. 2
and Art. 10 produce the refusal for the non-resident case (the IRNR
base only admits Spanish-source, so the per-row jurisdiction must
be declared explicitly to support the scope filter that the future
IRNR engine will apply).

The aggregation surface honours Art. 8 by accepting all source
jurisdictions into the resident-IRPF base. A future "clean-up"
refactor that removes foreign-source rows from the resident-IRPF
aggregation would silently under-state every cross-border resident's
base; the second anti-tautology test in the aggregation suite was
written specifically to fail loudly against that mutation.

The model-level validator is intrinsic and stateless. Coupling the
2-character alpha rule to profile state at the model layer would
have re-introduced the cycle that the helper-at-the-CLI design
breaks. The model validator is the same on every payload type that
carries the field; the helper is the only profile-aware code.

## Consequences

The CLI now refuses ledger add for non-resident IRNR and impatriado
profiles when the operator omits `--source-jurisdiction`. This is
the intended outcome but it changes the operator flow for those
profiles. The refusal text routes the operator to declare the
jurisdiction explicitly and anchors the requirement in regulatory
text via the `tr()` key.

Per-row gating at the IRNR M210 aggregation surface is complete for
the deferred S385b / cross-domain-continuity task #62: the selected
ledger source rejects foreign and unresolved jurisdictions with typed
diagnostics and persists the admitted source evidence. The M151
Beckham engine remains a Path-B refusal stub and a separately deferred
follow-up; its future gating must not be inferred from this M210
closure. The CLI create-boundary refusal prevents every filer from silently
adopting an unsupported ES provenance value.

Test-fixture discipline for non-resident profiles is now non-
trivial. The S384 truth-table tests revealed a three-bug smoke
sequence (a missing read-side projection wire, a wrong descriptor
key path, and a partial IRNR axis tuple) that future M210 and
Beckham fixture authors will hit unless they follow the pattern of
provisioning the full residency / country / representante tuple via
the diagnostics-app descriptor setter. The S384 fixture preserves
the recipe in inline comments.

A schema-catalogue mismatch on `representante_fiscal_nombre` was
discovered while authoring the S384 non-resident fixture: the
wizard catalogue, the projection layer, and the pydantic model all
reference the field, but the schema descriptor TOML does not expose
it as a `profile set`-able key. The S384 fixture uses a UE country
to dodge the representante coupling; the schema-gap is filed as a
separate follow-up task and is independently resolved.

The Transaction model and its persistence boundary carry an ISO-coded
axis that downstream calculation paths can rely on without
re-validating the field shape. The M210 IRNR engine delivered by
`8f5f690ed0` reads the field from the typed observation and records it
in the ledger filing evidence; its implementation and locale
verification close the M210 portion of task #62 only. The Beckham
engine will use the same axis when its separate follow-up is delivered,
without retrofitting the read-side provenance path.
