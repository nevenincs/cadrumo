---
tags:
  - '#plan'
  - '#aeat-verify'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-aeat-verify-adr]]"
  - "[[2026-04-25-aeat-verify-research]]"
  - "[[2026-04-25-aeat-verify-audit]]"
  - "[[2026-04-24-aeat-verify-reference]]"
  - "[[2026-04-25-pdf-sanitizer-research]]"
  - "[[2026-04-25-pdf-sanitizer-adr]]"
  - "[[2026-04-25-pdf-sanitizer-plan]]"
---



# `aeat-verify` `per-modelo-justificante-pipeline` plan

Wave-by-wave execution plan for the per-modelo verify loop. Inherits
the architectural decisions from the ADR and the discovered ground
truth from the prior research / reference / audit artefacts. The
plan is the source of truth for "which wave is in flight" — phase
status is updated in this document as commits land.

## Status legend

- `ready` — wave can start; no upstream dependency blocks it
- `running` — at least one phase landed but the wave is incomplete
- `done` — every phase ran to completion (or marked N/A with reason)
- `blocked` — waiting on an upstream wave's phase 5 (cumulation
  inputs)
- `na` — empty after P1 enumeration; no AEAT data on this account

Per-phase legend:

- `done`, `skipped(reason)`, `pending`, `failed(reason)`

## Cross-cutting prerequisites

These run once at the start of every authenticated session, not per
wave:

- **PR0** - Cl@ve session active. `uv run aeat auth status` confirms
  identity + remaining TTL. If expired, `uv run aeat auth login
  --provider clave_movil` triggers a 2FA push (the only sanctioned
  human touchpoint).
- **PR1** - Live env populated. `env/.env` carries
  `AEAT_LIVE_TESTS_ENABLED=true` and the NIE / soporte. Restored
  from `feature-285-auth-cli` if missing.
- **PR2** - Sanitiser tooling. **Superseded** by the standalone
  `pdf-sanitizer` sub-feature (its own research / ADR / plan
  triad — see `related:` above). The sanitiser is no longer a
  loose `scripts/` helper; it is the `aeat.adapters.inbound.sanitizer` subpackage
  with strict-frozen pydantic v2 records, an `aeat sanitize` CLI
  bridge, an adversarial-absence test, and a determinism contract.
  PR2 here means "the sub-feature's plan has reached at least
  phase 6 (orchestrator) so this loop can call `aeat sanitize pdf`
  against captured PDFs". Tracked in
  `2026-04-25-pdf-sanitizer-plan`.

## Pre-wave: enumeration sweep

Before running deep phases on any individual wave, do one
across-the-board P1 to learn which modelos exist on the account.

- `aeat sede list-expedientes --json` (no `--modelo` filter) →
  full account corpus.
- For each unique modelo seen, the corresponding wave moves from
  `ready` to `running`. Modelos in the catalogue with zero rows
  move to `na`.
- Record the enumeration result as the first audit-doc entry of
  the round.

Cost: one Cl@ve session (~17 min budget); the sweep is fast — under
a minute end-to-end against Kent's account.

### Result (2026-04-25, redacted operator NIE)

**Partial — walker covers wrong surface for this question.**

Ran `aeat sede list-expedientes --json`; 36 entries returned.
Distribution:

- 3 Modelo 100 (IRPF anual): `202110013520233F` (2021),
  `202210013522538B` (2022), `202310013522456T` (2023).
  Already captured under
  `scratch/recon-corpus/20260424T184450Z/`.
- 1 candidate Modelo 390: `202239013520267Q` (2022).
- 1 candidate Modelo 190: `2024190000000000494658` (2024).
- 28 RSC + 3 GRC entries — AEAT-side proceedings, not Kent-
  filed declarations.

Crucially, the listing **does not include** the routine
quarterly modelos (130, 303) and informativas (347, 390) that a
direct-estimación autónomo enrolled per the 036 census file
every year. The user (redacted NIE) confirmed this on
2026-04-25: as a direct-estimación autónomo he files the usual
IRPF + IVA quarterly + annual forms plus retentions /
informativas; only filings outside his 036 census enrolment
should be missing.

### Walker coverage gap

The `aeat.adapters.outbound.aeat.sede` walker walks `Mis Expedientes` at
`/wlpl/TEWV-CORE/ResumenVlt`. That surface lists *procedures*
(rectificaciones, sancionadores, gestión recaudación, plus the
per-year IRPF detail entries for Renta Web filings) — not the
full *declaraciones presentadas* register.

The full filings register lives at
`/wlpl/SCEJ-MANT/CONSUL/index.zul?MODELO=…&EJERCICIO=…
&NIFOBLIGADO=…` ("Consultar declaraciones presentadas"),
discoverable from the `Mis Expedientes` landing page's left-nav
links. The endpoint loads but is built on the ZK framework with
dynamically-assigned input ids (`c5uX...`) and a `Buscar` button
that issues the AJAX query — URL parameters alone do not drive
results.

A live HTML capture of the form is stored at
`scratch/sanitizer-validation/declaraciones-presentadas.html`
for offline analysis.

### Follow-up: walker enhancement (out of pdf-sanitizer scope)

A new feature is needed:

- Extend `aeat.adapters.outbound.aeat.sede` (or a new `aeat.adapters.outbound.aeat.sede._declarations` module)
  with a `walk_declarations_register(session, *, modelo: str |
  None = None, ejercicio: int | None = None) -> tuple[
  Declaration, ...]` helper that drives the ZK form via stable-
  selector clicks (the form has labelled inputs and a labelled
  `Buscar` button — selectors should bind on labels not on the
  ZK-generated ids).
- Per-modelo loops that follow this plan should call the new
  helper, not `walk_expedientes_tree`. The two surfaces are
  complementary, not redundant.

Until that lands, every wave's P1 status outside W1 (Modelo
100) is **unknown** rather than `na`. The 2026-04-25 wave-status
update below is the best-available hypothesis based on the
expediente-tree walk; the actual filings register will overwrite
it once the new walker is built.

### 2026-04-25 wave hypothesis (subject to revision)

- W1 (100): `running`. Three IRPF anual filings confirmed.
- W2 (130 IRPF fraccionado), W3 (303 IVA quarterly), W10 (347
  informativa anual): hypothesis `running`. Standard autónomo
  filing shape; not yet observable on the expediente tree but
  expected to surface via the declaraciones register.
- W4 (390 IVA anual): hypothesis `running`. One candidate ID
  observed.
- W5 (111), W7 (115/180), W8 (123/193), W6 (190/180/193): only
  applicable if Kent withholds — pending confirmation via the
  declaraciones register.
- W9 (131/202/200 sociedades), W11 (369/720/232/840): `na` —
  outside Kent's 036 census enrolment per his 2026-04-25
  confirmation.

## Wave list

Each row is a wave. Per-phase status updates land here as commits
push. The "audit doc" column points at the wave-specific audit
record (created when the wave starts, even if it ends `na`).

### W1 — Modelo 100 (IRPF anual)

- Status: `running`
- Audit doc: `.vault/audit/2026-04-25-modelo-100-pipeline-audit.md`
  (to be created when W1 P9 runs).
- P1 - **done**. Three expedientes captured (2021, 2022, 2023).
- P2 - **done**. Raw PDFs at the captured paths.
- P3 - **done**. Justificante metadata extracts cleanly across all
  three template revisions.
- P4 - **partial**. The `pdf-sanitizer` sub-feature is fully
  built (P1-P8 of its own plan: 91 sanitizer tests + 23 CLI tests,
  120 total green). End-to-end pipeline validated against the
  2022 IRPF capture in `scratch/sanitizer-validation/`: 19
  content-stream rewrite edits, 9 mapping entries verified, zero
  leaks, deterministic byte-equal output across runs. Committing
  fixtures into `tests/fixtures/justificantes/100/` is operator-
  gated on enumerating every Modelo-100 monetary casilla and free-
  text field in the per-capture mapping (~80 entries per
  declaration). See `2026-04-26-aeat-verify-audit` for the full
  status breakdown.
- P5 - **done**. Modelo 100 extractor lands 83-86 casillas/year
  across `2021.legacy` / `2022.modern` / `2023.modern` revisions.
- P6 - **na**. Modelo 100 is the consumer of 130/111/115/123;
  cumulation against IT runs only after those waves' P5 lands.
- P7 - **pending**. Live reconcile dry-run against any of Kent's
  three IRPF expedientes. Requires a synthetic APPROVED FilingDraft
  built from a sanitised fixture (so depends on P4).
- P8 - **done** (existing write-guard tests cover the surface).
- P9 - **pending**. Audit doc to be filled when P4 + P7 close.

### W2 — Modelo 130 (IRPF fraccionado, quarterly)

- Status: hypothesis `running`. Direct-estimación autónomos
  file Modelo 130 quarterly. The expediente-tree walk did not
  surface them, but the user's 2026-04-25 confirmation places
  this in scope. Awaiting the declaraciones-register walker
  (see "Walker coverage gap" above) before P1 can close.

### W3 — Modelo 303 (IVA quarterly)

- Status: hypothesis `running`. Same situation as W2.
  Standard autónomo IVA flow; expected via the declaraciones
  register.

### W4 — Modelo 390 (IVA anual)

- Status: `running` (single expediente). P1 surfaced
  `202239013520267Q` (2022 ejercicio) which matches the
  `<year>-390-1-<seq>` Modelo 390 expediente shape. Detail URL is
  a `TEWV-CORE/DetalleVlt` page rather than the per-year
  `DASR-CORE/AccesoDR<YYYY>RVlt?exp=...` shape that IRPF uses, so
  the capture flow needs verification. P6 cumulation is moot —
  W3 (303) returned `na`, so no quarterly inputs to sum against.

### W5 — Modelo 111 (retenciones trabajo, quarterly)

- Status: hypothesis `pending`. Only applicable if Kent
  withholds (paying employees / IRPF-eligible contractors). User
  has not confirmed; awaiting the declaraciones-register walker
  + per-NIF inspection.

### W6 — Modelo 190 (resumen anual retenciones, anual aggregator)

- Status: candidate `running`. P1 surfaced
  `2024190000000000494658` (22-char id, 2024 ejercicio) which may
  be a Modelo 190 informativa. Confirmation pending capture-by-id
  CLI command + per-modelo binding via the declaraciones register.

### W7 — Modelo 115 + 180

- Status: hypothesis `pending`. Only applicable if Kent has
  rented premises (115 quarterly retentions on rent paid).

### W8 — Modelo 123 + 193

- Status: hypothesis `pending`. Only applicable for retentions
  on capital mobiliario.

### W9 — Modelo 131, 202, 200 (sociedades)

- Status: `na` per user 2026-04-25 confirmation. Sociedades
  forms are outside the 036 census enrolment for an individual
  autónomo.

### W10 — Modelo 347 + 349 (informativas)

- Status: hypothesis `running` for 347 (operations with third
  parties >€3005.06 — most autónomos file this annual
  informativa). 349 (intra-EU operations) hypothesis `pending`
  on whether Kent has intra-EU activity.

### W11 — Modelo 369 (IVA OSS), 720 (extranjero), 232 (vinculadas), 840 (IAE)

- Status: `na` per user 2026-04-25 confirmation. Niche filings
  outside the standard autónomo set.

### W12 — Modelo 036 / 037 (censal)

- Status: `na` by design. Census forms live on a different sede
  surface (`Mantenimiento de datos censales`), not the
  `Mis Expedientes` tree. Out of the justificante pipeline; the
  audit record marks the boundary explicitly.

## Tasks

### Phase 1 (cross-wave) — Enumerate the account

1. Authenticate Cl@ve.
2. Run `uv run aeat sede list-expedientes --json` once with no
   `--modelo` filter.
3. Bin the rows by `modelo`, build the empty / non-empty map.
4. For each `na` modelo: scaffold its audit doc with status `na`
   and the empty enumeration as evidence.
5. Update this plan's wave statuses (`ready` → `running` /
   `na` / `blocked`).
6. Commit: `chore(audit): record enumeration sweep across all
   modelos (#239)`.

### Phase 2 (per wave) — Capture

For each non-empty wave:

1. `uv run aeat sede discover --modelo <N>` writes raw PDFs +
   discovery report under
   `scratch/sede-discovery/<utc-ts>/<N>/`.
2. Verify each PDF is non-empty + content-type was `application/pdf`
   (the discover report records this).
3. Spot-parse one PDF with `aeat.domain.justificante.parse_justificante`.
   If parse fails, P3 is the next phase rather than P4.
4. No commit yet — captures live in `scratch/`, gitignored.

### Phase 3 (per wave) — Justificante regex extension

For each modelo whose PDF the existing parser misses:

1. Inspect the failing field via `pdfplumber` text dump.
2. Extend the regex set in `aeat.domain.justificante._extract`
   (e.g. annual-modelo presented_at variants, NRC line variations).
3. Add a unit test exercising the extension against the captured
   PDF.
4. Commit: `feat(justificante): parse modelo <N> <variant>
   layout (#239)`.

### Phase 4 (per wave) — Sanitise to fixture

This phase delegates to the `pdf-sanitizer` sub-feature. Its plan
owns the sanitiser implementation; this loop only consumes the
public API.

1. Operator scaffolds a per-capture mapping:
   `aeat sanitize prepare-map <captured-pdf> --output
   scratch/<...>/sanitizer-mapping-<modelo>-<period>.yaml`. The
   YAML carries `synthetic:` pre-filled and `real:` blank.
   Operator fills in cleartext locally; the YAML stays gitignored.
2. Run the sanitiser against each captured PDF for the wave:
   `aeat sanitize pdf <captured-pdf> --mapping <yaml> --output
   tests/fixtures/justificantes/<modelo>/<year>-<period>.pdf
   --report tests/fixtures/justificantes/<modelo>/<year>-<period>.json`.
3. Verify the sanitised PDF still parses through
   `aeat.domain.justificante.parse_justificante` and produces the
   synthetic NIF / name / CSV / NRC / IMPORTE values
   (`aeat sanitize check` runs both checks).
4. Run `aeat sanitize verify <fixture-pdf> --against <yaml>`. Must
   exit zero; non-zero means a `real:` value leaked into the
   sanitised output and the fixture must NOT be committed.
5. Append the fixture's SHA-256 to
   `aeat.adapters.inbound.sanitizer.fixtures.SANITIZED_SHAS` so future
   re-sanitisation attempts hit `AlreadySanitizedError`.
6. Commit: `chore(fixtures): sanitised modelo <N> <year>-<period>
   justificante (#239)`. Per-capture mapping YAML stays gitignored.

If the wave's PDF layout exposes a token-replace edge case the
sub-feature's `_streams.py` does not yet handle (e.g. cleartext
spanning multiple `Tj` operands, an unobserved encoding), file a
follow-up phase against the sub-feature's plan rather than building
ad-hoc handling here.

### Phase 5 (per wave) — Declaración deep parse

For modelos whose PDFs carry a body beyond the metadata page:

1. Add a new package under
   `src/aeat/adapters/inbound/declaracion/_parsers/<modelo>/` mirroring the Modelo
   100 layout: `_scanner.py` (per-page text scan +
   value-typing), `_extractor.py` (per-template-revision driver),
   `__init__.py`, `test_extractor.py`.
2. Register the new template revisions in
   `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`.
3. Tests assert: ≥N casillas extracted (N >= the page-count *
   approximate-rows-per-page floor), every casilla typed
   correctly (`Decimal | int | str | date`), spot-checks for
   well-known casilla IDs (NIF, name, totals).
4. Commit: `feat(declaracion): modelo <N> casilla extractor
   (#239)`.

### Phase 6 (per aggregator wave) — Cumulation invariant

When a wave's aggregator inputs all have P5 fixtures landed:

1. New file
   `tests/integration/test_cumulation_modelo_<N>.py`.
2. Test sums the input casilla values across the four periods and
   compares to the aggregator's published figures within
   `Decimal("0.01")` tolerance.
3. Commit: `test(cumulation): modelo <N> = sum of <inputs>
   (#239)`.

### Phase 7 (per wave) — Live reconcile dry-run

1. Build a synthetic APPROVED `FilingDraft` from the sanitised
   fixture (using `aeat.application.filing.testing` helpers) under a
   throwaway `--drafts-dir`.
2. Run `uv run aeat filing reconcile --last --modelo <N> --period
   <P>` against the live (Cl@ve-authenticated) sede.
3. Assert exit-code 0 (MATCH) plus a JSON-mode parse to confirm
   the report shape.
4. Commit a `@pytest.mark.live` test exercising the same
   end-to-end path so the live verification is repeatable when
   `AEAT_LIVE_TESTS_ENABLED=1`.
5. Commit: `test(filing): live reconcile MATCH for modelo <N>
   <year>-<period> (#239)`.

### Phase 8 (per wave) — Write-guard re-verify

1. Run `uv run pytest -m unit -k no_write_surface` (existing
   guards across `aeat.adapters.outbound.aeat.sede`, `aeat.application.filing.reconciliation`,
   `aeat.entrypoints.cli.filing._reconcile`).
2. If the wave introduced a new module, add a sibling
   `test_no_write_surface.py` per the established pattern.
3. Commit (only if a new guard test was needed):
   `chore(write-guard): cover modelo <N> extractor (#239)`.

### Phase 9 (per wave) — Vault audit record

1. Scaffold the wave audit:
   `uv run --no-sync vaultspec-core vault add audit --feature
   aeat-verify --title "modelo-<N>-pipeline" --related ...`.
2. Fill: per-phase outcome, captured ground truth (CSVs +
   shas), extractor coverage (casilla counts), cumulation
   findings (if applicable), live-reconcile verdict, open
   issues for follow-up.
3. Update this plan's wave row to `done` (or `na` / `failed`).
4. Commit: `docs(vault): modelo <N> wave audit (#239)`.

## Parallelization

- The cross-wave P1 enumeration is single-threaded (one Cl@ve
  session, sequential nav).
- Within a wave, phases run sequentially: P1 → P2 → P3 → P4 →
  P5 → P6 → P7 → P8 → P9. Phase outcomes feed forward.
- Across waves, P1-P5 of independent modelos can interleave
  (different agents, different commits) provided they touch
  disjoint code surfaces. P6 cumulation waves (W4, W6, etc.)
  serialise behind their input waves' P5.

## Verification

The plan succeeds when, for every wave that returns non-empty
on P1:

- A sanitised fixture for every captured PDF lives under
  `tests/fixtures/justificantes/<modelo>/`.
- A per-modelo extractor exists and its regression tests pass.
- The aggregator cumulation invariant (where applicable) passes
  within tolerance.
- A live reconcile against the captured expediente returns
  MATCH.
- An audit doc captures the wave outcome.

The plan succeeds for every `na` wave when:

- The audit doc records the empty enumeration as evidence and
  marks the wave N/A with the date and the account NIF whose
  enumeration produced the negative.

Be honest: `na` waves can flip back to `running` the moment a
new live capture surfaces a row for that modelo. The plan's
status fields are point-in-time; an `na` wave is not closed
forever.

The hard end-to-end gate, after all non-`na` waves close, is
`uv run pytest -m unit && uv run pytest -m live -k aeat_verify`
green on every reconcile / cumulation / extractor test.
