---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity Code Review — #174 `_guard_casilla_data_type`

Commit `eef59339f` — guard `--casilla` against non-numeric `data_type` (Lourdes F4 root cause).

## Verdict: REVISION REQUIRED

---

## Critical-Question Answers

**CQ1 — `_NUMERIC_CASILLA_DATA_TYPES` completeness.**
The frozenset `{"decimal", "money", "integer", "ratio"}` is correct and complete against
the live schema. `CasillaDefinition.data_type` at `_schema.py:1593` is the authoritative
Literal. It enumerates: `decimal`, `money`, `integer`, `ratio`, `text`, `boolean`, `nif`,
`year`, `period_code`, `country_code`, `iban`, `name`, `nif_iva`, `ccaa_code`,
`province_code`, `postal_code`, `municipality_code`, `bic`, `date`. The TOML registry
also contains `bracket_table` (on `ParameterDefinition`, not `CasillaDefinition`).
No `percentage` or `signed_decimal` type exists anywhere in TOML or schema.
The frozenset admits exactly the four numeric types and excludes all identifier/descriptor
types. Set is complete.

**CQ2 — Guard runs after key normalisation.**
Confirmed. In `work_calculate` the sequence is: `_normalise_casilla_key` dict comprehension
(line 2164), then `_guard_casilla_data_type` loop (lines 2165-2166). Guard cannot see the
un-normalised alias; it only sees the canonical `CasillaId` string. Ordering is correct.

**CQ3 — Guard runs before engine; alternate silent-store path exists.**
In `work_calculate` (the primary command) the guard fires before the `Decimal()` conversion
loop and before the application-layer `calculate_work_unit` call. The guard is correctly
placed on this path.
However: `modelo_project` (line 3753) is a second CLI command that accepts `--casilla`
overrides and constructs `casilla_pairs` (line 3891) without calling
`_guard_casilla_data_type`. The M100 snapshot is available at line 3885; the revision
could be extracted. The identical silent-store hazard is unguarded on this path.
This is the HIGH finding below.

**CQ4 — Locale parity.**
`es.yml` and `en.yml`: fully translated with all three interpolation slots (`{key}`,
`{label}`, `{data_type}`) present and semantically correct.
`ca.yml`: fully translated. Catalan text is semantically equivalent, slots present.
`hu.yml`: uses the `cli.app.modelo.work.casilla_non_numeric_data_type` placeholder
pattern (delegates to the `es`/`en` fallback via the framework). This is consistent with
the existing `hu.yml` convention for this file (every other key in that section uses
the same delegation pattern). No missing locale; parity is adequate by convention, not
a defect.

---

## Findings

### GUARD-001 | HIGH | `modelo_project` `--casilla` path unguarded

`_guard_casilla_data_type` is not called in `modelo_project` (line 3891 of `_modelo.py`).
That command accepts `--casilla` overrides with the same semantics as `work_calculate`
and forwards `extra_inputs` directly into the M100 calculation engine.
The M100 snapshot is already resolved at line 3885 (`m100_snapshot`). The revision is
accessible from that snapshot. The guard should be called after key normalisation,
mirroring the pattern at lines 2164-2166. Without this fix the original silent-store
defect (Lourdes F4 root cause) remains reachable via `aeat app modelo project`.

### GUARD-002 | MEDIUM | `revision: object` type annotation is structural erasure

`_guard_casilla_data_type(casilla_id: str, revision: object)` uses `object` for the
revision parameter. The function accesses `.casillas` and iterates its members for
`.id` and `.data_type`. `ModeloRevision` is already imported in this module (returned
by `_casilla_revision_for_work_unit`). The parameter should be typed
`ModeloRevision` to make structural assumptions explicit and to allow type-checkers
to flag future callers passing incompatible types. This is the G2 boundary-typing
gate violation.

### GUARD-003 | LOW | Test asserts `"text"` string, not label

The regression test (`test_work_calculate_rejects_decimal_override_for_text_casilla`)
asserts `"0001" in result.output` and `"text" in result.output`. The commit message
states "names casilla id and 'text' data_type". Both assertions are present.
However, the diagnostic message also interpolates `{label}` (the casilla's human
label), which is a distinguishing element. The test does not assert that any
label string appears, so a future refactor that drops the label from the message
would not be caught. Non-blocking, but the test could assert a fragment of casilla
0001's known label to make the contract stronger.

---

## Standing Gates

- **G1 naked env reads:** No `os.environ` / `os.getenv` introduced. Pass.
- **G2 typed pydantic at boundaries:** `revision: object` is a type-erasure. See GUARD-002.
- **G3 `tr()` for user messages:** `tr("cli.app.modelo.work.casilla_non_numeric_data_type", ...)` used correctly. Pass.
- **G4 locale yml hand-edits:** Locale additions are present in all four files via the scaffold-consistent key position. The keys are inserted inline with surrounding structure at the correct alphabetical position. Consistent with scaffold output. Pass.
- **G5 no shims / duplication:** `_NUMERIC_CASILLA_DATA_TYPES` is a single frozenset defined once. No duplicates found in codebase. Pass on `work_calculate`; fail on `modelo_project` (GUARD-001).
- **G6 no tautological tests:** Test creates a real work unit, invokes the real CLI stack, asserts a non-zero exit, asserts no traceback, and checks for both `"0001"` and `"text"` in output. Not tautological. See GUARD-003 for a minor strengthening note.

---

## Required Actions

1. **GUARD-001 (HIGH, must fix before merge):** Apply `_guard_casilla_data_type` to the
   `casilla_pairs` path in `modelo_project`. After parsing `casilla_pairs` at line 3891,
   normalise keys against the M100 revision extracted from `m100_snapshot`, then call
   the guard for each resolved key. Add a regression test mirroring the `work_calculate`
   pattern for this command path.

2. **GUARD-002 (MEDIUM, fix recommended):** Change the signature from `revision: object`
   to `revision: ModeloRevision`. The import is already present.
