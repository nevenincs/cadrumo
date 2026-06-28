---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
tier: L2
related:
  - '[[2026-05-22-schema-hardening-adr]]'
  - '[[2026-05-22-schema-hardening-research]]'
  - '[[2026-05-21-schema-hardening-reference]]'
  - '[[2026-05-21-schema-hardening-plan]]'
---


# `schema-hardening` `optional-numeric-suppressor-burn-down` plan

### Phase `P01` - Optional-numeric exposure source grouping

Group the 36 optional-or-numeric suppressed warnings by source-visible family and select exact candidates for manual lookup.

- [x] `P01.S01` - Generate optional-numeric suppressed-warning inventory with labels locations and near-role pairs; `src/aeat/domain/calculations/registry`.
- [x] `P01.S02` - Classify optional-numeric exposed pairs into source families and legal-risk buckets; `.vault/audit`.
- [x] `P01.S03` - Choose first implementation candidates and blocked families from the inventory; `.vault/audit`.

### Phase `P02` - Manual source lookup and policy decisions

Look up official or registry-grounded source context for the highest-priority optional-numeric families and decide exact suppression or singleton policy.

- [x] `P02.S04` - Look up official source context for Modelo 200 mantenimiento-empleo correction families; `.vault/audit`.
- [x] `P02.S05` - Look up official source context for Modelo 100 quoted-fund coti families; `.vault/audit`.
- [x] `P02.S06` - Look up official source context for generated-pending year and line families; `.vault/audit`.
- [x] `P02.S07` - Look up official source context for cadastral and miscellaneous optional-token families; `.vault/audit`.

### Phase `P03` - Exact-helper implementation and regression gates

Implement only approved exact-family replacements for broad optional-numeric stripping and prove adjacent legal concepts remain visible.

- [x] `P03.S08` - Implement approved exact optional-numeric replacement helper without registry rewrites; `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`.
- [x] `P03.S09` - Add regression tests for approved helper and blocked optional-numeric boundaries; `src/aeat/domain/calculations/registry/test_semantic_role.py`.
- [x] `P03.S10` - Run semantic-role warning corpus gates and targeted registry validation; `src/aeat/domain/calculations/registry`.

### Phase `P04` - Vault review and next-slice decision

Record source decisions, execution records, review outcomes, and whether the remaining broad helper can be narrowed further.

- [x] `P04.S11` - Update schema-hardening reference and sidecar audit with optional-numeric decisions; `.vault/reference`.
- [x] `P04.S12` - Create execution records summaries and review entries for the optional-numeric slice; `.vault/exec`.

### Phase `P05` - Registry validator substrate split

Record the registry validator breakup that reduced _validate.py and the largest helper modules into bounded validation surfaces while preserving existing schema semantics and registry behavior.

- [x] `P05.S13` - Extract registry-wide, revision-section, reference-checker, relation-period, and semantic-role-axis validators from the monolithic registry validator; `src/aeat/domain/calculations/registry validators`.
- [x] `P05.S14` - Verify validator modularisation against registry integrity, relation closure, semantic-role, and TOML reviewability gates; `src/aeat/domain/calculations/registry tests`.
- [x] `P05.S15` - Record the validator split commit sequence and current module-size baseline for handoff; `.vault/plan/2026-05-22-schema-hardening-plan.md`.

P05 handoff record:

- Commits: `26db75e57` extracted semantic-role typo validators; `307b23288` extracted cross-domain snapshot hooks; `d23b80b4b` extracted registry-scope validators; `e7bd18ec3` extracted previous-filing source validators; `fe7152be7` extracted revision-section dispatch; `c431a1c0b` extracted snapshot reference checking; `8d08cca48` extracted revision validation context; `05b3db238` extracted relation-period validators; `9143aeb85` extracted semantic-role axis heuristics.
- Module-size baseline: `_validate.py` 204 lines; `_validate_references.py` 312; `_validate_revision_sections.py` 252; `_validate_semantic_roles.py` 243; `_validate_record_sections.py` 238; `_validate_revision_identity.py` 228; `_validate_relation_periods.py` 198; `_validate_semantic_role_axes.py` 188; `_validate_dependency_sections.py` 182.
- Verification baseline: registry integrity, relation closure, semantic-role, and TOML reviewability gates passed path-scoped after the split.

### Phase `P06` - Next registry hardening substrate

Track the remaining structural hardening work after validator modularisation: relation/reference balance, fragment-schema regression gates, and broader modelo fragmentation support without per-modelo special cases.

- [x] `P06.S16` - Finish reference-validator balancing by splitting remaining snapshot reference sections only if the next pass keeps each module under the current reviewability baseline; `src/aeat/domain/calculations/registry/_validate_references.py`.
- [x] `P06.S17` - Add or tighten fragment-schema regression gates for loader directory mode, TOML file-size, row-length, and multi-revision single-file prevention; `src/aeat/domain/calculations/registry/test_loader_directory_mode.py`.
- [x] `P06.S18` - Audit generic revision-fragment support across M100 and non-fragmented modelos without adding per-modelo schema definitions; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P06.S19` - Identify the next modelo-family fragmentation target using committed line-count and revision-count evidence before touching registry TOMLs; `src/aeat/_data/registry/aeat/modelos`.

### Phase `P07` - Registry hardening pathway tracking

Keep registry-hardening work out of ad-hoc implementation by mapping each
discovered pathway to its governing ADR, plan, or required follow-up decision
before any further code or TOML edits land.

- [x] `P07.S20` - Enumerate discovered registry hardening pathways and classify each as already tracked, plan-only follow-up, or ADR-required follow-up; `.vault/exec/2026-05-27-schema-hardening-placeholder-eradication.md`.
- [x] `P07.S21` - Refresh the committed-corpus fragmentation target list from current line-count, revision-count, and layout-mode evidence before selecting the next modelo split; `src/aeat/_data/registry/aeat/modelos`.
- [x] `P07.S22` - Decide whether M100 needs only physical fragments or a compile-time template authoring layer; create a new ADR before any template support is implemented; `.vault/adr`.
- [x] `P07.S23` - Keep validator-module reviewability under the P05 baseline; if a package-level validator boundary is needed, record the public-export compatibility plan before moving modules; `src/aeat/domain/calculations/registry`.
- [x] `P07.S24` - Research a generic casilla continuity/evolution contract for non-overlapping annual revisions before any M100 template-expansion ADR; `.vault/research`.
