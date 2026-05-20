---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
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
| R2 | T percentage type defects (5) | DONE | 5 ids / 30 instances | money -> ratio |
| R3 | M200 correcciones reconciliation | DONE | 0 shared roles, fractured | 631 casillas, one 24-axis scheme |
| R4 | M200 deducciones coherence | DONE (no defect) | suspected fracture | 853 casillas, 62 roles, 0 incoherent |
| R5 | 561 escaped-quote re-verification | IN PROGRESS | 561 | 114 boolean-flag clean; AEIP family defect found |
| R6 | singleton-role review | OPEN | 506 | - |
| R7 | Full semantic-correctness agent sweep | IN PROGRESS | - | M200 done (1250 corrections); M100 consolidating |
| R8 | Source-data changes re-verification | DONE | 5 change groups | all verified safe |
| R9 | Downstream test suite (registry) | DONE | - | 1572 pass, 10 fail (pre-date this session) |
| R10 | M123/130/131 calculation-test regressions | OPEN | 10 | - |

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
