---
tags:
  - '#adr'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-research]]"
---

# `fichero-boe-parity-gate` adr: `automatic casilla-completeness parity gate on the fichero-BOE export` | (**status:** `accepted`)

## Problem Statement

The fichero-BOE (`.boe`) export path carries no casilla-completeness parity gate.
The `modelo-export-mirrors-official-structure` rule requires every modelo export to
pass a registry-grounded parity gate — the exported casilla set covers the
completeness-manifest required set (number plus segmento, section order), a hard
failure on divergence — but that gate is wired only for the **workbook** export
(offline xls / Google Sheets). The `.boe` renderer relies on verify-time
`VERIFICADO_COMPLETO` plus render-time overlap/length field guards, none of which
knows the official *required casilla set*.

Because a `.boe` is fixed-width, every field always occupies its byte slot,
padding blanks for an absent value. A structurally-thin file — one where a
required calculation-closure casilla is blank because the draft never carried it —
is still byte-shaped and yields a valid `sha256_hex` digest. The only completeness
re-check, `verify_export`, is a **separate, non-automatic verb** that openly admits
coverage holes (`unchecked_casilla_ids`). So the autonomous LLM operator, and the
human it hands the file to, can ship an export missing required casillas with no
hard signal. This ADR closes that gap by extending the existing parity gate to the
`.boe` path, reusing the manifest and comparison logic rather than rebuilding it.

## Considerations

- The reusable authority already exists: `CalculationCompletenessManifest` (the
  AEAT Diseño de Registros projection the calculation engine consumes) and the
  workbook gate's one-directional `required - emitted` comparison in
  `test_modelo_export_parity.py`. This ADR reuses both; it does not author a new
  parity oracle.
- The manifest enumerates a modelo's **calculation closure only** (formula targets,
  formula operands, binding/relation endpoints, verification operands) and
  deliberately excludes pure accounting-statement data-entry fields. The `.boe`
  renders the **full official record**, so the two sets are unequal by design.
- The render choke point `export_draft` cannot see the manifest today: it holds
  only a narrow `RegistryModeloSubview` that does not project
  `completeness_manifest`, and the underlying `RegistrySnapshot` is discarded after
  the subview is built.
- Many revisions have `completeness_manifest = None`. A runtime gate fires for any
  exported modelo, so it must degrade honestly without silently passing and without
  blocking manifest-less modelos.
- Governing rules: `modelo-export-mirrors-official-structure` (divergence is a hard
  failure, never a warning), `aeat-registry-authority-flow` (consume typed
  projections derived from the snapshot), `no-silent-under-declaration` (an
  unverifiable completeness claim must surface, not vanish), and
  `cli-notices-are-the-only-diagnostic-channel` (non-blocking diagnostics ride the
  typed `Notice` channel).

## Considered options

**Hook point.** (A, chosen) Assert inside `export_draft` — the single render choke
point through which all `.boe` bytes flow — pre-write, so no `.boe` reaches disk
without the check. (B, rejected) Assert in the modelo-level `export_modelo_revision`
orchestrator — it holds more context but writes bytes via a `.tmp` sibling first,
so the file already exists on disk before the check, and it would leave the
lower-level `export_draft` entrypoint ungated for any other caller. (C, rejected)
Make `verify_export` automatic — it is a post-write re-parse that admits coverage
holes by design; it verifies round-trip fidelity, not required-set coverage.

**Manifest reachability.** (A, chosen) Project `completeness_manifest` onto
`RegistryModeloSubview` — a one-field extension mirroring how the subview already
projects `export_layouts` from `snapshot.revision`; `export_draft` then asserts
against the subview it already holds, with no signature change and no second
registry load. (B, rejected) Fresh authority load inside the export path — adds a
registry load to the render hot path and duplicates the snapshot the subview was
already derived from. (C, rejected) Thread the `RegistrySnapshot` through
`export_draft` and its callers — a wider signature change for state the subview can
carry.

**Comparison direction.** (A, chosen) `required_applicable ⊆ rendered` — the
workbook gate's one-directional shape; extra rendered casillas (accounting fields)
are legitimate. (B, rejected) `rendered == required` — false-fails on every
legitimate non-manifest field the `.boe` must carry.

**Absent-manifest policy.** (A, chosen) Non-blocking `Notice` advisory that parity
was unverified for lack of a manifest. (B, rejected) Block the export — breaks every
manifest-less modelo. (C, rejected) Silent pass — a silent under-declaration, barred
by `no-silent-under-declaration`.

## Constraints

- **Parent-feature stability.** Depends on `modelo-export-workbook-parity` (the
  manifest-grounded gate) and `aeat-registry-authority-flow` (the subview
  projection). Both are accepted and in production; the manifest field
  `ModeloRevision.completeness_manifest` and the subview builder
  `_subview_from_snapshot` are stable surfaces.
- **No over-strictness.** The rendered-set derivation
  (`_exported_casilla_provenance`) currently counts only `CasillaFieldKind.CASILLA`
  fields; a manifest casilla represented only as a `BINDING`-row or `COMPUTED`
  field, or one under a disposition-suppressed record (e.g. the DID refund page),
  must not false-fire. The required set must be restricted to manifest casillas
  representable in an applicable (non-suppressed) record, and the rendered set must
  count all casilla-bearing field kinds that reach disk.
- **Naming collision to avoid.** In `export_modelo_revision` the domain
  `CalculationRevision` is not the registry `ModeloRevision` that carries
  `completeness_manifest`; the manifest must be sourced from the registry
  projection, not the calculation revision.
- **No new authority.** Faithfulness is asserted against the registry completeness
  manifest — never a hand-authored `.boe` expectation that could drift from AEAT.
- **Scope guard.** The evidence-bytes-carried-by-id export gap is owned by the
  in-flight bucket-custody-completeness brief and is explicitly out of scope.

## Implementation

Project `completeness_manifest` onto `RegistryModeloSubview` (one field, populated
in `_subview_from_snapshot` alongside the existing `export_layouts` projection).
`export_draft` gains an automatic, pre-write parity assertion: after the rendered
casilla set is known (the `_exported_casilla_provenance` step) and before
`output_path.write_bytes`, it computes the required set from
`subview.completeness_manifest`, restricts it to casillas representable in an
applicable (non-suppressed) layout record, and asserts that restricted set is a
subset of the casillas that actually reached disk. A non-empty shortfall raises a
hard `FilingExportError` naming the missing casillas, before any bytes are written.

The rendered-set derivation is widened so it counts every casilla-bearing field
kind that reaches disk (plain `CASILLA`, `BINDING`-row casillas, and any
`COMPUTED`/derived casilla-bound field), not only `CasillaFieldKind.CASILLA`, so a
manifest casilla carried by a non-plain field is not undercounted.

Coverage honesty is explicit and non-silent: when `completeness_manifest` is
`None`, the export proceeds but emits a non-blocking `Notice` advisory that parity
was unverified for lack of a manifest; when the manifest is present but
`manual_extraction` (or otherwise partial), the gate asserts what it enumerates and
reports its coverage honestly rather than implying full parity; when the manifest
is present and a required-applicable casilla is absent from disk, the gate hard-
fails. The same check is threaded through `export_modelo_revision` so the operator-
facing orchestration verb surfaces the advisory on its envelope.

A new CI parity test mirrors the workbook `test_modelo_export_parity.py` shape over
the export-capable covered modelos, driving `export_draft` and asserting the
required-applicable manifest set reached disk — the regression lock for the runtime
assertion. The pre-write hard-failure is the primary gate (it closes the
"`verify_export` is a separate verb" hole); the CI test locks it against
regression.

## Rationale

Reusing the completeness manifest keeps "official parity" checked against the same
authority the calculation engine consumes, eliminating a drift surface — the same
reasoning the `modelo-export-workbook-parity` ADR applied to the workbook
transport, now extended to the transport that actually produces the file a human
uploads. The pre-write hook in `export_draft` is the only point where the rendered
set and the manifest can coexist before bytes touch disk, so it is where an
automatic gate belongs; making it automatic is precisely what closes the gap that
`verify_export` (a separate, coverage-admitting verb) leaves open. The
one-directional `required ⊆ rendered` comparison, the applicable-record
restriction, and the widened rendered-set derivation are all forced by the manifest
being the calculation closure while the `.boe` is the full record (research F4). The
non-blocking advisory on an absent manifest honours `no-silent-under-declaration`
without regressing the many manifest-less modelos, and routing it through the typed
`Notice` channel honours `cli-notices-are-the-only-diagnostic-channel`.

## Consequences

- **Gain:** a structurally-thin-but-clean `.boe` — a valid digest over a file
  missing required calculation-closure casillas — becomes a hard, automatic failure
  at export time, before the file exists, for both the autonomous operator and the
  human uploader.
- **Gain:** the parity discipline is now uniform across both export transports
  (workbook and fichero-BOE), grounded in one authority, satisfying the intent of
  `modelo-export-mirrors-official-structure` for the `.boe` path.
- **Cost:** a one-field subview extension plus a rendered-set derivation that must
  correctly enumerate all casilla-bearing field kinds; getting the applicable-record
  restriction wrong risks either false failures (over-strict) or missed thin files
  (under-strict), so the CI test must exercise a suppressed-record disposition.
- **Pitfall:** parity is only as strong as the manifest. A modelo with no manifest,
  or a `manual_extraction` manifest, yields a weaker gate; the advisory must make
  that honestly visible rather than implying full parity.
- **Pathway:** with the manifest reachable at the export choke point, later export
  surfaces (section-order and numbering assertions, or additional transports) can
  reuse the same projection and comparison.

## Codification candidates

- **Rule update (not a new rule):** extend `modelo-export-mirrors-official-structure`
  so its parity-gate mandate explicitly binds the fichero-BOE transport, not only
  the workbook transport — a `.boe` export must pass the same registry-grounded
  completeness gate, automatically and pre-write, a hard failure on divergence.
  Promote per the `vaultspec-codify` discipline once the gate lands and the CI
  regression test is green.
