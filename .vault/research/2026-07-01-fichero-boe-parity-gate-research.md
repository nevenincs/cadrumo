---
tags:
  - '#research'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-17'
related: []
---

# `fichero-boe-parity-gate` research: `fichero-BOE casilla-completeness parity gate`

The operator of this CLI is an autonomous LLM tax-advisor that produces a
fichero-BOE (`.boe`) for a human to upload (live submission is permanently
forbidden). A sweep found the fichero-BOE export path carries **no**
casilla-completeness parity gate. The `modelo-export-mirrors-official-structure`
rule's parity gate — exported casilla set covers the completeness-manifest
required set, keyed by number plus segmento, section order following registry
declaration order, a hard failure on divergence — is wired only for the
**workbook** export (offline xls / Google Sheets), not the fichero-BOE renderer.
This research grounds where and how to extend that gate to the `.boe` path,
reusing the existing manifest and comparison logic rather than rebuilding it. All
coordinates verified against HEAD; the originating brief's line numbers had
drifted +3 to +16 lines.

## Findings

### F1 — The gap is real at HEAD

`completeness_manifest` is referenced **nowhere** in `application/filing/` or
`application/modelo/` (confirmed by search). The `.boe` export path
(`export_draft` in `src/aeat/application/filing/_export.py`, currently
`:279`-`:342`) resolves the layout, calls `_raise_if_export_layout_not_renderable`
(a layout-**shape** gate, not value content), renders bytes via
`_render_export_layout`, computes `casilla_provenance` at `:327`, writes bytes at
`:329`, then digests at `:330`. There is no assertion anywhere in that sequence
that the rendered casilla set covers the completeness-manifest required set.

Completeness today rests only on two indirect guarantees: (a) the revision was
`VERIFICADO_COMPLETO` at verify time, and (b) registry layout authority plus
render-time overlap (`_render_record`, `:820`) and length (`_format_field`,
`:963`) field guards. Neither knows the official *required casilla set*.

### F2 — The digest and the round-trip verb do not close it

`sha256_hex(payload)` (`_export.py:330`, and again in `verify_export` at `:432`)
covers only the rendered bytes. A `.boe` is a **fixed-width** file: every field
occupies its byte slot always, padding blanks/zeros for an absent value. So a
structurally-thin file — one where a required calculation-closure casilla is blank
because the draft never carried it — is still byte-shaped and yields a perfectly
valid digest. The digest is a byte-integrity lock, not a completeness signal (this
is consistent with the `fichero-boe-golden-sha-contract-shape` ADR, which pins the
golden SHA as a byte-identity lock on one fixture, not a per-draft completeness
proof).

`verify_export` (`_export.py:383`-`:468`) is the only completeness re-check, and
it is a **separate, non-automatic verb**. It re-parses the on-disk file and
compares against `draft.values`, but openly admits coverage holes via
`unchecked_casilla_ids` (`:450`-`:456`): casillas the wire layout carries as
reserved literals or derived fields round-trip outside the deserialised set, so a
`MATCH` does not prove every draft casilla reached disk. Its own comment states the
verdict is honest about coverage precisely because a match is partial.

### F3 — The reusable authority already exists (workbook gate + manifest)

The workbook parity gate lives in
`src/aeat/application/storage/calc_sheets/tests/test_modelo_export_parity.py`. Its
core assertion (`test_export_plan_covers_completeness_manifest`) is the pattern to
reuse:

- `manifest = snapshot.revision.completeness_manifest`; assert it is present;
- `required = {(c.number, c.segmento) for c in manifest.casillas}`;
- `emitted = _plan_casilla_keys(snapshot)`;
- `missing = required - emitted`; a non-empty `missing` is a hard failure.

The comparison is **one-directional** (`required ⊆ emitted`), not equality. The
snapshot is obtained by a fresh authority load
(`resources().modelos.authority.snapshot(modelo, filing_year=..., period=..., on=...)`).

`CalculationCompletenessManifest` (`src/aeat/domain/calculations/registry/_schema_surfaces.py:398`)
is the AEAT Diseño de Registros projection the calculation engine already uses. It
enumerates a modelo's **calculation closure** only — formula targets, casillas
referenced in formulas, binding/relation endpoints, verification operands — and
explicitly **excludes** pure accounting-statement data-entry fields. It carries
`legal_refs`/`source_refs`, and a `manual_extraction` flag (plus reason) for
manifests hand-read from a PDF-only Diseño.

### F4 — Why the direction must be `required ⊆ rendered`, never `rendered == required`

The manifest (calculation closure) and the `.boe` record surface (full official
record) are **not** the same set, in either direction:

- The `.boe` renders **more** than the manifest — every pure accounting/data-entry
  field, plus non-casilla wire fields (literals, fillers, headers, NIF, control
  totals). Asserting `rendered == required` would false-fail on every legitimate
  extra field.
- The rendered casilla set can appear to have **less** than the manifest for two
  legitimate reasons: (i) a manifest casilla may be represented only as a
  `BINDING`-row or `COMPUTED`/derived field rather than a plain `CASILLA` field —
  `_exported_casilla_provenance` (`_export.py:1043`-`:1073`) currently counts only
  `CasillaFieldKind.CASILLA` fields intersected with `draft.values`, so those
  casillas would be undercounted; (ii) a record can be **suppressed** for the
  draft's disposition (e.g. `_did_page_suppressed`, `:482`-`:497`, drops the whole
  DID refund page for a non-refund draft), so casillas only applicable under an
  unselected disposition are correctly absent.

The defect the gate must catch is precise: a manifest-required casilla that **is
representable in an applicable (non-suppressed) layout record** but is **absent
from `draft.values`**, so it renders as blanks on disk while the digest stays
valid — the structurally-thin-but-clean file. The required set for the assertion
must therefore be the manifest casillas restricted to those with a casilla-bearing
field in an applicable record; disposition-suppressed and non-representable
casillas are excluded so the gate does not false-fire.

### F5 — Reachability: the manifest is not in scope at the render choke point

`export_draft` receives only a `RegistrySchemaAccessor` and resolves a
`RegistryModeloSubview` via `provider.get_subview(draft.modelo)`. That subview is a
**narrow projection** built by `_subview_from_snapshot`
(`src/aeat/application/filing/runtime.py:588`-`:608`); it copies `export_layouts`,
`reconciliation_total_casilla_ids`, and a fixed field list, but **does not project
`completeness_manifest`**, and the underlying `RegistrySnapshot` is discarded after
the subview is built. So the render choke point cannot see the manifest today.

Three ways to bridge, for the ADR to choose:

- **(a) Project `completeness_manifest` onto the subview.** One-field extension to
  `RegistryModeloSubview` (`filing/runtime.py:191`) plus one line in
  `_subview_from_snapshot` (it already projects `export_layouts` from
  `snapshot.revision` the same way). `export_draft` then asserts against the
  subview it already holds — no signature change, no second authority load. Aligns
  with `aeat-registry-authority-flow` (runtime consumers consume typed projections
  derived from the snapshot).
- **(b) Fresh authority load inside the export path.** Mirrors the workbook test's
  `resources().modelos.authority.snapshot(...)`. Adds a registry load to the render
  hot path.
- **(c) Thread the `RegistrySnapshot` down from a caller that has it.** Signature
  change through `export_draft` and its callers.

`export_modelo_revision` (`src/aeat/application/modelo/_export.py:930`-`:1086`) is
the modelo-level orchestration verb; it holds a `CalculationRevision` and builds
the schema provider before delegating. Note a naming collision the ADR must flag:
that domain `CalculationRevision` is **not** the registry `ModeloRevision` that
carries `completeness_manifest`. It writes bytes via a `.tmp` sibling then atomic
rename, so the true pre-any-disk-write moment is still inside `export_draft`; the
single render choke point is `export_draft`.

### F6 — Coverage honesty: the manifest may be absent or partial

The workbook **test** asserts `manifest is not None` because it iterates a fixed
`_COVERED` list of manifest-bearing modelos. A **runtime** gate fires for any
modelo an operator exports, and many revisions have `completeness_manifest = None`.
So the runtime gate must degrade honestly, never silently:

- manifest `None` → the gate cannot verify completeness; it must **not block** the
  export (that would break every manifest-less modelo), but must surface a
  non-silent coverage advisory that parity was unverified for lack of a manifest.
  Per `cli-notices-are-the-only-diagnostic-channel`, that advisory rides the typed
  `Notice` channel, not a bespoke field.
- manifest present but `manual_extraction` / partial → assert what it enumerates;
  the gate is only as strong as the manifest and says so (mirrors the
  `modelo-export-workbook-parity` ADR's coverage-honesty pitfall).
- manifest present and a required-applicable casilla is missing → **hard**
  `FilingExportError` pre-write; a structural divergence is a failure, never a
  warning (per `modelo-export-mirrors-official-structure`).

### F7 — No existing test asserts fichero-BOE completeness

`test_fichero_boe_export_roundtrip.py` proves per-casilla round-trip fidelity of
casillas that **are** rendered (M130, M303) plus an anti-tautology mutation-drift
proof, but never touches `completeness_manifest`. The modelo-level `test_export*.py`
suite covers headers, output paths, disposition, and refund DID, none asserting
manifest-vs-rendered parity. The nearest sibling gate is the workbook
`test_modelo_export_parity.py` (F3). A new CI parity test for the `.boe` renderer,
mirroring that shape over covered modelos, should lock the new runtime assertion as
a regression gate.

## Open questions for the ADR

1. **Hook point + reachability** — adopt F5(a) (project the manifest onto the
   subview so `export_draft` asserts in place) versus F5(b)/(c). Recommendation:
   F5(a).
2. **Rendered-set definition** — extend the rendered set to count all
   casilla-bearing field kinds (`CASILLA` + `BINDING` rows + `COMPUTED`) across
   non-suppressed records, and restrict the required set to manifest casillas
   representable in an applicable record, so the `required ⊆ rendered` assertion
   catches thin files without false-firing on derived/suppressed casillas.
3. **Coverage honesty policy** — confirm F6: hard fail on manifest-present-and-
   missing; non-silent `Notice` advisory (never block) on manifest absent; honest
   partial coverage on `manual_extraction`.
4. **Runtime + CI** — the automatic pre-write runtime assertion is primary (it
   closes the "verify_export is a separate verb" gap); add the mirrored CI parity
   test as the regression lock.
5. **Scope guard** — the evidence-bytes-by-id export gap is owned by the in-flight
   bucket-custody-completeness brief and is explicitly out of scope here.
