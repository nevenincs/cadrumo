---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
---

# CLI testimonial - Nuria, ledger deep flow

## What I was trying to do

I am an autonoma consultant. I had just imported my Q1 2025 bank movements and wanted to groom the full ledger: classify each transaction as business or personal, set the IVA breakdown, allocate the business percentage for mixed-use items, attach receipts, review the result, and finally see the review/audit queue drain. The goal was to end up with a clean, tax-ready ledger ready to feed Modelo 303 and Modelo 130.

## My session

### Step 1 — Profile creation

```
AEAT_LOCAL_STORAGE_ROOT=.../persona-nuria uv run --no-sync aeat config profile create nuria \
  --quiet --tax-id "12345678Z" --name "Nuria" --surnames "García López" \
  --activity "Consultora independiente" --address-postcode "28001" \
  --taxation-type 1 --output-language es --iva-regime GENERAL
```

**Expected:** profile created silently.
**Got:** first attempt failed with `No such option: --professional-income-mostly-withheld`. The actual flag is `--professional-income-withholding-ge-70pct`. The wrong name is plausible — I guessed from the help text summary. Second attempt without the flag succeeded silently (no output at all on success — slightly alarming but acceptable).

Verification via `aeat config profile show nuria` worked perfectly and showed all 27 fields.

**Felt:** one stumble on flag naming; otherwise smooth.

---

### Step 2 — Discovering the import format

```
AEAT_... aeat app ledger import --provider list
# Error: Missing argument 'PATH'.
```

There is no `--provider list` or equivalent. I had to probe by trial and error.

```
AEAT_... aeat app ledger import --provider N26 /dev/null --dry-run
# ERROR ... failed to parse OFX file
```

```
AEAT_... aeat app ledger import --provider csv /dev/null --dry-run
# Error. CSV headers do not match any supported bank layout
```

I eventually discovered that `csv` and `N26`/`ofx` are the two valid provider families. Valid CSV headers are `Date,Description,Amount,Currency,Balance`. There is no help text, `--provider list`, or example file to discover this — pure trial and error.

**Felt:** very frustrating. A `--provider` enum or `--show-example` flag would save this entirely.

---

### Step 3 — Import 10 realistic transactions

```
aeat app ledger import --provider csv movimientos.csv
# Filas  10
# Entradas importadas  10
# Omitidos  0
```

**Expected:** 10 transactions imported.
**Got:** exactly that. Clean output.

```
aeat app ledger list
# 11 rows (includes 1 from earlier test run)
# All status: pending
```

**Felt:** clean and satisfying.

---

### Step 4 — View a single transaction

```
aeat app ledger view 9662ea42
# ID    9662ea428a76f7dba46a9d22...
# Fecha    2025-01-15
# Importe  1500
# Descripción  Factura 001 - Consultoria IT cliente Empresa SL
# Estado de revisión  pending
```

**Expected:** basic fields. Got them. No classification, IVA, or category visible yet — correct at this stage.

---

### Step 5 — Classify a transaction

```
aeat app ledger classify \
  --id 9662ea42 \
  --classification BUSINESS \
  --taxable-base 1239.67 \
  --iva-rate 0.21 \
  --iva-amount 260.33
# ID    9662ea42...
# Fecha    2025-01-15
# Importe  1500
# Descripción  Factura 001 - Consultoria IT...
# Estado de revisión  reviewed
```

**Expected:** state changes to `reviewed`, IVA fields stored.
**Got:** state changed. But the output does not echo back the IVA values I just set. I cannot tell from the output whether they were stored.

Follow-up `ledger view 9662ea42` shows only the 4 base fields — classification, taxable base, IVA rate, IVA amount are not surfaced. To verify storage I had to run `ledger export`.

**Felt:** opaque. The `view` command is a dead-end for grooming work.

---

### Step 6 — Allocate business percentage

```
aeat app ledger allocate --id 9662ea42 --business-pct 1.0
# ID ... Estado de revisión  reviewed
```

**Expected:** record the 100% business allocation; preserve the BUSINESS classification from classify.
**Got:** command succeeded. But `ledger export` later revealed that the classification was silently downgraded from `BUSINESS` to `MIXED` even though `business_pct = 1.0`. This is a data integrity bug: allocate overwrites the explicit classification regardless of the percentage value.

Cross-check: `classify --classification BUSINESS` alone (no allocate) correctly stores `BUSINESS` in the export. The overwrite only happens when `allocate` is called afterward.

Also discovered: calling `allocate` on a transaction that has never been classified causes the transaction to become `reviewed` with classification `MIXED` and the given `business_pct`, bypassing the classify step entirely. This is probably unintended — a transaction can become "reviewed" without any IVA breakdown.

**Felt:** silent data corruption. Dangerous for tax accuracy.

---

### Step 7 — Attach a receipt

```
aeat app ledger attach --id 9662ea42 --attachment-id "factura-001-empresa-sl.pdf"
# Error. attachment_ids must reference existing secure attachment manifests and blobs
#   attachment_id: factura-001-empresa-sl.pdf
```

```
aeat app ledger attach --id 9662ea42 --purchase-invoice-evidence-id "INV-001-2025"
# Error. purchase_invoice_evidence_id must reference an existing purchase invoice evidence record
#   purchase_invoice_evidence_id: INV-001-2025
```

**Expected:** some path to attach a receipt file or reference.
**Got:** both options require pre-existing internal IDs (secure blob manifests, purchase invoice evidence records). There is no CLI surface to create these — no `evidence add`, no `attachment upload`, no guidance on how to obtain a valid ID. The `attach` command is a dead-end for a new user.

**Felt:** completely blocked. The feature exists in the schema but is unreachable from the CLI.

---

### Step 8 — Update transaction metadata

```
aeat app ledger update --id 9662ea42 --notes "Proyecto Q1 enero" --counterparty "Empresa SL"
# ID ... Estado de revisión  reviewed
```

**Expected:** notes and counterparty updated and visible in `view`.
**Got:** command succeeds. But `ledger view 9662ea42` still shows only the 4 base fields — no notes, no counterparty. Running `ledger export` confirmed the update was stored (notes and counterparty present in CSV). So the update works but `view` is blind to it.

**Felt:** update works, but `view` is useless as a verification step.

---

### Step 9 — Review session

```
aeat app ledger review
# Lists all 11 transactions with status
```

```
aeat app ledger review --id 9662ea42
# Refused. The command input failed validation.
# -> Run `aeat config repair`
```

```
aeat app ledger review --id 9662ea428a76f7dba46a9d22fd795f85236de70a77205bd0568c8d50b63294b6
# ID ... Fecha ... Importe ... Descripción
# (4 fields, no Estado de revisión, no IVA data)
```

Three problems found here:
1. Short IDs (8-char prefix) accepted everywhere else fail with a misleading "validation failed / run config repair" error in `ledger review`. The real error is that `review` requires the full UUID.
2. The `ledger review --id <full-uuid>` for an already-reviewed transaction shows only 4 fields and omits `Estado de revisión`. Less information than `ledger view`.
3. `--filter pending` (without `=`) fails with "Fallo al analizar el filtro". The correct syntax is `--filter "status=pending"` but this is undocumented.

**Felt:** confusing. The "run config repair" error message is a red herring — nothing is broken, the ID format is wrong.

---

### Step 10 — Review queue

```
aeat app review queue
# Lists 5 pending transactions with full UUIDs and a "Siguiente" action hint
```

```
aeat app review view e9dc2f1f...
# ID, Tipo, Objeto, Bucket, Severidad, Siguiente
```

The queue works. It surfaces the 5 still-pending transactions and gives the next action. `review view` gives the item metadata but no information about WHY the transaction is pending — no checklist of what still needs to be done (classify? allocate? attach?).

**Felt:** the queue is functional but gives no actionable diagnosis per item.

---

### Step 11 — Ledger status

```
aeat app ledger status
# Bucket  nuria
# Filas  11 / Activas  11 / Archivadas  0 / Apartadas  0
# Pendientes de revisión  5 / Revisadas  6 / Omitidos  0
```

**Expected:** summary of grooming progress.
**Got:** exactly that. Clean and useful.

---

### Step 12 — Export for verification

```
aeat app ledger export --output export.csv
# Filas 11, SHA-256 ...
```

The export CSV is rich: 25 columns including all classification, IVA, notes, counterparty, lifecycle state, and provenance. This is the only way to verify that `classify`, `allocate`, and `update` actually stored data. The `ledger view` command is far too sparse to be useful for grooming verification.

---

### Step 13 — No reconcile verb

There is no `ledger reconcile` in the CLI. The help surface (`aeat --help`) does not list it either. For an autonoma wanting to reconcile bank movements against issued invoices this is a notable gap.

---

### Step 14 — Modelo bindings check

```
aeat app modelo bindings list --modelo 303 --year 2025 --period Q1
# 6 bindings, all ledger_iva_aggregation or previous_filing source
# borrador_capable: False for all
```

The ledger is wired as the source for M303 IVA casillas. However `borrador_capable` is False for every binding, so no draft declaration can be generated from the CLI. The entire grooming workflow feeds into a dead end at the modelo layer.

## Did it work?

Partially. The core state machine (import → classify → allocate → review → export) functions and state changes persist. The data is stored correctly (as verified via export). However:

- `ledger view` is too sparse to trust as a grooming verification tool
- `attach` is completely unreachable (no surface to create evidence or blob IDs)
- `allocate` silently corrupts the BUSINESS classification to MIXED
- `ledger review --id <short>` gives a misleading repair error
- `review view` gives no actionable diagnosis
- No `ledger reconcile` verb
- No modelo draft generation (all `borrador_capable: False`)

## Bugs and gaps

1. **`allocate --business-pct 1.0` overwrites BUSINESS → MIXED**
   Command: `aeat app ledger allocate --id X --business-pct 1.0` after `classify --classification BUSINESS`
   Expected: classification remains BUSINESS (pct=1.0 is by definition fully business)
   Actual: export shows `MIXED,1.0` — the allocate event overwrites the explicit classification
   Severity: **BLOCKER** — silent tax data corruption; a 100% business expense filed as MIXED may alter IRPF/IVA calculations

2. **`attach` is a dead-end — no surface to create attachment IDs or evidence records**
   Command: `aeat app ledger attach --id X --attachment-id "file.pdf"`
   Expected: some path to attach a receipt/invoice file
   Actual: requires pre-existing blob manifest or evidence record IDs with no CLI path to create them
   Severity: **BLOCKER** — the receipt-attachment workflow is completely unreachable

3. **`ledger review --id <short>` gives misleading "run config repair" error**
   Command: `aeat app ledger review --id 9662ea42`
   Expected: either display the review or a clear "use full UUID" message
   Actual: `Refused. The command input failed validation. Run aeat config repair`
   Severity: **MAJOR** — misleading error sends user on a false diagnostic path; every other verb accepts short IDs

4. **`ledger view` does not surface classification, IVA, notes, counterparty, or allocation data**
   Command: `aeat app ledger view <id>`
   Expected: after classify/allocate/update, view shows the full current state of the transaction
   Actual: always shows only 4 fields: ID, Fecha, Importe, Descripción (+ Estado de revisión)
   Severity: **MAJOR** — grooming verification requires export; view is useless as a spot-check

5. **`allocate` without prior `classify` silently marks transaction as reviewed**
   Command: `aeat app ledger allocate --id X --business-pct 0.8` (never classified)
   Expected: error or warning that classify has not been run
   Actual: transaction moves to `reviewed` with `MIXED,0.8` and no IVA data — skips classify entirely
   Severity: **MAJOR** — allows incomplete records to pass through as "reviewed"

6. **`--filter pending` (without `=`) gives unhelpful parse error**
   Command: `aeat app ledger review --filter pending`
   Expected: filter to pending transactions, or a clear format hint in the error
   Actual: `Invalid value: Fallo al analizar el filtro del libro` — no hint that `status=pending` is the correct form
   Severity: **MINOR** — workaround exists; error message needs a format example

7. **`review view` gives no diagnosis of what is needed to clear the item from the queue**
   Command: `aeat app review view <item-id>`
   Expected: checklist of unmet grooming requirements (e.g., "missing: classify, allocate")
   Actual: shows type, severity, and the `Siguiente` next-action command — no explanation of why it is pending
   Severity: **MINOR** — functional but unhelpful for orientation

8. **No `ledger reconcile` verb**
   Expected: ability to reconcile bank movements against issued/received invoices
   Actual: verb absent; not surfaced in help
   Severity: **MINOR** — may be out of scope for current phase, but is a meaningful gap for a real autonoma workflow

9. **No `--provider list` or example format discovery**
   Command: `aeat app ledger import --provider list`
   Expected: list of valid providers with format hints
   Actual: `Missing argument 'PATH'`; valid providers and CSV column schema require trial and error to discover
   Severity: **MINOR** — significant friction at onboarding; a `--show-example` or `--provider list` flag would fix this

10. **All M303 bindings `borrador_capable: False` — no draft declaration reachable**
    Command: `aeat app modelo bindings list --modelo 303 --year 2025 --period Q1`
    Expected: at least one binding capable of producing a draft from ledger data
    Actual: all 6 bindings show `borrador_capable: False`
    Severity: **MAJOR** — the full grooming workflow (classify → allocate → modelo) leads to a dead end; no declaration draft can be generated from the CLI
