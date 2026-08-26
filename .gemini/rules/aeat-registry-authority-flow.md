---
name: aeat-registry-authority-flow
trigger: always_on
---

# AEAT registry authority, schema, identifiers and revision resolution

## The authority pipeline

Treat the modelo registry as a deterministic authoring-compiler pipeline:
TOML authoring tree → loader/compiler → strict schema objects → registry
validation → validated authority → immutable snapshots → runtime projections.

**`ValidatedRegistryAuthority` is the production orchestration boundary.**
Request validated modelos, deadline windows and snapshots through the authority
or a repository facade that owns one. Do not add production paths that call raw
loaders and then independently validate or select revisions.

**`_loader.py` is a compiler implementation detail.** Loader changes MUST
preserve deterministic merge order, reject ambiguous scalar conflicts, include
every read TOML file in cache invalidation, and compile fragments into the
existing strict runtime schema.

**Snapshot construction is authority-owned.** Filing schema providers, query
services, formula execution, export parsing and adapter projections consume
`RegistrySnapshot` or typed projections derived from snapshots — never fragment
paths or partially merged raw dictionaries.

**Invalidate any cache above the loader by the complete registry tree
fingerprint**, including directory-mode manifests and recursive revision
fragments. Never introduce a path-only registry cache that can serve stale TOML.

## Revision content is fragmented

A revision declares its sections — bindings, formulas, casillas, verification
expectations and predicates, constructs, completeness manifest — ONLY in
fragmented subdirectories. The fragment directory's `revision.toml` carries
scalar metadata only, and an inline section table is a hard `RegistryLoadError`.

**Assess coverage from the LOADED snapshot, never a directory listing.** To
decide whether a revision is calc-grade or a casilla is ledger-bound, load
through the authority and inspect the compiled schema; grep fragments only to pin
exact ids. A file-shape glob undercounts the same way — a pattern matching one
shape silently excludes directory-mode fragments, which can hold most of the
corpus. Assume fragmentation until you have checked; both shapes ship. Read a
binding's `source` field before classifying a blank: a `profile` binding absent
from a ledger sweep is not a ledger silent-zero.

## Regulatory values live in the config or the registry

All AEAT schema, constants, thresholds, regulatory codes and registry-shaped data
MUST be defined in the central config or the registry authoring tree — never
inlined as Python literals in feature modules. These values are versioned by
filing year plus revision, so a literal bakes the value into the call site,
scatters the authority, and silently drifts on a new revision.

Read regulatory values through the authority (`authority.snapshot(...)`) and
deployment settings through `load_settings()`, honouring `override_settings()`.
New thresholds, windows and constants land first in registry TOML. A one-line
import from the curated `core.external_constants` re-export layer is acceptable
for a true regulatory leaf constant.

**Acceptable exceptions:** pure mathematical or framework constants, the AEAT
control-letter table, sentinel zeros; and translation KEY literals — but literal
user-facing prose belongs in the locale files.

## Modelo identifiers are the core enum

Production code MUST reference modelo identifiers through the
`cadrumo.core.Modelo` StrEnum, never as bare three-digit string literals. An AST
gate enforces this; a genuine non-identifier occurrence (an article number, a
digit-set membership test, a CLI command-name token) is recorded in the gate's
allowlist with a stated reason.

Use the **bare member** in comparison, membership and dict-key positions; reserve
**`.value`** for plain-`str` contracts (pydantic field values, call arguments,
parameter and CLI-option defaults, returns). A `StrEnum` member compares, hashes,
`str()`s and JSON-serialises identically to its value, so the substitution is
behaviour-preserving.

A modelo that is code-referenced but has no registry definition (a retired form)
is added to the enum and listed in `NON_REGISTRY_MODELOS`, which the
registry-parity gate excludes.

## Revision resolution is law-determined, never injected

Every production calculation, verification, filing, export or projection path
MUST resolve its registry revision from `(modelo, filing_year, period)` through
`ValidatedRegistryAuthority.snapshot` / `select_revision`, or through
`law_selected_revision_for_work_target`, which takes exactly one
`RegistryAuthorityCapture` and delegates to the pure
`assert_work_target_revision`. A stored, literal or operator-supplied
`revision_id` may only be **asserted equal** to that resolution, never injected
as the selector; the requested and stored axes are judged independently against
the same capture, so neither can select the revision the other is judged by.

AEAT binds every triple to exactly one revision by publishing orden, so "which
revision applies" is a derived fact. Feeding a stored id back into resolution
makes the stored value *causal* — the defect class that lets one year's numbers
be computed under another year's norms. The non-overlap window gate guarantees
resolution is unique, so a narrowing can only equal the law-determined pick or
refuse.

**Carried observations stamp their revision and re-confirm it.** Every persisted
calculation observation MUST carry a required, non-empty law-determined
`stamped_revision_id`, and a missing or invalid stamp MUST refuse at strict load.
Every cross-period or cross-year carry MUST re-confirm a populated stamp against
`select_revision` for the source context before trusting the value; a divergent
or unreconfirmable stamp MUST block the carry. The carry path is the one place a
revision error *compounds across years*.

## Period boundaries have one authority

Every period-scoped selection resolves its date span through `Period.contains()`,
built from the canonical year plus the AEAT-token grammar. No call site may
implement a parallel boundary, an inclusion override, or a legacy period alias.
Re-derived start/end math creates off-by-one gaps, overlaps and inconsistent
handling of adjacent quarters; a continuity invariant keeps the boundary gap-free
and overlap-free.

## How

- **Good:** load the work unit, resolve the snapshot from its `filing_year` and
  `period`, then assert equality and raise an instructive refusal naming both
  revisions on mismatch. A creation-time `--revision` is accepted only when it
  names exactly the resolved id.
- **Good:** the producer persists the stamp from the law-selected snapshot it
  already holds; anti-tautology coverage deletes the persisted field and proves
  loading fails.
- **Good:** `if unit.modelo != Modelo.M303:` and `{Modelo.M100: ...}` use bare
  members; `modelo=Modelo.M720.value` for a `str`-typed field.
- **Good:** parse `--year 2026 --period 1T` to a `Period`, then filter with
  `period.contains(row.date)`.
- **Bad:** passing a stored `revision_id` into `authority.snapshot(...)` on a
  calculation path, so resolution is *selected* by the stored value.
- **Bad:** reconstructing, defaulting or bypassing a missing stamp; or treating a
  divergent stamp as a warning instead of a blocker.
- **Bad:** `if unit.modelo != "303":`; an inline
  `THRESHOLD = Decimal("3005.06")`; redeclaring period codes as bare-string sets.
- **Bad:** re-introducing a section table inline in a `revision.toml`, or
  `ls bindings/ | wc -l` as the sole signal of whether a revision is calc-grade.
- **Bad:** accepting an alternate boundary grammar (`2026Q1`, `ANUAL`, `Q1`), or
  open-coding `start <= row.date <= end` with locally derived dates.

Gates: `src/cadrumo/core/tests/test_modelo_string_usage.py`, `test_modelo.py`.
Source: ADRs `2026-07-02-arch-remediation-registry-format-adr`,
`2026-06-10-modelo-enum-hardening-adr`,
`2026-06-10-period-revision-resolution-adr`,
`2026-06-10-ledger-filter-period-adr`.
