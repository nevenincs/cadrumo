---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:57bbfaecf00a79042c5e6737609c46126fc86fd0c4476e1e51b734767244f4e2'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
---

# `registry-campaign-sequencing` audit: `Export authority chain: canonical keys and enforcement`

## Scope

Every key on the operator-named chain — revision → `record_design` source →
`corpus_path` and hash pin → `record_design_epoch` → export layout → records
→ fields → `casilla_id` / `export_refs` — read from its schema declaration
in `src/cadrumo/domain/calculations/registry/_schema*.py`, then traced
forward to its real consumers (validators, resolvers, generators) rather
than judged from the declaration alone. Every consumer function named below
was opened and read; none is inferred from a caller's docstring. Worked at
the loader/schema tier throughout, since `bundled_authority()` refuses at
load by operator ruling.

This pass covers the source-identity half of the chain
(revision/source/corpus/hash/epoch) and the export-structure half
(layout/record/field/casilla) in full. It does NOT re-derive a full
reachability census comparable to tonight's `_designs_claimed_by`/
`_boundaries_for` findings for every key — that would need its own pass at
that scale — but does trace real consumers for every key reported below,
and says so per finding.

## Findings

### Export authority chain: canonical keys and enforcement | critical | THE DENOMINATOR: 14 keys traced, 10 canonical/typed, 4 free-form, 0 wholly unenforced, 1 with no shape or uniqueness check on the value itself

| Key | Type shape | Canonical? | Build-time enforcement | Traced consumers |
|---|---|---|---|---|
| `ModeloRevision.id` | `RevisionId` (pattern-validated) | Yes | Schema | Yes |
| `Revision.source_refs[*]` | `SourceRefId` (pattern-validated) | Yes | Schema + catalogue lookup | Yes |
| `SourceReference.kind` | `Literal[...]` closed set | Yes | Schema | Yes |
| `SourceReference.corpus_path` | bare `str` | Partial | POSIX-shape + extension-whitelist validator (`record_design` kind only) + real-file existence + hash cross-check | Yes |
| `SourceReference.sha256` | `ContentDigest` = `Hex64Str` (pattern) | Yes | Cross-checked against the ACTUAL file bytes (`verify_source_file`/`hash_file`), not merely declared | Yes |
| `SourceReference.record_design_epoch` | bare `str`, min/max length only | **No** | Presence-consistency only (must accompany `kind="record_design"`, non-blank); **no pattern, no year-shape check, no cross-source uniqueness check anywhere in `_validate*.py`** | Yes |
| `ExportRecordDefinition.id` | `RecordId` (pattern-validated) | Yes | Schema | Yes |
| `ExportRecordDefinition.record_type` | bare `str` | **No** | None beyond schema-level `str` | Yes, exactly one production consumer |
| `ExportRecordDefinition.binding_record` | `str \| None`, non-empty only | **No** | Cross-validated at build time against real binding selectors (`_validate_export_record_binding_link`) — refuses if no binding's `selector.record` matches | Yes |
| `ExportFieldDefinition.id` | `ExportFieldId` (pattern) | Yes | Schema | Yes |
| `ExportFieldDefinition.casilla_id` | `CasillaId` (pattern) | Yes | Schema + cross-reference validation | Yes |
| `ExportFieldDefinition.kind`/`data_type`/`padding`/`justification`/`value_policy`/`producer_key`/`computed_key` | Enums / `Literal` (7 fields, counted as one row) | Yes | Schema | Yes (spot-checked `producer_key`/`computed_key` against earlier session work) |
| `CasillaDefinition.export_refs` | `tuple[ExportFieldId, ...]` | Yes | Schema | Yes |

**Denominator: 14 distinct keys on the named chain (counting the 7-field
enum cluster as one row for space). 10 are canonical/typed by the project's
own standard (validated pattern or closed enum). 4 are genuinely free-form
strings: `corpus_path` (partially constrained), `record_design_epoch`,
`record_type`, `binding_record`. Of those 4, three ARE enforced at build
time by a real cross-check against something independent of the string
itself (file existence+hash, or a matching binding selector). Exactly ONE —
`record_design_epoch` — has no enforcement of its own SHAPE or of
uniqueness across sources: nothing stops two unrelated `SourceReference`
rows from declaring the same epoch string, and nothing stops a
non-year-shaped value (a document-version suffix, the exact case the
operator's peer worried about) from being accepted.**

### Export authority chain: canonical keys and enforcement | high | `record_design_epoch` is the confirmed unenforced case — but traced consumers bound the risk to spurious refusal, not silent wrong-selection, in every path checked

Confirmed exactly what was suspected: `record_design_epoch: str | None =
Field(default=None, min_length=1, max_length=128)` in `_schema_references.py`
carries no pattern, no enum, no uniqueness constraint. Grepped every
production reference (10 total, all read) rather than trusting the schema
declaration alone.

**What the trace found, precisely, because the premise deserves checking
rather than assuming the worst case:** in every one of the four real
consumer sites read (`_corpus_catalogue.py`'s `resolve_record_design_binary`,
`_m303_orden_manifest.py`, `_m303_orden_resolution.py`, and
`_m303_orden_projection_models.py`'s snapshot-invariant checks),
`record_design_epoch` is used as a SECONDARY consistency assertion
alongside a canonical anchor — the source's own `id` (`SourceRefId`,
pattern-typed and dictionary-keyed) and/or its `sha256` hash pin (verified
against real file bytes) — never as the SOLE or PRIMARY selection key. The
lookup that actually SELECTS a source is always keyed by `source_ref`
(canonical); the epoch match is then asserted (`!=` raises, `==` is
required alongside id+hash together) as a belt-and-suspenders check that
the resolved thing is what was expected. A malformed, inconsistent, or
mismatched epoch string, in every path traced, produces a hard
`RegistryValidationError` refusal — never a silent substitution of the
wrong design.

**What this does NOT establish, stated precisely:** this is 4 consumer
sites, not an exhaustive census of every reference to this field in the
tree, and it does not rule out a FUTURE consumer selecting by epoch alone
without a paired `source_ref`/hash anchor — nothing in the schema prevents
that shape from being written tomorrow, since the field itself carries no
enforcement. The uniqueness gap is real and unproven-safe: two
`SourceReference` rows COULD declare the same `record_design_epoch` string
today with nothing refusing it, and while none of the traced consumers
would currently be confused by that (they all resolve by `source_ref`
first), an untraced consumer might not.

**Verdict: confirmed free-form and confirmed unenforced on its own
terms — the "nothing enforces the convention" premise holds exactly as
stated — but the severity is bounded, not "silently selects the wrong
design," based on what four real consumers actually do with the value.** A
build-time pattern check (year-shape) plus a per-modelo uniqueness check
across `record_design_epoch` values would close the gap on its own terms
rather than relying on every future consumer independently re-deriving the
same defensive pairing this session's traced consumers happen to use.

### Export authority chain: canonical keys and enforcement | low | `binding_record` and `record_type` — both free-form, one enforced by cross-reference, one narrow and low-consequence

`ExportRecordDefinition.binding_record` (`str | None`) is genuinely
free-form at the schema level but IS enforced: traced to
`_validate_export_record_binding_link` in `_validate_exports.py`, which
walks every binding on the revision, resolves each one's export selector,
and requires at least one `selector.record == record.binding_record` match
— a revision where this key doesn't resolve to a real binding refuses at
build time (`"derives fields from unknown binding record"`). The
`.get(record.binding_record, [])`-shaped lookup this key feeds
(`_export.py:132`) looked, in isolation, like a silent-default risk (a
`dict.get` with a fallback empty list rather than a raise), but the build
validator closes that gap independently before such a mismatch could reach
generation.

`ExportRecordDefinition.record_type` (`str`) is free-form and has exactly
ONE production consumer: `application/filing/_export_parity.py:159`,
comparing against one hardcoded sentinel constant to identify the DID
(domiciliation) page record specifically. A typo or drift here fails
closed (the special case silently does not fire) rather than misdirecting
data. Narrow blast radius, traced not assumed, low priority.

### Export authority chain: canonical keys and enforcement | info | The historical "declared but not enforced" shape (no-op completeness gate on a missing layout) is CONFIRMED FIXED on the export path, not still open

Checked the exact site CONTINUITY.md names as the historical enabling
mechanism — `_fixed_width_addressed_casillas` in
`_validate_export_exemption.py` — since the operator's directive
("mandating that export authorities... are all being enforced") is exactly
what this function's history is about. The function's early-return-on-None
shape (`if not layouts: return None`) still exists verbatim, but it is no
longer reachable as a no-op: `validate_export_exemption_declarations`, its
caller, now checks `if not derive_export_layouts_from_bindings(revision):
failures.append(...); return` FIRST, unconditionally refusing any revision
that emits nothing at all, BEFORE the completeness-manifest/addressed-casilla
scan is ever reached. The function's own docstring names the historical
defect explicitly and states the fix's shape ("no allowance, no allowlist
and no per-modelo exemption"). `_fixed_width_addressed_casillas` returning
`None` today is reachable only for a revision that HAS a real export layout
but none of it is fixed-width (the XML-dictionary case, e.g. Modelo 100) —
a legitimately different, non-no-op state, not the historical hole. Read
the fix in full rather than trusting the docstring's claim on its own word.

## Recommendations

**Ranked by whether a wrong or absent value reaches a filed artefact**, per
the assignment's ordering:

1. `record_design_epoch` (finding 2) ranks highest of the free-form keys
   despite the bounded-risk trace, because it is the one place on this
   chain where the schema itself asserts nothing about the value's shape
   or uniqueness — every safety property found here is a property of how
   TODAY's four consumers happen to use it, not a guarantee the schema
   makes. Add a build-time pattern check (year, or year-plus-qualifier
   shape) and a per-modelo uniqueness check across declared epochs, so the
   convention the operator's peer derived from evidence becomes something
   nobody can violate by accident, matching this campaign's own standing
   bar for every other identifier on this chain.
2. `binding_record` and `record_type` (finding 3) do not need schema
   hardening with the same urgency — `binding_record` is already
   cross-validated, and `record_type` has one narrow, fail-closed consumer
   — but promoting both to `RecordId`-shaped or enum-typed fields would
   remove the "free-form that happens to work" residue the operator's
   directive is about, at low cost.
3. The historical no-op completeness gate (finding 4) needs no further
   action — confirmed fixed, reachable, and enforced. Recorded here so a
   later reader does not re-open it on the strength of CONTINUITY.md's
   historical description alone, which describes the PRE-fix state.
4. This pass did not extend the reachability census (the `_designs_claimed_by`/
   `_boundaries_for` shape) to the export-structure half of the chain
   (layout → records → fields) beyond confirming each field's consumers
   exist and were traced. If a fuller reachability audit of that half is
   wanted, it is a distinct pass at the same scale as tonight's relayout
   work, not something this audit's budget covered.
