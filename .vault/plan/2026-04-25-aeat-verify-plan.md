---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace aeat-verify with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#aeat-verify'
# ISO date format (e.g., 2026-02-06)
date: '2026-04-25'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-adr]]")
related:
  - "[[2026-04-25-aeat-verify-adr]]"
  - "[[2026-04-25-aeat-verify-research]]"
  - "[[2026-04-25-aeat-verify-audit]]"
  - "[[2026-04-24-aeat-verify-reference]]"
  - "[[2026-04-25-pdf-sanitizer-research]]"
  - "[[2026-04-25-pdf-sanitizer-adr]]"
  - "[[2026-04-25-pdf-sanitizer-plan]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
  loose `scripts/` helper; it is the `aeat.sanitizer` subpackage
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

- Status: `ready`
- Audit doc: TBD on wave start.
- All phases new. Foundational input to W1's eventual P6 if Kent
  has filed quarterly pagos fraccionados.

### W3 — Modelo 303 (IVA quarterly)

- Status: `ready`
- Audit doc: TBD on wave start.
- All phases new. Highest-volume autónomo modelo.

### W4 — Modelo 390 (IVA anual)

- Status: `blocked` on W3 P5.
- Audit doc: TBD on wave start.
- First aggregator wave to exercise P6 cumulation (sum of 4× 303
  trimestral figures).

### W5 — Modelo 111 (retenciones trabajo, quarterly)

- Status: `ready`
- Audit doc: TBD on wave start.

### W6 — Modelo 190 (resumen anual retenciones, anual aggregator)

- Status: `blocked` on W5 P5.
- P6 invariant: sum of 4× 111 retentions == 190 anual cuotas.

### W7 — Modelo 115 + 180

- Status: `ready` for 115 (quarterly); 180 `blocked` on 115 P5.

### W8 — Modelo 123 + 193

- Status: `ready` for 123 (quarterly); 193 `blocked` on 123 P5.

### W9 — Modelo 131, 202, 200 (sociedades)

- Status: `ready` (P1 will likely return `na` for solo autónomo
  profiles; included for completeness).

### W10 — Modelo 347 + 349 (informativas)

- Status: `ready`. P6 for both is invoice-catalogue cross-reference,
  not aggregator-of-modelos.

### W11 — Modelo 369 (IVA OSS), 720 (extranjero), 232 (vinculadas), 840 (IAE)

- Status: `ready` (likely all `na` for Kent).

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
3. Spot-parse one PDF with `aeat.justificante.parse_justificante`.
   If parse fails, P3 is the next phase rather than P4.
4. No commit yet — captures live in `scratch/`, gitignored.

### Phase 3 (per wave) — Justificante regex extension

For each modelo whose PDF the existing parser misses:

1. Inspect the failing field via `pdfplumber` text dump.
2. Extend the regex set in `aeat.justificante._extract`
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
   `aeat.justificante.parse_justificante` and produces the
   synthetic NIF / name / CSV / NRC / IMPORTE values
   (`aeat sanitize check` runs both checks).
4. Run `aeat sanitize verify <fixture-pdf> --against <yaml>`. Must
   exit zero; non-zero means a `real:` value leaked into the
   sanitised output and the fixture must NOT be committed.
5. Append the fixture's SHA-256 to
   `aeat.sanitizer.fixtures.SANITIZED_SHAS` so future
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
   `src/aeat/declaracion/_parsers/<modelo>/` mirroring the Modelo
   100 layout: `_scanner.py` (per-page text scan +
   value-typing), `_extractor.py` (per-template-revision driver),
   `__init__.py`, `test_extractor.py`.
2. Register the new template revisions in
   `src/aeat/declaracion/_extractors/__init__.py`.
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
   fixture (using `aeat.filing.testing` helpers) under a
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
   guards across `aeat.sede`, `aeat.filing.reconciliation`,
   `aeat.cli.filing._reconcile`).
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
