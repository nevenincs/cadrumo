---
tags:
  - '#audit'
  - '#export-import-fidelity-swarm'
date: '2026-05-16'
modified: '2026-05-16'
related: []
---



# `export-import-fidelity-swarm` audit: `Export/import fidelity`

## Scope

Audited operator-facing export/import surfaces across the AEAT codebase for fidelity loss across wire-format boundaries. Examined:

1. **Fichero-BOE TXT format** (`src/aeat/adapters/outbound/aeat/export/_formats/`): Field encoders (`_serialise.py`), decoders (`_deserialise.py`), and record specs for FieldKind parity (CURRENCY, DATE, ALPHANUMERIC, NUMERIC, RESERVED).

2. **Workbook xlsx parity** (`src/aeat/application/storage/calc_sheets/`): `SheetExportPlan` structure, apply adapter field coverage, and pull adapter read-back completeness.

3. **Google Sheets pull/apply adapters** (`src/aeat/adapters/outbound/google/`): `apply_export_plan`, `compute_from_pull`, and round-trip boundary integrity.

4. **AEAT inbound capture** (`src/aeat/adapters/inbound/`): Inbound record schemas and field completeness against source authority.

## Findings

### 1. Sentinel Value Collision in CURRENCY Fields (High Impact)

**Location**: `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py:108` and `_deserialise.py:71-95`.

**Issue**: CURRENCY fields default to `Decimal("0.00")` when missing from operator input (`casilla_values.get(spec.casilla_id, _ZERO)`). The zero-padded encoding produces `b"0000000000000"` for a 13-byte field. On deserialization, the bytes decode identically for both an actual zero value and an unset/empty field. This creates an **irrecoverable ambiguity**: the deserializer cannot distinguish whether the operator intentionally entered zero or the field was never populated.

**Evidence**: The encode/decode path has no sentinel or marker to disambiguate. `_decode_currency` returns `Decimal("0.00")` for both cases. Inbound AEAT capture (e.g., justificante parsing) likely encounters real casilla values that may legitimately be zero; exporting and re-importing loses the "was this supplied by the operator?" metadata.

**Test Coverage Gap**: `test_currency_edge_cases.py` covers zero encoding but does NOT test round-trip fidelity with absent-vs-zero distinction.

---

### 2. Relation Provenance Metadata Written But Not Read Back (High Impact)

**Location**: Apply writes to `_build_developer_metadata_requests()` at `src/aeat/adapters/outbound/google/_calc_sheets_apply.py:573-591`. Pull does not read it.

**Issue**: The apply adapter writes relation provenance (value, provenance tier, source_filing_year, resolved_at) into spreadsheet developer metadata with keys like `aeat_relation:{relation_id}`. The pull adapter (`src/aeat/adapters/outbound/google/_calc_sheets_pull.py`) reads relation values from the Tarifas tab cells directly but **does not parse or recover the developer metadata**. This causes **data loss**: stale relation prefills (marked with `provenance="operator_manual"` or missing `resolved_at`) cannot be detected on pull, violating the audit trail contract.

**Evidence**: `PullResult` carries a `relation_edits` tuple with bare `(relation_id, value)` pairs. `RelationEdit` has no `provenance` or `resolved_at` field. The metadata is written but orphaned.

**Test Coverage Gap**: `test_worksheet_export_pull_roundtrip.py` constructs `RelationEdit` records with hardcoded `value=Decimal("0")` and does not verify provenance recovery.

---

### 3. NUMERIC Field Stripping Ambiguity in Deserializer (Medium Impact)

**Location**: `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py:181-187`.

**Issue**: NUMERIC fields are right-justified, zero-padded. On deserialization, `text.lstrip("0")` strips all leading zeros; an all-zero field `"0000"` becomes empty string, then normalizes to `"0"`. This is correct but creates a **visual silent loss**: the wire-format information that the field was padded (eight zeros, not one) is lost. If a downstream consumer expects the raw padded value for audit purposes, they cannot recover it from the parsed record (they see `"0"` not `"00000000"`). CURRENCY fields do NOT normalize, so there's an inconsistency.

**Evidence**: Compare handling in `_decode_currency` (returns `Decimal("0.00")` for empty/all-zeros) vs. NUMERIC deserialization (normalizes to `"0"`). Asymmetry suggests incomplete specification.

**Test Coverage**: Covered by `test_fichero_boe_roundtrip.py` but test does not validate that an all-zero NUMERIC field round-trips the intended semantic (is it "zero" or "absent"?).

---

### 4. CP1252 vs. ISO-8859-1 Encoding Inconsistency in Field Specs (Medium Impact)

**Location**: `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py:39`, `_serialise.py`, `_deserialise.py`.

**Issue**: Registry-backed export layouts declare `FicheroBoeEncoding` as `Literal["cp1252", "iso-8859-1", "iso-8859-15"]`. The comment notes that AEAT treats Windows-1252 and ISO-8859-1 as equivalent for fichero-BOE, but the codebase accepts all three and passes them directly to `.encode(encoding)` and `.decode(encoding)`. If a registry layout mistakenly declares `"iso-8859-15"` for a field containing a Euro character (0xA4), and the operator's system uses a different encoding on import, silent character corruption occurs. **No validation** checks that the encoding choice is consistent with the field content or that the registry's encoding declaration matches AEAT's actual published spec for the model year.

**Evidence**: No canonical registry mapping of (modelo, year, field_id) → approved encoding. The code delegates to the registry and trusts it.

---

### 5. SheetExportPlan Field Coverage Not Validated at Pull Boundary (Medium Impact)

**Location**: `src/aeat/application/storage/calc_sheets/_records.py:446-461` defines `SheetExportPlan`; apply writes most fields but pull reads back incomplete projection.

**Issue**: `SheetExportPlan` carries:
- `metadata`, `value_cells`, `formula_cells`, `tariffs`, `provenance`, `protected_ranges`, `cell_constraints`, `row_sets`, `relation_provenance`, `guide`.

Apply adapter writes all of them. Pull adapter's `compute_from_pull` receives a `PullResult` with only:
- `operator_edits`, `binding_edits`, `relation_edits` (from Tarifas cells), `row_set_edits` (from Detalle), `metadata`.

The pull adapter **does not read back**:
- `tariffs` (parameter bracket tables) — values are not validated against the export plan.
- `provenance` rows (audit trail) — no checksum or validation.
- `protected_ranges` — not checked at pull time.
- `cell_constraints` (validation rules) — operator edits are not validated against constraints.

A corrupted or manually-edited workbook could have constraints stripped or tariff tables altered with no detection.

---

### 6. Inbound Declaración Schema Missing Field Provenance (Low-Medium Impact)

**Location**: `src/aeat/adapters/inbound/declaracion/_schema.py:76-105` and `src/aeat/adapters/inbound/borrador/_schema.py:56-98`.

**Issue**: `DeclaracionObservation` and `BorradorObservation` carry `values: tuple[ExtractedCasilla, ...]` but no `extraction_config` or `registry_profile_version` marker. When an operator imports a filed declaración and the AEAT template subsequently changes (casilla renumbering, new/deleted fields), there is no automatic way to detect that the imported PDF predates the registry change. A mismatch could cause silent casilla misalignment.

**Evidence**: `TemplateRevision` pins (modelo, año, revision) but not registry snapshot identity. An AEAT 2024 orden update could change casilla topology; if the operator files a 2025 declaration from 2024 AEAT templates, the boundary record has no signal of the mismatch.

---

## Recommendations

1. **Sentinel Value for Unset CURRENCY Fields**: Introduce an optional marker in the wire format or metadata to distinguish actual-zero from unset. Consider a reserved field or a parallel validity bitmap. Update `_serialise.py` and `_deserialise.py` to preserve and check the marker. Add test case in `test_fichero_boe_roundtrip.py`.

2. **Recover Relation Provenance on Pull**: Extend `PullResult` and `RelationEdit` to carry `provenance`, `source_filing_year`, and `resolved_at`. Parse `aeat_relation:*` metadata keys in `_read_developer_metadata`. Update `test_worksheet_export_pull_roundtrip.py` to verify round-trip parity of provenance fields.

3. **Normalize NUMERIC Field Handling**: Update `_deserialise.py` to document whether a padded all-zero NUMERIC is "zero" or "absent". Align behavior with CURRENCY (which now returns `Decimal("0.00")`). Add test validating the semantic after normalization.

4. **Lock Encoding Choice in Registry**: Add a registry-level validator ensuring each model-year declares one encoding and no field contradicts it. Emit a lint error if multiple encodings are declared. Update the registry loader to validate and cache the choice per snapshot.

5. **Add Pull-Side Validation**: Extend `compute_from_pull` to optionally receive the original `SheetExportPlan` and validate:
   - No tariff/constraint cells were dropped or modified.
   - Row-set column count matches the export plan.
   - Protected range footprint is intact.

6. **Ground Inbound Declaración to Registry Snapshot**: Add a `registry_snapshot_version` or `registry_sha` field to `DeclaracionObservation`. When parsing a filed declaración, capture the AEAT template publish date and cross-check against the active snapshot. Log warnings if the template is stale.


