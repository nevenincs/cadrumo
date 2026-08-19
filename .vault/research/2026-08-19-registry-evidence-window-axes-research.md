---
tags:
  - '#research'
  - '#registry-evidence-window-axes'
date: '2026-08-19'
modified: '2026-08-19'
body_schema: 'body-v1'
body_hash: 'sha256:8a972df20c015ef10ac87db8f7d2100c92710403c73ebb7621d6d12bd58f2f9b'
related: []
---
# `registry-evidence-window-axes` research: `evidence windows are validated on the axis the citation defends`

The registry validates every evidence citation against the *revision's* own date
span. Two defect reports traced to one cause: the span a citation is checked
against is not always the span that citation has to defend. One case is now
fixed; the second is open and needs a ruling, because the obvious "fix"
fabricates grounding.

## Findings

### A filing deadline lawfully falls outside the period it closes

`_check_revision_scoped_source_windows` in
`src/cadrumo/domain/calculations/registry/_snapshot.py` intersected every
revision-scoped `source_ref` with the revision's `[valid_from, valid_to]`. A
fourth-quarter return is filed in the January of the following year, so the
calendario stating its deadline is the following year's, and the check rejected
it.

Three revisions, authored independently, carried the same lawful citation:

| revision | cites | window it grounds |
|---|---|---|
| 123 / 2019-2023 | `aeat-calendario-contribuyente-2024` | 2024-01-01 .. 2024-01-22 |
| 131 / 2019-2023 | `aeat-calendario-contribuyente-2024` | 2024-01-01 .. 2024-01-30 |
| 180 / 2019-2022 | `aeat-calendario-contribuyente-2023` | 2023-01-01 .. 2023-01-31 |

Three authors reaching the same citation is evidence of a lawful pattern, not a
shared mistake. The refusal blocked `python -m dev.registry.conformance report`
outright, so the whole conformance surface was unreachable.

Re-citing the prior year's calendario would have silenced it while making the
grounding false: that PDF does not state the January deadline. Fixed in commit
`ed96dc17d8` by validating a deadline window's own `source_refs` against that
window's `opens_on`/`closes_on` — narrowly, applying only to refs cited
*exclusively* by deadline windows, so a source also cited by a casilla, binding
or formula still has to overlap the revision.

### A retroactive provision governs periods preceding its entry into force

Still open. `python -m dev.registry.conformance report` now refuses at:

```
modelo 190 revision 2024 cites legal references outside their effective window:
 - legal reference 'real-decreto-ley-13-2025:art-2' (kind 'real_decreto_ley',
   effective_from 2025-11-27, effective_to 2025-12-31) does not cover revision
   '2024''s devengo date 2024-12-31
```

The citation is substantively correct. The bundled corpus at
`corpus/normatives/html/real-decreto-ley-13-2025-art-2.html` states the
provision amends the La Palma deduction "durante los periodos impositivos 2022,
2023, 2024 y 2025", enumerating the governed periods explicitly. It modifies
`ley-35-2006:art-68.4`, which the same citing casilla also cites. The two citing
rows are
`src/cadrumo/_data/registry/aeat/modelos/190/revisions/2024/bindings/0002-bindings.toml:131`
and the `cperc.provincia__cperc.situacion-familiar.toml:32` casilla.

So `effective_from` / `effective_to` record when the norm entered force, and
nothing records which tax periods it governs. For a retroactive provision those
differ, and the devengo check reads the wrong one.

Deleting the citation would remove correct grounding for a real deduction.
Widening `effective_from` backwards would misstate when the norm came into force
and corrupt every other consumer of that field.

### The model has no field for governed periods

`LegalReference` (`src/cadrumo/domain/calculations/registry/_schema_references.py:161`)
carries `published_at`, `effective_from`, `effective_to` and
`consolidated_as_of`. None expresses retroactive reach; `consolidated_as_of` is
a corpus-vintage marker, not a governed-period claim.

An opt-in declared pair — the earliest and latest devengo a provision governs,
defaulting to the in-force span when absent — would let the devengo check use
the axis the citation defends, keeping the claim explicit and author-grounded
rather than inferred. Whether it belongs on `LegalReference` or on the citing
row is what the ADR must settle, along with whether corpus text enumerating the
periods should be required grounding for such a declaration.

### Not investigated

Whether other revisions carry retroactive legal citations the devengo check has
not yet reached: the report stops at the first failure, so the population behind
M190 is unmeasured. Whether the same axis problem affects `orden_aplicabilidad`
validation, which has its own window logic in
`_validate_orden_aplicabilidad.py`.

## Sources

- `src/cadrumo/domain/calculations/registry/_snapshot.py` — `_check_revision_scoped_source_windows`, `_deadline_window_source_spans`, `_source_applies_across`
- `src/cadrumo/domain/calculations/registry/_schema_references.py:161` — `LegalReference`
- `src/cadrumo/domain/calculations/registry/_schema.py:572` — `DeadlineWindowDefinition`
- `src/cadrumo/domain/calculations/registry/tests/test_source_applicability_window.py` — the three deadline-axis regressions
- `src/cadrumo/_data/corpus/normatives/html/real-decreto-ley-13-2025-art-2.html` — the enumerated periodos impositivos 2022-2025
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:1214` — the `real-decreto-ley-13-2025:art-2` catalogue entry
- commit `ed96dc17d8` — the deadline-axis fix as landed
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-23911 — RDL 13/2025
