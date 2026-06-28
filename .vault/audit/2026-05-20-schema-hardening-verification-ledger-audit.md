---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-20-schema-hardening-plan]]"
  - "[[2026-05-18-schema-hardening-adr]]"
---

# `schema-hardening` verification ledger

Living tracking document for the post-enrollment verification and
remediation campaign. The enrollment campaign reached 100% structural
coverage (every casilla carries a `semantic_role`); this ledger drives
it toward genuine **type, label, and semantic correctness**.

Every change is recorded here with before/after counts so progress is
measurable rather than asserted.

## Honest scope statement

"100% coverage" means every one of 14,971 casillas carries a
`semantic_role` string. It does **not** mean every string is correct.
Roughly 3,700 of this campaign's assignments came from classification
agents reading section + label data and were applied by script. The
snapshot-build validators enforce *structural* consistency (per-id
cross-revision identity; per-role `data_type`/`constraints` identity)
— they do **not** verify that a role is the semantically correct
concept for its casilla. That gap is what this ledger closes.

## Known contamination

- **Escaped-quote label truncation.** The cluster-dump scripts that fed
  the classification agents extracted labels with the regex
  `label = "([^"]*)"`, which truncates at the first escaped quote.
  **561 casillas** (559 M100, 2 M200) have a `"` in their true label
  and were therefore classified on truncated input
  (e.g. `Marque una \` instead of
  `Marque una "X" si en la casilla [0077] ha consignado un NIF...`).
  These need re-verification against true labels. The registry TOML
  files themselves are valid and intact; only the extraction was wrong.
- **Parallel paired-cluster dispatch.** M200 `correcciones-a/-b` and
  `deducciones-a/-b` were dispatched concurrently with an instruction
  for half-B to read half-A's audit for naming consistency — physically
  impossible. Result: `correcciones-a` 231 casillas -> 18 roles vs
  `correcciones-b` 231 casillas -> 214 roles, **zero shared roles**.
  `deducciones-a/-b`: 1 shared role of ~50.

## Verification harness

`.vault-scratch/verify_roles.py` parses every casilla with `tomllib`
(no regex truncation) and reports high-confidence structural signals.
It deliberately does **not** emit a name-vs-label "semantic" count:
role names are bilingual conceptual summaries and legitimately diverge
from AEAT label wording; token matching cannot adjudicate that. True
semantic correctness is verified by agent review.

## Baseline (2026-05-20)

| Signal | Count | Notes |
|---|---:|---|
| casillas total | 14,971 | |
| roled | 14,971 (100%) | structural coverage |
| distinct roles | 2,143 | |
| TOML parse errors | 0 | files are valid |
| T type-vs-label candidates | 14 | ~5 confirmed defects, rest false-positive or needs-review |
| C incoherent roles | 6 | ~3 real outliers, rest coarse-but-valid roles |
| S singleton roles | 458 | each enforces no consistency; needs review |
| escaped-quote contaminated casillas | 561 | classified on truncated labels |

### T - confirmed type defects (percentage stored as money)

`ratio` is the registry's proportion type (`percentage` is not a valid
`data_type`). These five casillas hold a percentage but declare `money`:

- M100 `0063` "Propiedad (%)" - role `irpf_inmueble_porcentaje_propiedad`
- M100 `0064` "Usufructo (%)" - role `irpf_inmueble_porcentaje_usufructo`
- M100 `0087` "Indique el porcentaje (%) del inmueble a disposicion..."
- M100 `0710` "Porcentaje del importe total del prestamo hipotecario..."
- M100 `1564` "Porcentaje de participacion del contribuyente en la entidad"

All five are manual-input leaves with no `formula`, `binding`, or
`export_refs` in the registry graph - low blast radius. Status: OPEN.

### T - false positives / needs-review

- M100 `0619/0621/0630/0634/0653/0657` boolean flagged as nif: labels
  are "Indique si ... y en su caso el NIF del cedente" - the casilla is
  the yes/no flag; `boolean` is correct. Needs confirmation a sibling
  NIF casilla exists. Status: NEEDS-REVIEW.
- M100 `0831/0834`, M200 `00559`: labels are amounts ("Importe...",
  "Base imponible...") that mention a percentage incidentally;
  `money` is correct. Status: FALSE POSITIVE.

## Remediation tracker

| # | Item | State | Before | After |
|---|---|---|---|---|
| R1 | Verification harness | DONE | - | - |
| R2 | T percentage type defects | DONE | 5 ids / 30 instances | money -> ratio |
| R3 | M200 correcciones reconciliation | DONE | 0 shared roles, fractured | 631 casillas, one 24-axis scheme |
| R4 | M200 deducciones coherence | DONE (no defect) | suspected fracture | 853 casillas, 62 roles, 0 incoherent |
| R5 | escaped-quote re-verification | DONE | 561 | 114 flags clean; AEIP family (315) fixed; rest covered by R7 |
| R6 | singleton-role review | DONE | 506 | re-baselined; typo-twin heuristic improved |
| R7 | Full semantic-correctness agent sweep | DONE | - | M200 1250 + M100 2155 corrections applied |
| R8 | Source-data changes re-verification | DONE | 5 change groups | all verified safe |
| R9 | Downstream test suite (registry) | DONE | - | 1572 pass, 10 fail at baseline |
| R10 | M123/130/131 calc-test regressions | DONE | 10 | 7 stale tests fixed; 3 registry bugs (relations) removed |

## Change log

Records every registry source modification made during remediation,
with rationale and blast-radius assessment.

### 2026-05-20 - R3 M200 correcciones reconciliation

The `correcciones al resultado contable` cluster (695 casillas) was
re-classified under one consistent `is_correccion_<concepto>_<eje>`
scheme (24-axis vocabulary, 72 concept slugs), replacing the fractured
generic-vs-hyperspecific split. 689 `semantic_role` values rewritten.

**Misrouting found and corrected.** The re-dump's section->cluster
router swept 64 non-correction casillas into the correcciones bucket:
60 entity-identification checkboxes (`is_identificacion_flag`), 2
employee-headcount fields (`is_personal_asalariado_cifra_media`), the
negative-base indicator `00027` (`base_imponible_negativa_is`), and the
fiscal-group number `00018` (`is_grupo_fiscal_numero`). The
reconciliation agent gave them `is_correccion_*` roles; all 64 were
reverted to their correct pre-reconciliation roles. This surfaced via
the drift gate (a constraints-signature divergence on `00027`).
Blast radius: `semantic_role` only; no `data_type`/label/constraint
edits. Post-state: 0 data_type divergences, 0 constraints divergences.

### 2026-05-20 - R5 escaped-quote re-verification (in progress)

Re-checked all 561 casillas whose true label contains a quote char and
was therefore truncated in the agent cluster-dumps.

- **114** "Marque ... X ..." boolean-flag casillas: all clean
  (`*_flag` role + `boolean` data_type). The section path carried
  enough signal despite the truncation.
- **AEIP family defect found.** ~307 casillas in
  `anexo_a_res.deducciones_inversion_empresarial_res` whose labels are
  quoted public-event names (`"<event>": Aplicado en esta declaracion`)
  — all the same concept (AEIP event-sponsorship deduction amount) —
  are scattered across **7 roles**, 5 of them plainly wrong (energy-
  efficiency excess, pension contributions, Balearic reserve, anexo-B
  carry-forward). Caused directly by truncated-label classification.
  A focused agent is determining the canonical role; fix pending.

### 2026-05-20 - R5 AEIP family fix applied

Investigation agent confirmed **315** quoted-event-name casillas (all
6 revisions; 46 ids host different events across revisions, so the fix
is keyed per `(id, revision)`). All are the same concept: the amount
of an AEIP event-sponsorship deduction applied in the declaration.
Canonical role: **`irpf_anexo_a_aeip_aplicado`** (the pre-existing
`irpf_anexo_a_aeip_aplicado_flag` had a wrong `_flag` suffix - these
are euro amounts). 315 `semantic_role` values rewritten; the
non-event members of the 8 previously-conflated roles (196 casillas)
were left untouched. Blast radius: `semantic_role` only. Post-state:
0 data_type divergences, 0 constraints divergences.

### 2026-05-20 - R2 percentage type defects

5 M100 casillas hold a percentage but declared `data_type = "money"`:
`0063` "Propiedad (%)", `0064` "Usufructo (%)", `0087` "...porcentaje
(%) del inmueble...", `0710` "Porcentaje del importe total del
prestamo...", `1564` "Porcentaje de participacion...". Changed to
`ratio` (the registry's proportion type; M303 prorrata uses it) across
all 6 revisions = 30 (id,revision) instances, each label-guarded.
**Blast radius verified before the change:** none of the 5 ids is
referenced by any M100 formula file, revision binding, or cross-modelo
relation - they are pure manual-input leaves with no `export_refs`.
This is a `data_type` source edit; recorded here per the source-data
discipline.

### 2026-05-20 - R8 source-data change re-verification

Blast-radius re-check of every label/data_type/constraint edit made
earlier this campaign:
- `1096` text->nif, `0210` text->money default, RIC `dotacion_anio`
  ->text: NOT referenced by any formula, revision binding, or relation
  - pure leaves, safe.
- `0153` +`non_negative` constraint: referenced by 1 formula
  (`renta-2025-retenciones-arrendamientos-urbanos`); a constraint
  validates the value without changing it, and a retention is
  non-negative - safe.
- `irpf_ed` 2025 money->decimal: referenced by 51 formula entries, but
  the change only harmonised the 2025 instances to the 2020-2024
  `decimal` baseline they were already inconsistent with; the full
  registry suite's M100 estimacion-directa calculation tests pass.
All five change groups verified safe.

### 2026-05-20 - R7 M200 semantic sweep applied

All 566 M200 roles were reviewed by 6 semantic-review agents against
full labels (name accuracy, member coherence, granularity). 111 roles
carried a correction (92 renames, 19 splits); a consolidation agent
resolved 8 cross-batch conflicts into one per-casilla mapping. **1,250
casillas** had `semantic_role` rewritten; 144 distinct corrected role
names. Blast radius: `semantic_role` only. Post-state: 0 data_type
divergences, 0 constraints divergences. Common defect classes fixed:
factually wrong role names (e.g. `cooperativas` family was actually
grupo-fiscal group-exit; `actividades_economicas` amortization family
was actually I+D-specific), `_flag` suffix on money/decimal fields,
over-coarse roles lumping distinct LIS concepts, and outlier casillas
swept in from adjacent sections.

### 2026-05-20 - R7 M100 semantic sweep applied

All 1,560 M100 roles reviewed by 12 semantic-review agents against full
labels across all 6 revisions. ~24% flagged; a consolidation agent
resolved 8 cross-batch conflicts into 2,155 per-(id,revision)
corrections (1,302 renames, 809 split rows, 44 outliers). Applied.

Two integration issues surfaced and were resolved:
- **Required-role gate conflict.** R7 split `base_imponible_irpf`, but
  the `_REQUIRED_ROLE_LABEL_PATTERNS` hard-flip rule pins casillas
  labelled "Base imponible general/imputada" to that exact role. The
  12 affected casillas (0259/0435 x 6 revisions) were reverted to
  `base_imponible_irpf`; the rest of the split stands.
- **Foreign-id type split.** Renaming `landlord_nif`/`tenant_nif` to
  `irpf_arrendador_nif`/`irpf_inmueble_arrendatario_nif` merged the
  strict-`nif` casillas with the `text`-typed foreign-fiscal-id-capable
  variants. The 38 `text` casillas were split into
  `irpf_arrendador_nif_o_id_extranjero` /
  `irpf_inmueble_arrendatario_nif_o_id_extranjero`.

Post-state: 0 data_type divergences, 0 constraints divergences, all 13
drift-gate tests pass.

### 2026-05-20 - singleton-role guard re-baselined

The comprehensive R7 sweep split coarse roles into precise per-concept
roles. Single-revision modelos (M200) intrinsically produce one casilla
per concept, so single-occurrence roles are the expected shape. The
`test_singleton_semantic_role_warning_count_does_not_regress` threshold
was re-baselined 235 -> 560. Justification recorded: all 541 current
singletons were checked by an edit-distance near-duplicate scan; the 49
lexically-close pairs are genuine distinctions (`ascendiente` vs
`descendiente`, numbered catastral slots) - zero actual typos.

### 2026-05-20 - R10 stale calculation tests fixed

7 of the 10 R10 failures were stale tests (registry correct): the M130
+ M131 `result.entries` assertions did not include the
`saldo-negativo-fin-periodo` computed casilla added by feature commit
`eb4306024`; the M123 test used pre-fragmentation casilla ids. Updated
all 7 assertions to match the correct registry. The remaining 3 (a
malformed self-referencing carry-forward relation) are a genuine
registry structural bug, tracked open.

### 2026-05-20 - R10 malformed self-referencing relations removed (Option B)

The three remaining R10 failures (Failures 8, 9, 10 per the investigation
document) were caused by intra-modelo carry-forward relations introduced by
commit `eb4306024` using the cross-model `RelationDefinition` schema. The
relations are structurally invalid: `source_modelo == modelo.id` violates
the cross-model hierarchy contract, `copy` aggregation with 3 static
`source_periods` is incoherent, and no formula expression consumed the
`direct_calculation` dependency role.

**Root cause:** the relations were redundant — each modelo already carries the
carry-forward value through a `source = "previous_filing"` binding that is
fully self-sufficient. Option B applied: remove the relation and dependency
classification entirely; the binding alone carries the value.

**Blocks removed per file:**

- `src/aeat/_data/registry/aeat/modelos/130.toml` — removed
  `[[revisions."2019-y-siguientes".relations]] id = "modelo-130-rel-self-prior-quarter-negative"` and
  `[[revisions."2019-y-siguientes".dependency_classifications]] id = "modelo-130-dep-self-prior-quarter"`;
  removed `relations` and `dependency_classifications` lines from construct manifest.
  Binding `modelo-130-resultados-negativos-anteriores` (previous_filing) carries the value.

- `src/aeat/_data/registry/aeat/modelos/131/revisions/2019-2023.toml` — same pattern:
  `modelo-131-2019-2023-rel-self-prior-quarter-negative` relation and
  `modelo-131-2019-2023-dep-self-prior-quarter` classification removed.
  Binding `modelo-131-2019-2023-resultados-negativos-anteriores` carries the value.

- `src/aeat/_data/registry/aeat/modelos/131/revisions/2024.toml` —
  `modelo-131-2024-rel-self-prior-quarter-negative` and `modelo-131-2024-dep-self-prior-quarter` removed.

- `src/aeat/_data/registry/aeat/modelos/131/revisions/2025.toml` —
  `modelo-131-2025-rel-self-prior-quarter-negative` and `modelo-131-2025-dep-self-prior-quarter` removed.

- `src/aeat/_data/registry/aeat/modelos/131/revisions/2026.toml` —
  `modelo-131-2026-rel-self-prior-quarter-negative` and `modelo-131-2026-dep-self-prior-quarter` removed.

**Additional pre-existing violations surfaced and fixed:** removing the M130/M131
relations caused the contract test loop to advance past those failures and expose
two more modelos with the same structural bug (also introduced via the same
pattern prior to this session):

- `src/aeat/_data/registry/aeat/modelos/303.toml` —
  `modelo-303-rel-self-compensacion-anteriores` and `modelo-303-dep-self-prior-quarter` removed.
  Binding `modelo-303-compensacion-pendiente-anteriores` (previous_filing, source_period_offset_from_target = -1) carries the value.

- `src/aeat/_data/registry/aeat/modelos/202/revisions/2019-2022/` —
  `0001-modelo-202-2019-2022-rel-self-pagos-2p.toml`,
  `0002-modelo-202-2019-2022-rel-self-pagos-3p.toml`, and
  `0001-modelo-202-2019-2022-dep-self-prior-pagos.toml` deleted;
  manifest updated. Same for `2023-2024` and `2025-y-siguientes` revisions.
  Binding `modelo-202-*-pagos-fraccionados-anteriores` (previous_filing, sum aggregation) carries the value.

**Test results post-fix:**
- `test_cross_dependency_calculations.py` + `test_cross_dependency_contract.py` + `test_committed_registry.py`: **72 passed, 0 failed**
- `test_cross_revision_drift.py`: **13 passed, 0 failed**

### 2026-05-20 - R9 registry test suite (honest finding)

Full `registry/` suite: **1572 passed, 10 failed** (32 min run).
The 10 failures are calculation / cross-dependency tests for modelos
**123, 130, 131** (e.g. modelo 130 emits an unexpected
`saldo-negativo-fin-periodo` engine entry the test does not list).
Git attribution: those modelo files were last modified by campaign
commits *older than this session* (`b3c37983d Split large multi-
revision modelos`, `c1563e2ff`, `c389b07bb`, `690ed3e6e`) - **not by
this session's M100/M200 work**. They are pre-existing schema-hardening
regressions, in scope for the campaign, tracked here as R10. The
registry validation / drift / semantic-role tests all pass.

### 2026-05-20 - R10 M303/M202 over-reach corrected

The R10 relation-removal pass over-reached: while removing the
malformed M130/M131 carry-forward relations (correct - those modelos'
bindings are self-sufficient), it also removed the M303 and M202
intra-modelo carry-forward relations on a pattern match, WITHOUT
running the M303/M202-specific registry tests. The full registry suite
then surfaced 3 `test_modelo_303_registry.py` failures: those tests
assert the relation requirement resolves - the M303 relation is
genuinely used, not redundant.

Correction: the M303 relation and the 9 M202 relation/dependency
fragments were restored to their pre-R10 state. The real fix for the
self-referencing-relation contract violation is Option A, not removal:
a `previous_period` relation models legitimate intra-modelo
prior-period carry-forward. The cross-dependency contract was updated
to accept `kind == "previous_period"` in three places (the hierarchy
self-reference check, the formula-consumption `required` set, and the
`direct_calculation` role contract). 104 targeted registry tests pass.

Lesson logged: a relation-removal "same structural violation" pattern
match must be validated against each modelo's own test suite before
being applied - structural similarity does not imply redundancy.

## Campaign closeout (2026-05-20)

Full `src/aeat/domain/calculations/registry/` test suite: **1608 passed,
0 failed** (25m run). Baseline at R9 was 1572 pass / 10 fail; all 10
R10 regressions resolved, and the R7 semantic sweep landed under green
gates.

Final corpus state:
- 14,971 casilla declarations, 100% `semantic_role` coverage, 26 modelos.
- ~2,426 distinct roles after the semantic-correctness sweep.
- 0 intra-role `data_type` divergences, 0 constraints divergences.
- Cross-revision drift gate, semantic-role consistency, required-role
  hard-flip, cross-dependency contract: all green.

Remediation R1-R10 all DONE. Honest residual: the harness still lists
9 type-vs-label candidates - all verified false positives or
documented needs-review (the `Indique si ... NIF` boolean flags; the
0831/0834/00559 amounts) - and the role namespace carries legitimate
single-revision singletons (re-baselined, typo-twin heuristic improved,
zero actual typos found). No FATAL validator or test failure remains.

### 2026-05-20 - R7 extended corpus-wide (24 small modelos)

The R7 sweep originally covered M100 + M200 (97% of casillas). Extended
to the remaining 24 modelos: all 175 roles reviewed against full labels
by 3 agents. 36 `semantic_role` corrections applied - 9 renames
(English->Spanish, `immueble` typo, wrong-frame roles), 3 splits
(`pago_fraccionado` IRPF vs IS; OSS cuota per destination country), 2
outliers (M184 entity-member NIF, M840 IAE census event). Zero
data_type/constraints divergences. The semantic-correctness review is
now corpus-wide: every role in all 26 modelos has been read against its
casillas' true labels.
