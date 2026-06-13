---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
  - '[[2026-05-19-schema-hardening-role-taxonomy-reference]]'
---

# `schema-hardening` Registry Health Audit

This audit maps the next registry-hardening work after the continuity
conformance plan reached 100 percent completion.

## Current Health

The registry artifact is materially healthier than it was before the M200 and
M100 fragmentation work. There is no longer a single 100k-line modelo TOML file
in the committed corpus. Directory-mode modelo loading, revision fragmentation,
continuity fragments, export-layout fragment merging, construct merging, and
completeness-manifest fragment merging are now generic loader capabilities.

The health is not good enough to relax. The largest TOML fragments are still
close to the current 1750-line reviewability ceiling. M100 completeness
manifests for 2024, 2023, 2022, 2021, and 2020 remain large singleton files.
Several M200 export fragments and M303 casilla/export fragments are also
between roughly 1200 and 1620 lines. These are not catastrophic, but they are
near-threshold surfaces that will regress quickly if future data lands without
further fragmentation.

The registry Python surface is also large. `_bindings.py` is roughly 3000
lines, `_schema.py` roughly 2500, `_record_design.py` roughly 1770,
`_applicability.py` roughly 1450, `_formula_runtime.py` roughly 1280, and
`_loader.py` roughly 900 after the fragment compiler additions. `_validate.py`
itself is no longer the monolith; validation has already been split into many
modules. The current validator pressure point is `_validate_cross_revision.py`,
which is roughly 420 lines and now owns both advisory drift summaries and
strict continuity policy. That module is still reviewable, but it is the next
validator module to watch.

Full registry-directory ruff is still not a clean signal. Touched-file ruff
passed during the continuity work, but a broad
`ruff check src/aeat/domain/calculations/registry` still reports pre-existing
lint debt in unrelated modules, including long lines, docstring argument gaps,
and import-order issues. That means broad lint cannot currently be used as a
single campaign confidence gate without either path-scoping or a separate lint
stabilization slice.

The shared worktree remains dirty with unrelated changes in CLI, live, docs,
storage, M347, and tests. Registry-hardening work must continue using
path-explicit commits and must inspect target-path diffs before editing.

## Discovered Not Yet Addressed

- M100 completeness manifests for 2024 through 2020 remain large and should be
  split now that generic completeness-manifest fragment merging exists.
- M200 export fragments remain near the fragment ceiling; they need a file-size
  audit and possibly further record-field fragmentation.
- M303 2009 and 2023 casilla/export fragments remain near the fragment ceiling.
- M123 current revision TOML is over 1200 lines and should be audited for
  directory-mode migration before it grows further.
- M100 continuity coverage is still intentionally narrow. Only two continuity
  surfaces are authored today: `0582` and `1038`. The next continuity data must
  remain evidence-grounded and should not convert repeated casilla ids into
  implied continuity.
- M347 singleton warning pressure appears in current shared-worktree context.
  The committed tests had been warning-clean after explicit singleton markers,
  but M347 is currently dirty and should be re-audited before relying on the
  singleton-warning gate.
- Signed cuota semantic roles are only partially settled. The role taxonomy
  reference identifies `resultado_ingresar_o_devolver_irpf` and
  `resultado_ingresar_o_devolver_is`; these need a focused role-consistency
  slice if the current corpus or tests drift.
- `base_intracomunitaria` appears grounded for M349 in current data, but it
  should be verified through a focused M349 registry test rather than assumed.
- Loader fragment support is generic but growing. `_loader.py` should be
  reviewed after the next fragmentation batch to decide whether source
  discovery, revision merging, and nested-fragment merging should split into
  private modules.

## Recommended Next Substrate

The next substrate should be reviewability, not more semantic expansion. Split
the remaining near-threshold registry authoring files first, while preserving
runtime schema semantics. After that, continue continuity rollout in small
evidence-grounded M100 slices. Only after the file-size and continuity surfaces
are stable should the campaign take on broad role taxonomy expansion or Python
module decomposition.
