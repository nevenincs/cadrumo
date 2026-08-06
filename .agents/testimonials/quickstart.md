---
doc: docs/how-to/quickstart.md
persona: freelance autónomo, first-ever use, wants the shortest path to a Modelo 130 file
author: coordinator (covered directly after the background persona for this page failed to start twice)
date: 2026-06-18
---

# Quickstart — naive-user walkthrough

Environment: isolated `AEAT_LOCAL_STORAGE_ROOT` + secret store under `/tmp/coord-quickstart`;
master-key passphrase supplied via env (the page never warns one is needed). CLI invoked as
`uv run --no-sync aeat ...`.

## Walkthrough

### Step 1 — `config profile create` + `profile status`
- Expected (doc): create profile, then status shows you are ready to proceed.
- Actual: profile created (`estado=creado`, `active_profile=my-profile`). BUT `profile status`
  reports `readiness=blocked`, `activities.description=missing`, `next_action: aeat config profile edit`.
- Verdict: BOTH / MINOR. The quickstart's own step-1 command leaves the profile `blocked`; the
  page does not tell the reader they must also declare an activity before later steps work.

### Step 2 — `ledger import ./statement.csv --provider auto --dry-run`
- Expected (doc): a dry-run import preview.
- Actual: a raw Python traceback (`FileNotFoundError: ... 'statement.csv'`) plus a stray
  `pdf_n26_provider: failed to parse PDF` ERROR log line, then finally
  `Error. auto-detection of ledger format failed for statement.csv`.
- Verdict: BOTH / **BLOCKER**. (a) The page supplies no `statement.csv` and never shows the CSV
  format, so a naive user cannot run this step at all. (b) A missing input file produces a stack
  trace before the friendly error — it should fail cleanly.

### Step 4 — `overview agenda`
- Expected (doc): "see what may be due for the active profile."
- Actual: `Error — El perfil activo no declara este modelo fiscal; actualiza el perfil...`
  The minimal step-1 profile does not declare any modelo, so agenda errors out.
- Verdict: BOTH / MAJOR. The page presents `agenda` as a simple call, but it fails on the very
  profile step 1 told you to create. `overview explain 130 --year 2024` *does* work (lists profile facts).

### Step 5 — `modelo work create --modelo 130 --year 2024 --period 1T`
- Expected: create the filing workspace. Actual: works (`Nueva unidad de trabajo creada`). Verdict: OK.

### Step 6 — `modelo work calculate ...`
- Expected (doc): "Run calculation for the same form" — presented as a one-liner.
- Actual: `Error — La vinculación irpf.previous_year_economic_activity_net_income no tiene valor
  asignado.` Modelo 130 1T needs **6 bindings**: 3 `previous_filing` carries and 3
  `ledger_renta_income_aggregation` income values. With no ledger data and no prior filing, calculate
  cannot run.
- Verdict: BOTH / **MAJOR**. The page never mentions that calculate requires imported/classified
  income and prior-filing values. The error's remediation ("supply `--binding KEY=VALUE`") is also
  **misleading**: supplying the ledger-derived income bindings via `--binding` is *refused*
  (`Los bindings de agregación derivados del bucket entran en conflicto...`) — only the
  `previous_filing` bindings accept `--binding`; income must come from real ledger rows.

### Step 6 (made to work) — backend capability confirmed
- After `ledger add --date 2024-02-15 --amount 10000 --direction INCOMING --classification BUSINESS`
  and supplying the three prior-filing bindings as `0`, calculate succeeds and produces a coherent,
  registry-grounded Modelo 130: casilla 07 = **2000.00** (20% pago fraccionado of the 10 000
  rendimiento), box 13 minoración 100.00, casilla 19 final = **1900.00**.
- Verdict: APP delivers. The engine is correct and well-formed once real inputs exist.

### Step 7 — `modelo work verify`
- Before a successful calculate: `Error — work unit has no selectable current_calculation_revision_id`
  (cascades from step 6). After a successful calculate, verify returns **3 blocking findings**:
  `missing_required_casilla 02` (gastos), and two `cross_period_dependency_unclean` findings
  (the M100/2023 prior is unevidenced; no activity-start date on the profile).
- Verdict: APP is robust/correct — the verify gate is well-grounded (carries `legal_refs` +
  `source_refs`, gives concrete remediation). But this directly contradicts the quickstart's framing
  ("When verification passes, aeat marks the draft verified") — a genuine first-time autónomo will
  NOT pass on the first try; they must record an activity-start date and/or supply casilla 02.

### Step 8 — `modelo export`
- Expected: produce the `.boe`. Actual: correctly refused —
  `current revision is still draft; verify it before exporting`. Verdict: APP correct (good gating),
  but unreachable for the naive path because verify never passes.

### Step 9 — `modelo work file`
- Correctly refused: `filing requires a verified-complete revision`. Verdict: APP correct.

## Findings

1. **[BLOCKER][BOTH]** Step 2 import: no sample `statement.csv` and no CSV format on the page; and a
   missing file dumps a `FileNotFoundError` traceback + spurious PDF-parser ERROR log before the
   friendly message. Fix: ship a tiny sample CSV (or inline the column format) and make missing-file
   a clean refusal, not a traceback.
2. **[MAJOR][BOTH]** Step 6 calculate is presented as a one-liner but requires imported+classified
   income and prior-filing values. Fix: the quickstart must sequence "import → classify → calculate",
   and step 6 should state the prerequisites (or link them inline as hard requirements, not optional).
3. **[MAJOR][APP]** The calculate error tells the user to pass `--binding KEY=VALUE` for *every*
   missing binding, but ledger-aggregation bindings reject `--binding`. Fix: the error should
   distinguish ledger-sourced bindings ("add ledger rows / import") from `previous_filing` bindings
   ("pass `--binding` or file the prior period").
4. **[MAJOR][BOTH]** Step 4 `overview agenda` errors on the minimal step-1 profile ("el perfil no
   declara este modelo"). Fix: either step 1 must create a profile that declares an activity/modelo,
   or step 4 must precede with the profile-edit that makes agenda meaningful.
5. **[MAJOR][DOC]** Steps 7–9 promise a smooth verify→export→file, but a real first-period autónomo
   hits blocking `cross_period_dependency_unclean` findings. Fix: the page should cover recording the
   activity-start date (`aeat config profile edit`) for first-period filers, and entering casilla 02.
6. **[MINOR][DOC]** No mention anywhere that a master-key passphrase is required; an interactive user
   is silently prompted, a scripted user is hard-blocked. Add a one-line note.
7. **[NIT][DOC]** `ledger add` (the manual single-row path most users need when they have no CSV) is
   absent from the curated top-level help overview, though present in `ledger --help`.

## Testimonial

As a first-time autónomo I got a profile created in seconds, but the quickstart fell apart the moment
I left step 1: there was no `statement.csv` to import (and the failure was an ugly traceback), and the
single-line "Run calculation" step refused me because I had no income in the ledger and no prior
filing. Once I figured out `ledger add` on my own and fed in €10 000 of income, the tool *shone* — it
produced a clean, legally-grounded Modelo 130 (2000 € pago fraccionado, 1900 € to pay) and then very
sensibly refused to export or "file" a draft that still had an unevidenced prior-year dependency. The
**engine is trustworthy and well-gated; the quickstart page is the weak link** — it reads like a happy
path that the app's own (correct) safety gates will not actually let a beginner walk.

## Scorecard
- Doc clarity: 2/5 (linear narrative breaks at steps 2, 4, 6, 7 for a genuine first-timer)
- App capability: 4/5 (correct calculation + robust, well-grounded gating; loses a point for the
  traceback-on-missing-file and the misleading `--binding` remediation hint)
- Findings: BLOCKER 1, MAJOR 4, MINOR 1, NIT 1
