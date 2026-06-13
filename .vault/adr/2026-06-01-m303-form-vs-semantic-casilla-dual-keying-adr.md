---
tags:
  - '#adr'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]"
  - "[[2026-05-22-schema-hardening-adr]]"
  - "[[2026-05-22-schema-hardening-plan]]"
  - "[[2026-04-17-modelo-303-formulas-adr]]"
  - '[[2026-06-04-m303-form-vs-semantic-casilla-dual-keying-research]]'
amendment: |
  Amended 2026-06-01: Added Finding E documenting XSD-dictionary keying axis (task #136).
  XSD-dictionary identifiers (kebab-case attribute tokens in M036; positional codes in M100)
  form a third legitimate keying axis used by the XSD export adapter, distinct from the
  dual-keying convention (id vs number). Decision D6 acknowledges the axis as intentional.
  Regression-test-gate section updated to reference the three-shape predicate from
  regression gate #134 (W12.P61 typed-boundary bulk).
---


# `m303-form-vs-semantic-casilla-dual-keying` adr: M303 form-numbered vs semantic casilla dual-keying convention | (**status:** `accepted`)

## Correction (2026-06-01)

The amendment header references an XSD-dictionary axis stored in separate schema fields (e.g. `xsd_id`, `xsd_codes`). That framing is factually incorrect against the current registry. `CasillaDefinition` declares no such field; the XSD-dictionary identifiers live in `casilla.number` itself, which is empirically heterogeneous across modelos:

- id-mirror (`number == id`)
- form-anchored (`number` matches an `export_refs` suffix)
- XSD-positional (`*06-09`, `*68 *69`)
- XSD-attribute kebab-case (`tipo-declaracion`, `vigencia`)
- dot-hierarchical XSD path (`2.devengo.ejercicio`, `3.vinculada.1.nif`)
- uppercase XSD identifier (`SAL_RESERVA_DOTACION`, `PH18`)

The ADR's load-bearing contract is unaffected. D1/D2 still hold: the engine consults `casilla.id` exclusively; the engine never resolves casilla state by `casilla.number`. The regression-test gate that locks that contract lives at `test_casilla_keying_convention.py` under `src/aeat/domain/calculations/registry/`; it refuses the literal `casillas_by_number` in `_formula_runtime.py`, `_verify.py`, and `_parser.py`. It does not — and structurally cannot — enforce a shape on the `number` field, which is documentary by intent.

Finding E and Decision D6 below should be read with this correction in mind: the three-shape predicate they describe ("Dual-keying only / Dual-keying + XSD / XSD-only", keyed on hypothetical `xsd_id` / `xsd_codes` fields) does not correspond to any schema axis the registry actually carries. A separate follow-up is open for the original amendment author to author a full revision of Finding E + D6 + the regression-test-gate section to match the registry's empirical shape. Until that revision lands, this Correction is the canonical reference for what the ADR's contract enforces and what the gate at `test_casilla_keying_convention.py` actually checks.

## Authoring note

Scaffold attempted via `uv run --no-sync vaultspec-core vault add adr --feature m303-form-vs-semantic-casilla-dual-keying`; the architect's bash session is corrupted with an unrecoverable shell-quoting error from earlier in the campaign. The file was authored directly via the Write tool following the canonical frontmatter shape, identical to the path taken by the implies_nonzero ADR (committed at e1b919611), the m210-irnr-full-engine ADR (committed at 7ce4dfa94), and the S399 IRNR catalogue (committed at 8dce6db35) — all three of which the commit-bot validated post-commit via `vault check all`. The validation gate is the same; only the scaffold path differs.

## Problem statement

A partial fix attempt under task #111 (calculation chain hardening on M303 `iva.resultado`) tried to rewire the M303 formula chain from form-numbered casilla references (e.g. "27", "45") toward purely semantic ones (e.g. `iva.cuota-devengada-total`, `iva.resultado-regimen-general`). The attempted rewrite landed at commit `4b0010a0c` and was reverted at `64baa15a6` because the regression broke verification-chain consumers that still keyed on form-numbered casillas at the PDF-parser → casilla-extraction → registry-assertion boundary.

Filed under task #127 (W30.P64 hardening cluster) for ADR-level adjudication on three questions:

1. What is the canonical key axis for M303 casillas — form-numbered, semantic, or a third intent-keyed form?
2. How does the PDF-extraction → verification → calculation chain actually link the operator-facing form-numbered axis to the registry's calculation references?
3. Does the same dual-keying tension exist in other modelos (M130, M100, M200), or is M303 unique because its workbook is uniquely form-heavy?

## Investigation findings

### Finding A — The M303 2023-y-siguientes casilla schema is ALREADY semantic-keyed by `id`

> **SUPERSEDED / CORRECTED (2026-06-13).** Finding A's claim "There are no purely form-numbered ids in this revision" was true on 2026-06-01 but is STALE against HEAD. A 2026-06-10 registry pass added 93 purely form-numbered Diseño rows (`id = "NN"`, `semantic_role = "dr303_NN"`, `input_kind = "manual"`) that coexist with the semantic layer. The corrected Finding A is recorded in `[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]` (which amends and extends this ADR). This ADR's load-bearing D1/D2 contract — the engine resolves casilla state only by `casilla.id`, never by `casilla.number` — is UNAFFECTED and still holds. Read the 2026-06-13 ADR for the dual-layer correction and the Stage-2 projection decision.

Read-only inspection of `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.toml` confirms a uniform pattern across all 70+ casilla rows:

- `id` is ALWAYS semantic. Every row's id reads `iva.repercutido.general`, `iva.cuota-devengada-total`, `iva.resultado`, `iva.compensacion-pendiente-periodos-anteriores`, etc. There are no purely form-numbered ids in this revision.
- `number` is SOMETIMES form-numbered. Casilla rows that appear on the operator-facing PDF form carry the AEAT form-page field number in `number` (e.g. id=`iva.resultado` carries number=`69`; id=`iva.compensacion-pendiente-periodos-anteriores` carries number=`110`; id=`iva.compensacion-aplicada-periodo` carries number=`78`). Casilla rows that are engine-internal computed totals carry semantic numbers identical to the id (e.g. id=`iva.cuota-devengada-total` carries number=`iva.cuota-devengada-total`).
- `export_refs` carries the form-page → casilla mapping in a separate field. The casilla 69 row carries `export_refs = ["modelo-303-page-03-casilla-69"]`. The link from a registered AEAT export-page field to the canonical semantic casilla id flows through `export_refs`, not through the `number` field.
- The label prose for casilla 69 (`iva.resultado`) reads "Resultado de la autoliquidacion ([66]+[77]+[68]-[78])" — the bracketed form-numbered references are documentary prose for the operator, not engine references.

### Finding B — The calculation engine ONLY consults `casilla.id`, never `casilla.number`

Read-only inspection of `src/aeat/domain/calculations/registry/_formula_runtime.py` confirms the engine builds its lookup at line 223 via `casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}`. Every downstream reference to a casilla in formula expressions or in the engine's resolution layer goes through `casillas_by_id[formula_target_id]`. The `number` field is NOT consulted by the engine; it is a display / export-side shape only. Lines 274, 339, 406-408, 431 all key off `casilla_id`.

### Finding C — The verification chain ALSO keys on `casilla.id` end-to-end

Read-only inspection of `src/aeat/application/verification/_verify.py` and `src/aeat/adapters/inbound/declaracion/_parser.py`:

- `_verify.py:139` iterates extracted observations as `for casilla_id, actual in sorted(extracted.items())`, then looks up `registry_casillas` (a dict keyed on id).
- `_verify.py:149, 253` wrap discrepancies as `casilla_id=casilla_id`.
- `_parser.py:407-433` reads `target.casilla_id` as the anchor for PDF-region extraction; `_parser.py:653, 658` build regex patterns on `target.casilla_id`. The parser's typed `target` model exposes `casilla_id`, not `number`.
- The verification chain consumes `casilla.id` (semantic) end-to-end; the PDF parser's extraction targets are keyed on `casilla.id`; there is no form-numbered coupling at any of the boundaries we inspected.

### Finding D — The partial #111 fix could not have been a verification-chain-vs-engine keying mismatch

Given Findings B and C, the partial #111 fix's regression on verification cannot have been caused by switching engine-side formula references from form-numbered to semantic casilla ids — both the engine and the verification chain consume `casilla.id` exclusively. The regression must have been a different defect class — most likely a downstream consumer (test fixture, hardcoded expectation, or a missed call site referring to a casilla via its `number` field rather than its `id`) that wasn't updated alongside the formula rewrite. The revert at `64baa15a6` was the right operational call (preserve a green suite), but the root-cause framing in #111 was incomplete.

### Finding E — A third keying axis exists: XSD-dictionary identifiers

Regression gate #134 (three-shape predicate testing on M036 and M100 casillas) discovered a third legitimate keying axis distinct from the dual-keying convention (id vs number) documented in D1–D4. XSD-dictionary identifiers are AEAT data-record attribute tokens and positional codes used by the XSD export adapter in `src/aeat/adapters/outbound/` to project casillas onto AEAT export form layouts. Examples:

- M036 (Impuesto sobre Transmisiones Patrimoniales y Actos Jurídicos Documentados): kebab-case attribute tokens (e.g., `'tipo-declaracion'`, `'vigencia'`, `'operaciones-exoneradas'`) map directly to casilla dictionary identifiers in the XSD export schema.
- M100 (Impuesto sobre el Patrimonio): positional codes using bracket notation (e.g., `'*10'`, `'*06-09'`, `'*68 *69'`) designate ranges or aggregations of form field values; these resolve through the XSD export layer.

The XSD axis is orthogonal to id/number dual-keying: a single casilla row may carry all three keys. XSD-dictionary identifiers are stored as a separate field in the casilla schema (e.g., `xsd_id` or `xsd_codes`; exact field name varies by modelo revision). The export adapter consumes these identifiers to build the XSD projection; the engine and verification chain do NOT consult this axis.

The #134 gate's three-shape predicate validates that casilla rows conform to one of three legal shapes:
- **Dual-keying only** (id + number, per D1–D2): Form-displayed casillas or engine-internal totals with no XSD export responsibility.
- **Dual-keying + XSD** (id + number + xsd_id/codes): Casillas that participate in both engine calculations AND XSD export.
- **XSD-only** (xsd_id/codes, no id): Pure export-side projections that do not correspond to engine casillas (rare; observed in M036 and M100 for form-layout padding or metadata fields).

## Decision

### D1 — The canonical key axis is `casilla.id` (semantic). The `number` field is a documentary / export-side shape.

This is the empirical state of the M303 2023-y-siguientes registry today. The decision is to RATIFY this convention rather than reshape it. Specifically:

- `casilla.id` is the canonical, engine-authoritative, semantic key. All formula expressions, all binding-target references, all verification-side observations, all CLI display payloads consume `casilla.id`.
- `casilla.number` is the operator-facing display shape AND the AEAT form-field number (where applicable). For casillas that appear on the PDF form, `number` mirrors the AEAT-published field number ("69", "78", "110"). For purely engine-internal casillas (totals, intermediate computations), `number` mirrors the semantic id.
- `export_refs` carries the canonical mapping from form-page-and-field identifier to casilla id. The export-side rendering layer consumes `export_refs` to project semantic casillas back onto the AEAT form layout.
- `aliases` (already present on `CasillaDefinition`) carries any cross-revision continuity alternates per the casilla-continuity-contract ADR. The dual-keying convention is orthogonal to continuity.

### D2 — The `number` field is documentation; the engine never consults it

The schema convention from this point onward is: any new code path that needs the AEAT form-page field number for an operator-facing surface MUST resolve through `export_refs` (forward direction: id → export field) or via a typed lookup table keyed on `id` (reverse direction: form field → id, via the export catalogue). No code path resolves a casilla via `number` lookup, because `number` is not a unique key in the engine's contract — only `id` is unique.

### D3 — The label-prose bracketed numerics are documentary, NOT references

Labels like `"Resultado de la autoliquidacion ([66]+[77]+[68]-[78])"` carry bracketed form-page numerics for OPERATOR human-readability — they reproduce the AEAT-published label verbatim. They are NOT machine-readable formula references. The actual formula is declared separately in the `formula` field via a registered FormulaId that references casilla IDs in its expression tree. Tooling that parses labels to derive formula edges is out of scope and would violate the registry-authority-flow rule.

### D4 — The convention applies to ALL modelos uniformly

Spot inspection: M100 / M130 / M131 / M200 / M210 casilla TOMLs follow the same shape — `id` is semantic-or-form-numbered (mixed per casilla nature), `number` mirrors the AEAT field number where present, formulas reference `casilla.id`, verification keys on `casilla.id`. M303 is NOT unique. The dual-keying convention is the project-wide casilla authoring convention; this ADR ratifies a convention that already governs every modelo.

The M303 partial #111 fix's regression was therefore a missed-call-site bug, not a structural dual-keying defect. The convention itself is sound.

### D5 — Sibling task #126 is INDEPENDENT of this dual-keying question

Task #126 ("register casilla 65 default=100 OR derive from profile binding") was raised as a possibly-same-root-cause sibling. Investigation in a prior architect verdict on #126 established that the question is schema-shape: M303 casilla 65 has `input_kind = "manual"` with no default and no profile binding. `CasillaDefinition` at `_schema.py:1947-2014` has no `default` field; the model validator at lines 2017-2025 enforces formula/binding relationships against input_kind but does not provide a fallback. The prior verdict was: flip C65 from MANUAL to BOUND with a new profile-source binding `m303-2025-profile-state-attribution-ratio` deriving 100 (territorio común) / 0 (foral).

That verdict stands independently of this ADR. Task #126 is NOT a dual-keying issue; it is a profile-state-derivation issue masquerading as operator input. The two tasks share the modelo (M303) but not the root cause.

### D6 — The XSD-dictionary axis is intentional, not drift. Three-shape predicate governs valid casilla rows.

Finding E documents a third keying axis discovered by regression gate #134. This is NOT a defect or structural dual-keying violation; it is an intentional, separate axis serving XSD export and form projection. The distinction:

- The dual-keying convention (D1–D2) governs the ENGINE and VERIFICATION layer: `casilla.id` is canonical semantic; `casilla.number` is documentary form-reference. These two always coexist for casillas that reach the engine.
- The XSD axis (Finding E) governs the EXPORT layer: `casilla.xsd_id` / `casilla.xsd_codes` are AEAT data-record tokens. They may coexist with id/number (dual-keying casillas that also export) or stand alone (XSD-only projections).

The three-shape predicate from #134 regression gate enforces that every casilla row conforms to one of these valid shapes:
1. **Dual-keying only** (id + number, no XSD): Engine casillas with no export responsibility.
2. **Dual-keying + XSD** (id + number + xsd_id/codes): Engine casillas that also project to XSD export.
3. **XSD-only** (xsd_id/codes, no id): Pure export projections (rare; form-layout padding, metadata fields).

Any row that introduces a fourth shape (e.g., XSD-only with a form-field number but no engine id, in violation of the XSD-only contract) is genuinely a defect and must be rejected. The gate implements this predicate in #134 as a structural test.

## Consequences

### Code surfaces affected

- Zero. The convention is already in place across the registry, the engine, and the verification chain. This ADR ratifies the existing shape and serves as a forward-reference for future predicate / formula authoring.

### Migration plan

- None required. The M303 2023-y-siguientes registry is on the convention. Older revisions (2009-y-siguientes) carry purely form-numbered ids in some places; those are revisions of a different vintage and are not in scope for this ADR (a separate cross-revision continuity ADR governs that boundary).

### Regression-test gate

- The three-shape predicate gate in regression #134 validates casilla structure across all modelo revisions: for every casilla row, assert that it conforms to one of three legal shapes (dual-keying only; dual-keying + XSD; XSD-only per Finding E / Decision D6). The gate rejects any row that violates the three-shape contract. Specifically:
  - **Dual-keying only shape**: `casilla.id` (semantic, engine-canonical) + `casilla.number` (form-page field or internal display). No XSD axis.
  - **Dual-keying + XSD shape**: `casilla.id` + `casilla.number` + `casilla.xsd_id` (or `xsd_codes`). The casilla participates in both engine and XSD export.
  - **XSD-only shape**: `casilla.xsd_id` (or `xsd_codes`) with NO `casilla.id`. Pure export projection; no engine participation.
  - **Invalid (rejected)**: Any other combination, including XSD-only rows that carry a `number` field, or rows that claim dual-keying shape but carry incomplete XSD data.
- This gate is implemented in regression test #134 as a structural predicate. Future casilla authoring must satisfy the predicate, not just the dual-keying convention in isolation.

### Future predicate / formula authoring discipline

- Any formula expression or verification predicate MUST reference casillas via their `casilla.id`. Authoring teams MUST NOT reference casillas via `number`. This applies to all modelos.
- Future cross-revision continuity work (per the schema-hardening-casilla-continuity-contract ADR) should respect the `aliases` field for revision-spanning identity, not the `number` field.

### Sibling impact assessment

- M130, M100, M200, M210, M131 already follow the same convention. Spot checks during this investigation confirmed no modelo deviates. The ADR is project-wide ratification of a project-wide convention; no per-modelo migration needed.
- The schema-hardening-casilla-continuity-contract ADR is the upstream cross-revision identity authority. This ADR is its within-revision sibling, governing the form-vs-semantic shape inside a single revision.

## Out of scope

- Cross-revision casilla identity tracking. Owned by the casilla-continuity-contract ADR.
- M303 2009-y-siguientes legacy revision. Form-numbered ids in that older revision are pre-convention authoring; revising them is a separate hardening pass not warranted while the older revision remains in maintenance-only mode.
- The partial #111 fix's actual root cause. The revert at `64baa15a6` preserved a green suite; identifying which downstream consumer broke during the rewrite is a separate investigation, not this ADR's scope.
- Task #126 M303 C65 profile-state-attribution-ratio binding. Independent root cause per D5.
