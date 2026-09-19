---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:06de00da7cd7ed2154440835a86b007be3ba4683830861c795be799b749fda6e'
related:
  - "[[2026-08-15-registry-campaign-sequencing-export-authority-key-enforcement-audit]]"
---

# `registry-campaign-sequencing` audit: `Export authority chain: reachability census`

## Scope

The prior enforcement audit confirmed a consumer EXISTS for each of the 14
keys on the export authority chain. This pass asks the harder question: for
each key, is the consumer actually REACHED on every path that depends on it,
or is there a filter, early return, guard precondition, or enumeration
mismatch that lets a real declared value bypass the check it appears to have?
The named prior-art shape (`_designs_claimed_by`/`_boundaries_for` missing
51/209 and 62/174 real design files because their enumeration's glob shape
didn't match the corpus's actual shape) was read first to calibrate what to
hunt for: not "does the function exist" but "does the function's own
enumeration or filter see every real instance."

Traced by reading the actual validator/selector functions and their callers,
cross-checked against the real on-disk registry tree (`find`/`grep`, not
inference from docstrings), never from `bundled_authority()` since it refuses
at load by operator ruling. Per key below, the table states whether the full
path was traced or only a consumer confirmed to exist, per the assignment's
instruction. `.vault/audit/**` only; nothing committed; no source touched.

## Findings

### Export authority chain: reachability census | critical | Denominator: of 14 keys, 11 have their consumer traced full-path-reachable, 1 has a confirmed-dormant reachability gap, 2 were corrected mid-trace after their previously-named "consumer" proved unreached in production

| Key | Consumer traced full path? | Verdict |
|---|---|---|
| `ModeloRevision.id` | Yes | Reachable — every revision directory is walked by the loader; pydantic validates on parse |
| `Revision.source_refs[*]` | Yes | Reachable — `_missing_refs` runs unconditionally per revision inside `validate_revision_definition`, itself called for every `modelo.revisions.values()` |
| `SourceReference.kind` | Yes | Reachable — schema `Literal`, validated on every catalogue-file parse; `legal/*.toml` is flat (no nested subdirectory a non-recursive glob could miss) |
| `SourceReference.corpus_path` | Yes | Reachable — `verify_source_catalogue` walks `sources.values()` unconditionally; see finding 3 for the one guard that looked risky and was traced clear |
| `SourceReference.sha256` | Yes | Reachable — same unconditional walk, real byte-hash via `hash_file`, not a declared-value comparison |
| `SourceReference.record_design_epoch` | Yes, corrected mid-trace | See finding 2 — the specific consumer the prior audit credited is unreached in production; the real production consumers use it as a bare non-null filter, not a value check |
| `ExportRecordDefinition.id` | Yes | Reachable — schema pattern, and `_check_casilla_refs`-style checkers walk every record unconditionally |
| `ExportRecordDefinition.record_type` | Yes | Reachable — one consumer, unconditional string compare, no filter to bypass |
| `ExportRecordDefinition.binding_record` | Yes | Reachable — `_validate_export_record_binding_link` runs whenever `binding_record is not None`, which is the correct condition, not a gap |
| `ExportFieldDefinition.id` | Yes | Reachable — schema pattern; every field in every record in every layout is walked unconditionally (see finding 4) |
| `ExportFieldDefinition.casilla_id` | Yes | Reachable — `endpoint_casilla_id` returns `self.casilla_id` first whenever it is set, never silently substitutes a different value; both directions checked (field->casilla AND casilla->field, finding 4) |
| `ExportFieldDefinition.kind`/`data_type`/etc (7 fields) | Yes (schema only) | Reachable by construction — pydantic validates on every parse; not independently re-traced beyond the loader-reachability finding below, which applies uniformly |
| `CasillaDefinition.export_refs` | Yes | Reachable — `checker.chk_tuple(..., casilla.export_refs, checker.export_field_ids)` closes the reverse direction (dangling ref caught); see finding 4 |

**The one real gap found is structural, not per-key**: finding 1 below. It is
currently dormant against the live tree (confirmed empirically, not assumed),
but it is a genuine mismatch in the loader's own fragment-collection
mechanism that would affect ANY of the section-scoped keys above the moment a
fragment is nested one directory level deeper than today's tree ever nests
them.

### Export authority chain: reachability census | high | The loader's non-emptiness GUARD and its fragment COLLECTOR use different glob depths — the guard can pass on a shape the collector cannot see

`src/cadrumo/domain/calculations/registry/_loader.py`:

- `_require_revision_section_fragments` (the guard that refuses an empty
  section directory) checks `section_dir.rglob("*.toml")` — RECURSIVE.
- `_revision_section_fragment_paths` (the function that actually collects the
  TOML fragments to merge into the compiled revision) checks
  `section_dir.glob("*.toml")` — NON-recursive, one level only.

If a revision section directory (`casillas/`, `bindings/`, `export_layouts/`,
`formulas/`, etc.) ever nested its TOML fragments one directory level deeper
than today — the exact shape the `aeat-registry-authority-flow` rule already
warns about for a different reason ("a pattern matching one shape silently
excludes directory-mode fragments") — the guard would find the nested files
via `rglob` and pass silently (reporting the section non-empty, correctly),
while the collector's non-recursive `glob` would never see them: every
casilla, binding, export record or field declared inside that nested
subdirectory would be silently absent from the compiled revision, with **no
error at any tier** — not a `RegistryLoadError`, not a validation failure,
because the content the validators would check against never entered the
compiled structure to begin with. This is the exact shape of the
`_designs_claimed_by` class: a guard exists, the guard is satisfied, and the
guard's satisfaction is read as proof the collector saw everything, when it
is not.

**Confirmed dormant against the real tree, not assumed:** walked every
`revisions/*/**/*.toml` path under `src/cadrumo/_data/registry/aeat/modelos/`
and found the maximum nesting depth inside any section directory is exactly
one file-level (`section_dir/*.toml`); zero files exist at
`section_dir/*/*.toml` anywhere in the bundled tree, in `export_layouts/` or
any other section. Every key that lives inside a revision section
(`ExportRecordDefinition.*`, `ExportFieldDefinition.*` via `export_layouts/`,
and `CasillaDefinition.export_refs` via `casillas/`) is reachable TODAY only
because no author has yet organised a section with a nested subdirectory —
not because the loader would catch it if one did.

### Export authority chain: reachability census | high | AMENDS the prior audit's finding on `record_design_epoch`: the consumer credited with pairing the epoch to a canonical anchor is unreached in production; the real production selectors treat the epoch as a bare non-null filter, never a value check

The prior enforcement audit (finding 2) named `resolve_record_design_binary`
(`_corpus_catalogue.py:67`) as one of four traced consumers, and characterised
`record_design_epoch` as always used "as a SECONDARY consistency assertion...
never as the SOLE or PRIMARY selection key," with every mismatch failing
closed. **That characterisation was built on a function that has no
production caller.** Grepped every reference to `resolve_record_design_binary`
in the tree: it is exported from the package facade
(`registry/__init__.py:288,1305`) but every actual call site is a test module
(`test_record_design_source_selection.py`, `test_record_design.py`,
`test_modelo_303_exonerado_390_endpoints.py`, and others) — zero call sites in
`application/`, `domain/modelos/`, or any non-test `domain/calculations/`
module. The epoch-equality raise (`if source.record_design_epoch !=
design_epoch: raise`) that grounded the "fails closed" claim is proven, real,
and passes its tests — but it never executes when a real filing runs.

Traced what DOES run in production instead, three independent selector
functions that each re-implement "find the one record-design source that
qualifies," none of which call `resolve_record_design_binary` or perform its
epoch-equality check:

- `_m303_orden_resolution.py:_unique_active_record_design` (called from
  `resolve_m303_regimen_simplificado_snapshot`, the production entry point
  for M303 régimen simplificado, itself called from
  `application/calculations/_m303_regimen_simplificado.py:34`) — filters
  `sources.values()` on `kind == "record_design"`, `id in
  revision_source_refs`, `record_design_epoch is not None`, and an
  `applies_from`/`applies_to` DATE WINDOW. The epoch's literal string value
  plays no role beyond non-nullness; the date window is the real selector.
- `_m303_orden_manifest.py:_annual_orden_record_design_source` (the annual
  Orden compiler, reached from `compile_supplementary_ordenes` at
  `_authority.py:446`, unconditional for every registry build) — same shape:
  `kind == "record_design" and record_design_epoch is not None`, no value
  comparison.
- `_m303_orden_projection_models.py`'s snapshot-invariant checks — pin a
  LITERAL `"2022"` for one specific historical revision's own assertion, not
  a general epoch-value check applicable to other revisions.

**Where the value actually goes once selected:** traced
`application/calculations/_m303_regimen_simplificado.py:88-100` — after
selection, `record_design.record_design_epoch is None` is checked (raise if
absent) and then the epoch string is stamped VERBATIM into the persisted
`M303RegimenSimplificadoCalculationResult.record_design_epoch` field with no
further validation — this result feeds `_calculation_revision_m303_evidence.py`
and `_calculation_revision_m303_handoff.py`, both of which carry the epoch
into calculation-revision evidence. **The value reaches a filed artefact
having been checked for presence only, never for shape or correctness,
anywhere on the traced production path.**

**Corrected verdict, replacing the prior audit's "bounded, paired with a
canonical anchor" framing:** the "nothing enforces the convention" premise
was always right; what was wrong was the claim that today's consumers happen
to pair it defensively. They do not — they gate on presence and then trust
the date-window selection to have picked correctly, and the selected epoch
string is carried through to a filed evidence record unchecked. This does not
change the earlier conclusion that byte-level file integrity is still real
(the catalogue-wide `verify_source_catalogue` hash-check at registry build
time, confirmed reachable in finding 3, is unconditional and independent of
which selector picks which source) — but the epoch VALUE specifically is
weaker than previously stated: a wrong-but-non-blank, wrong-but-syntactically-
plausible epoch string on a `SourceReference` whose `applies_from`/
`applies_to` dates are still correct would sail through every traced
production selector and land in a filed record unexamined.

### Export authority chain: reachability census | info | `verify_source_catalogue`'s `source_root is not None` guard looked like a silent-skip risk; traced clear

`RegistryValidator.__init__` defaults `source_root: Path | None = None`, and
`_validate_catalogues` only calls `verify_source_catalogue` (the byte-hash
sweep over every declared source) `if self._source_root is not None:` — a
shape that would silently skip ALL corpus-integrity checking if the default
were ever exercised in a production path. Traced every non-test
`RegistryValidator(...)` construction site (`_snapshot.py:248`,
`_handoffs.py:251`, `_coverage.py:330,417`, `_authority.py:471`): every one
passes `source_root=` explicitly. Traced `_authority.py:471` up to
`bundled_authority()` (`_authority.py:318-330`): `ValidatedRegistryAuthority.
load(root, source_root=_bundled_path())` — `source_root` is a REQUIRED
keyword parameter on `.load()` with no default, always a real path in the
bundled/production authority. **The `None` default on `RegistryValidator`
exists but is dead in every production call site** — confirmed by reading
every call site, not inferred from the type signature. `SourceReference.
corpus_path` and `.sha256` are reachable as stated in the enforcement audit.

### Export authority chain: reachability census | info | `casilla_id` / `export_refs` bidirectional cross-reference confirmed reachable in both directions, unconditionally

Traced `validate_export_layout_section` -> `_validate_export_record` ->
`_validate_export_field` -> `_validate_export_field_references`
(`_validate_exports.py:64-510`): every layout, every record, every field is
walked with plain `for` loops, no filter that could skip a declared field.
`ExportFieldDefinition.endpoint_casilla_id` (`_schema_exports.py:230-236`)
returns `self.casilla_id` FIRST whenever it is set — the fallback to
`projection_ref`-derived resolution only fires when `casilla_id is None` —
so a declared `casilla_id` is never silently bypassed by the property. The
reverse direction (does every id a casilla lists in `export_refs` correspond
to a real field) is checked separately: `_validate_references.py:123`,
`checker.chk_tuple(f"{cp}.export_refs", casilla.export_refs,
checker.export_field_ids)`, inside `_check_casilla_refs`, itself called
unconditionally for `for casilla in revision.casillas` inside
`revision_reference_identity_failures`, itself called unconditionally inside
`validate_revision_definition` for every revision. Both directions of the
`ExportFieldDefinition.casilla_id` <-> `CasillaDefinition.export_refs`
relationship are reachable; no grade-gating, no early return, no filtered
enumeration found on this path.

## Recommendations

**Ranked by whether a skipped consumer means a wrong artefact reaches the
operator, rather than merely a missing check:**

1. Finding 2 (`record_design_epoch`'s real production selectors) ranks
   highest: a wrong-but-plausible epoch string on an otherwise-valid
   `SourceReference` reaches a persisted filing-evidence field with zero
   value-level check anywhere on the traced production path. This is a
   correction to the prior audit's conclusion, not merely a new datum — the
   prior "bounded by pairing with a canonical anchor" framing should be
   treated as retracted for the production path (it remains an accurate
   description of the test-only `resolve_record_design_binary`, which is
   real code and passes real tests, just unreached). Closing this needs
   either routing the three production selectors through
   `resolve_record_design_binary`'s epoch-equality check (making the
   currently-unreached safety net reached), or adding an explicit
   epoch-value assertion at the point the selected source's epoch is stamped
   into `M303RegimenSimplificadoCalculationResult`.
2. Finding 1 (the loader's `glob`/`rglob` mismatch) ranks second: confirmed
   real and confirmed dormant. It is a latent structural gap rather than a
   currently-biting one, but it is a ONE-LINE fix
   (`section_dir.rglob("*.toml")` in `_revision_section_fragment_paths` to
   match its own guard) that removes an entire class of "declared, guard
   passed, content silently absent" risk for every future section fragment
   across casillas, bindings, export_layouts, formulas and every other
   revision section — not scoped to the export chain alone.
3. Findings 3 and 4 need no action: both looked, on first read, like exactly
   the shape this census was assigned to find (an unconditional-seeming
   guard hiding a silent skip, a property indirection hiding a substitution)
   and both traced clear on the real call graph. Recorded so a later reader
   does not have to re-derive the trace from scratch.
4. This pass traced the 14-key denominator from the prior audit; it did not
   extend to every other consumer of `SourceReference`/`ExportRecordDefinition`
   in the tree (e.g., the export-format-specific generators beyond the
   validators, or the M100 XML-dictionary path noted in the prior audit's
   finding 4). If a reachability census of the generation-time consumers
   (not just the build-time validators) is wanted, it is a distinct pass.
