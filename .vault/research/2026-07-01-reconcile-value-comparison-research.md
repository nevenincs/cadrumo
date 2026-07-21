---
tags:
  - '#research'
  - '#reconcile-value-comparison'
date: '2026-07-01'
modified: '2026-07-01'
related: []
---

# `reconcile-value-comparison` research: `reconcile value comparison`

The `aeat` CLI's target operator is an autonomous LLM tax-advisor that closes the
filing loop with `aeat app modelo reconcile` — pull the AEAT justificante (or read
a local one) and compare it against what it computed. This research confirms, at
HEAD, that the reconcile compare is **identity-only**: it diffs four header fields
and returns match/mismatch, but never loads the calculation revision and never
reconciles the receipt totals the parser already extracts. So `verdict=matches`
certifies "this is a receipt for the right modelo / period / filer", NOT "the filed
amount equals my computed result." An agent relying on reconcile for
closing-the-loop assurance gets a **false green**. The purpose here is to ground the
gap, inventory the canonical machinery a value reconciliation would consume, and
frame the decisions the ADR must resolve. Nothing is implemented in this pass.

## Findings

### F1 — The compare is header-identity-only; totals are parsed then dropped

`_reconcile_parsed_justificante` (`src/aeat/application/modelo/_reconcile.py:270-398`)
diffs exactly four header-identity fields against the parsed receipt: `modelo`
(`:309`), `ejercicio` (`:318`), `period` (`:327`), `tax_id` (`:336`). Verdict is
binary `MATCHES` / `MISMATCHES` (`:347`). It never loads the local
`CalculationRevision` and compares **no** casillas nor totals (service docstring
`:216-219`; payload docstring `src/aeat/entrypoints/cli/_payloads_modelo_reconcile.py:28-32`).
The `--revision` CLI arg is consumed only for work-unit resolution
(`_modelo_reconcile_cli.py:176,228`), never for value comparison.

The parser **does** extract the receipt totals: `Justificante.total_a_ingresar` /
`total_a_devolver` (`Decimal | None`, `src/aeat/domain/justificante/_schema.py:73-74`),
matched by `_TOTAL_INGRESAR_RE` / `_TOTAL_DEVOLVER_RE` / `_NRC_IMPORTE_RE`
(`src/aeat/adapters/inbound/justificante/_extract.py:184-198`, resolved by
`_extract_totals` `:457-463`). These live on every parsed `Justificante` and are
carried through both reconcile entry points (`modelo_reconcile`,
`modelo_reconcile_bytes`) — but `_reconcile_parsed_justificante` never reads them.
A filed-amount divergence is therefore structurally invisible today.

### F2 — The canonical total→casilla spine already exists: `reconciliation_total_casilla_ids`

`VerificationExpectationDefinition.reconciliation_total_casilla_ids` is a
registry-declared, strict `Mapping[Literal["ingresar", "devolver"], CasillaId]`
(`src/aeat/domain/calculations/registry/_schema.py:574`). It maps the two receipt
total kinds to the canonical **result** casilla of a revision, and it is
registry-build validated against real casilla ids on three surfaces
(`_validate_references.py:250`, `_validate_surfaces.py:283`,
`_validate_revision_rules.py:186`) and by the record-design coverage check
(`_record_design_coverage.py:136`).

Crucially, `calculation_result_summary`
(`src/aeat/application/modelo/_result_summary.py:94-167`) **already consumes** this
map to project `result_ingresar` / `result_devolver` rows out of
`revision.casilla_values`. So the canonical computed total — the value the receipt
total must equal — is exactly `revision.casilla_values[reconciliation_total_casilla_ids["ingresar"|"devolver"]]`.
This is the `one-aggregation-path-pull-equals-calculate` value (the persisted
revision's own casilla value), not a re-derivation. Reusing this map means the
reconciler reconciles totals against the same canonical result the result-summary
and export surfaces render.

### F3 — The map is declared on only 8 revisions (sparse coverage)

`reconciliation_total_casilla_ids` is declared on only **8** revision fragments
today: `111/2019-y-siguientes` (`ingresar="30"`), `123/2019-2023` (`"08"`),
`123/2024-y-siguientes` (`"14"`), `115/2019-y-siguientes` (`"05"`), `131/2024`
(`"15"`), `131/2026` (`"15"`), and two siblings. The large periodic/annual modelos
an agent most needs to close the loop on — M303 (IVA), M100 (Renta), M130, M200 —
do **not** declare it. Consequences: a value reconciliation keyed on this map can
compare totals only where the revision declares it; everywhere else it must **not**
emit a false green — it must surface that value reconciliation was *not performed*
(an advisory / distinct verdict), and enrolling the map for the missing revisions is
a bounded registry follow-on. This is the `no-silent-under-declaration` fault line
of the whole feature.

### F4 — Receipt exposes totals only; per-casilla values are not extractable here

The justificante is a *receipt*: `extract_justificante_from_digest`
(`_extract.py:323-383`) pulls CSV, modelo, period/ejercicio, tax_id, presentation
id, timestamp, the two payment totals, and the verification URL — and the module
docstring is explicit that "casilla-level filing values belong to the
declaración/borrador adapters, not this receipt surface" (`_extract.py:6-9`). So
casilla-by-casilla reconciliation of the *receipt* is not achievable without the
deferred modelo-specific **declaration** parser (already refused at
`_reconcile.py:221-224,249-252` via `ReconciliationDeclaracionSourceUnsupportedError`).
The achievable depth for the *receipt* reconcile is **totals**. (Casilla-level
extraction is sequenced as a follow-on gated on the declaration parser, out of scope
here.)

### F5 — A distinct casilla-level filed-vs-engine surface already exists at *verify*

The today-dated `2026-07-01-verification-reconcile-when-present-adr` added a
`reconcile_when_present` verification class: at the **verify** gate, every computed
casilla is reconciled filed-vs-engine when the filing prints it, excluded from the
coverage denominator so it can never flip a coverage verdict. This is a *different
surface* from the receipt reconcile — it reconciles against provided declaration
values inside `_verify.py`, not against the justificante receipt — but it confirms
the project's direction (surface filed-vs-engine divergences as advisory
`NEEDS_REVIEW`, never silently pass) and the `reconciliation_total_casilla_ids`
vocabulary the ADR reuses. The two surfaces are complementary: verify reconciles the
*declaration*; reconcile must reconcile the *receipt total*. The receptor of the
"false green" today is specifically the receipt-reconcile path.

### F6 — Envelope command-id bug: pull and file both emit `modelo.reconcile`

Both `reconcile pull` and `reconcile file` call
`_render_reconciliation_report(ctx, report, command="modelo.reconcile")`
(`_modelo_reconcile_cli.py:202,257`), but the schemas are registered under
`modelo.reconcile.pull` / `modelo.reconcile.file`
(`_payloads_modelo_reconcile.py:40-41`). `emit_json_success` stamps the `command`
string verbatim without validating it against the registered leaf
(`src/aeat/core/json_contract.py`), so the emitted envelope carries neither
registered id. An agent cannot discriminate pull vs file from the envelope.
(`history` is correct: it emits `modelo.reconcile.history`, `:340`.) This is a
concrete instance of a *behavioural*-conformance gap: the leaf-schema gate is
structural (it asserts a schema is registered per id) and does not assert the
runtime emit string equals the registered id.

### F7 — Dead `EVIDENCE_INVALID` verdict

`ModeloReconciliationVerdict` advertises `EVIDENCE_INVALID` (`_reconcile.py:54-56`),
but the report path only ever sets `MATCHES` / `MISMATCHES` (`:347`). A parse
failure is raised as a typed refusal (`ReconciliationEvidenceInvalidError`,
`_reconcile.py:159-181,229-232,257-260`), never returned as a report carrying that
verdict. An agent watching the verdict enum for `evidence_invalid` never sees it —
it must instead catch the refusal error. The member is currently a shell.

### F8 — Lossy history: diff **count**, not which fields

`MODELO_RECONCILED` persists diffs as a **count** string in the event payload
(`_reconcile.py:364-370`: `"diffs": str(len(diffs))`), and
`list_modelo_reconciliations` reads back only `diff_count`
(`_reconcile.py:458`; surfaced as `ModeloReconciliationHistoryEntry.diff_count`,
`:79`). `reconcile history` can therefore say "N fields diverged" but never *which*
— so a past divergence is not auditable after the fact from history alone.

### F9 — Auth + evidence-byte dependence (custody coupling)

`pull` is gated by the same live-auth boundary as `app live`
(`capture_justificante_snapshot` → `require_live_read`) and needs the raw PDF bytes
from the encrypted snapshot (`src/aeat/application/live/_justificante.py`). The
durable `Justificante` **metadata** record holds the totals but not the PDF bytes,
so reconcile cannot fall back to metadata-only — it needs either a persisted capture
(bytes) or a local `--file`. A restored bundle that dropped attachment bytes cannot
be re-reconciled without a fresh pull. This ties to the in-flight
`bucket-custody-completeness` brief; the evidence-bytes fix is owned there, recorded
here as a dependency only.

### F10 — Conditional skips weaken even the header check

`ejercicio` is compared only when present on the receipt
(`_reconcile.py:318`, `justificante.ejercicio is not None`), and `tax_id` only when
the active profile carries one (`:337`, `if profile_tax_id and ...`). A receipt that
omits `ejercicio`, or a profile with no tax id, silently drops that field from the
comparison and can still reach `verdict=matches`. Whether a missing identity anchor
should downgrade the verdict or raise an advisory is an open decision.

## Canonical value-read path (for the ADR)

The value reconciliation the ADR mandates consumes existing, proven surfaces:

- Resolve the work unit and its law-determined revision
  (`revision-resolution-is-law-determined`) — the same `--revision`-asserted
  resolution the CLI already performs.
- Load the persisted `CalculationRevision` for that work unit (the surface
  `calculation_result_summary` and `_load_revision_for_export`
  (`src/aeat/application/modelo/_export.py:398`) already read;
  `revision.casilla_values` is the canonical `{CasillaId: Decimal}` map).
- Read `snapshot.revision.verification_expectations[*].reconciliation_total_casilla_ids`
  → `{ingresar|devolver → CasillaId}`; look those casillas up in
  `revision.casilla_values` → canonical computed `total_a_ingresar` /
  `total_a_devolver`.
- Compare against `justificante.total_a_ingresar` / `total_a_devolver`, carrying the
  result casilla's `legal_refs` / `source_refs` onto any divergence
  (`aeat-calculation-grounding`).

## Constraints and rules in force

- `aeat-cli-pull-and-file-standard`: `pull` fetches from AEAT, `file --file` is the
  local artefact; the reconcile subgroup and the command-id must conform.
- `one-aggregation-path-pull-equals-calculate` + `aeat-calculation-grounding`:
  compare against the canonical revision value with provenance carried onto
  divergences.
- `no-silent-under-declaration`: a filed-amount divergence (especially filed <
  computed) MUST surface, never be hidden behind an identity match; a revision with
  no `reconciliation_total_casilla_ids` must not yield a false green.
- `cli-notices-are-the-only-diagnostic-channel`: divergences are structured findings
  / typed `Notice`s, not prose.
- `aeat-roundtrip-discipline`: the reconcile-report persistence gets a real
  roundtrip test; `revision-resolution-is-law-determined` for the revision it
  compares against.

## Out of scope

- OCR / scanned-image justificante parsing (keep the current instructive refusal).
- The declaration-source reconcile parser (leave deferred at
  `_reconcile.py:221-224`).
- The custody evidence-bytes fix (owned by `bucket-custody-completeness`; recorded
  as a dependency).
- Casilla-by-casilla receipt reconciliation (gated on the declaration parser;
  sequence as a follow-on).

## Open decisions handed to the ADR

1. **Comparison depth** — extend to value reconciliation of the receipt totals
   against the canonical revision result via `reconciliation_total_casilla_ids`; the
   behaviour when the revision does not declare the map.
2. **Divergence model** — structured `ModeloReconciliationDiff` kinds
   (header-field, total, and a reserved casilla kind) carrying provenance, and a
   non-lossy history that persists *which* fields diverged.
3. **Dead `EVIDENCE_INVALID`** — wire it (return a report carrying the verdict) or
   remove the enum member.
4. **Envelope command-id fix** — pull/file must emit their registered
   `.pull` / `.file` keys; flag the behavioural-gate candidate for the
   manifest/conformance brief without scoping that gate here.
5. **Conditional-skip hardening** — whether a receipt missing `ejercicio` (or a
   profile missing `tax_id`) passes silently or downgrades the verdict / raises an
   advisory.
