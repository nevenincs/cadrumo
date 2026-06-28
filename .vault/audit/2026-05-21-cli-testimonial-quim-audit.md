---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-persona-task-catalogue-reference]]"
---

# CLI testimonial - Quim, mixed-use asset categorization

## What I was trying to do

I am Quim, a freelance architect based in Barcelona. I work from a home office and use my car and phone for both client visits and personal errands. I want this tool to help me figure out what fraction of my electricity bill, fuel costs, and phone bill I can deduct. I was told there is an `allocate` command that lets me set a business-use percentage. My goal was to:

- Create a profile for my tax situation (autonomo, IVA general, Cataluña).
- Import a few months of mixed-use transactions from a bank CSV.
- Mark each one as mixed-use and assign the business percentage (car 40%, electricity 30%, phone 70%).
- Run a Modelo 303 and Modelo 130 calculation and see whether those percentages actually affect the figures.

## My session

### Step 1 — Profile creation

I ran `aeat --help` first to understand the structure. The overview is clear: `config` for setup, `app` for tax work. I found `aeat config profile create` and tried to use `--tax-residence-community` because that sounded natural — got an error saying `Did you mean --tax-residence-ccaa?`. Once I corrected the flag name, the profile created in one shot. The confirmation output was minimal but sufficient.

```
CMD: aeat config profile create quim ... --tax-residence-community cataluna
OUTPUT: Error: No such option: --tax-residence-community Did you mean --tax-residence-ccaa?
EXIT: 2

CMD: aeat config profile create quim ... --tax-residence-ccaa cataluna
OUTPUT: profile quim / status created
EXIT: 0
```

Felt: cosmetic friction on the flag name. Help shows `--tax-residence-ccaa` but the "community" phrasing is what a Spanish taxpayer would type.

### Step 2 — Import

`aeat app overview status` told me to use `--provider csv`. I created a simple CSV with six rows (electricity, fuel, phone × two months). Import worked first time without error. `ledger list` showed all six entries with short IDs and status `pending`. Clean.

```
CMD: aeat app ledger import extracto_quim.csv --provider csv
OUTPUT: Filas 6 / Entradas importadas 6 / Omitidos 0
EXIT: 0
```

Felt: smooth. The `csv` provider accepting a standard Date/Description/Amount/Balance file without documentation or schema hints is good.

### Step 3 — Mixed-use classification (BLOCKED)

This is where the workflow completely stopped. The whole point of Quim's scenario is that expenses are MIXED — part personal, part business. The `ledger classify` help shows `MIXED` as a valid `--classification` value. But every attempt to use it was refused:

```
CMD: aeat app ledger classify --id 3181ed1e --classification MIXED
OUTPUT: Refused. The command input failed validation. Run `aeat config repair` or reset the profile state.
EXIT: 2
```

I tried: short ID, full 64-char hash, adding `--iva-rate`, adding `--taxable-base`, adding `--category-id`. All refused with the same message. I ran `aeat config repair` — it reported only two warnings (auth not configured, venv stale), nothing relevant to classify validation. I reset the ledger, reimported, and tried again. Still refused.

`BUSINESS` and `PERSONAL` classifications both accepted (when the import graph was stable — see Bug 2 below), but `MIXED` is silently forbidden regardless of what additional fields I supply.

### Step 4 — Allocate (reached via workaround)

Since MIXED was blocked, I classified the entries as BUSINESS and then ran `allocate` to set the proportions anyway:

```
CMD: aeat app ledger classify --id d3577f34 --classification BUSINESS
EXIT: 0

CMD: aeat app ledger allocate --id d3577f34 --business-pct 0.40
OUTPUT: ID ... / Importe -80 / Estado de revisión reviewed
EXIT: 0
```

`allocate` accepted 0.40 without error. But `ledger view` after the allocation shows nothing about the business percentage — the entry looks identical before and after the allocate call. There is no confirmation that 40% was stored, no field showing it back to me.

### Step 5 — Modelo 303 calculation

I found the right revision (`2009-y-siguientes`) from `bindings list`, created a work unit, and ran the calculation. It succeeded with exit 0 but produced all zeros:

```
CMD: aeat app modelo work calculate 5b978afdb0...
OUTPUT:
  casilla iva.cuota-deducible-total    0.00
  casilla iva.soportado.interiores     0
  casilla iva.resultado                0.00
  [all 21 casillas = 0]
EXIT: 0
```

Six classified-and-allocated ledger entries, all in Q1 2026, and the 303 for Q1 2026 produces zero IVA soportado. The ledger data is not flowing into the binding aggregation.

### Step 6 — Modelo 130 calculation

The 130 calculation demanded a prior-period binding value that the system had no way to auto-fill, and gave a hard error:

```
CMD: aeat app modelo work calculate 3925b2655b...
OUTPUT: Error. La vinculación irpf.previous_year_economic_activity_net_income no tiene valor asignado.
EXIT: 1
```

I worked around it with `--binding "irpf.previous_year_economic_activity_net_income=0"`. The calculation ran but also returned zeros for all income/expense casillas — the ledger data was not picked up here either. Casilla 13 showed 100.00 and 14 showed -100.00, which appear to be hardcoded minimums, not derived from my transactions.

### Step 7 — Intermittent import crash

During the session I observed two ImportError crashes that prevented the CLI from starting at all:

```
ImportError: cannot import name 'DisenoCompletenessCasilla' from 'aeat.domain.calculations.registry._schema'
EXIT: 1

ImportError: cannot import name 'DerivedManifestCasilla' from 'aeat.domain.calculations.registry._record_design'
EXIT: 1
```

These crashes are non-deterministic — the same command may succeed on one invocation and fail on the next. This indicates a mid-refactor import graph where some symbols have been renamed or moved but not all call sites are updated.

## Did it work?

**No.** The core goal — set a business-use percentage on a mixed-use expense and verify it flows into a modelo calculation — was not achievable. Two independent blockers prevented it:

- `MIXED` classification is silently refused by validation with no actionable error message.
- Even via the BUSINESS workaround, `allocate` claims success but the percentage is invisible in `view` and produces no effect in the 303 or 130 calculation (all casillas remain zero).

The profile creation, CSV import, BUSINESS/PERSONAL classification, and modelo work-unit creation are all functional. The calculation engine runs but produces empty output for a non-trivial ledger.

## Bugs and gaps

**Bug 1 — BLOCKER**
Command: `aeat app ledger classify --id <id> --classification MIXED`
Expected: Entry classified as mixed-use, business proportion can then be set via `allocate`.
Actual: `Refused. The command input failed validation. Run aeat config repair or reset the profile state.` — unhelpful message, repair reports nothing wrong, no path forward for mixed-use expenses.
Severity: BLOCKER — the entire mixed-use proportionality workflow is unreachable.

**Bug 2 — BLOCKER**
Command: `aeat app modelo work calculate --help` (and other CLI commands, intermittently)
Expected: Help text displayed.
Actual: `ImportError: cannot import name 'DisenoCompletenessCasilla' from 'aeat.domain.calculations.registry._schema'` / `ImportError: cannot import name 'DerivedManifestCasilla' from 'aeat.domain.calculations.registry._record_design'` — full traceback, CLI unusable.
Severity: BLOCKER — non-deterministic import crashes make the CLI unreliable. Root cause: mid-refactor symbol renames in the registry module are not yet consistent across all call sites.

**Bug 3 — MAJOR**
Command: `aeat app modelo work calculate <work-unit-id>` (303, Q1 2026, after classifying 6 Q1 ledger entries)
Expected: `iva.soportado.interiores` and `iva.cuota-deducible-total` reflect the IVA on classified business expenses.
Actual: All IVA casillas are 0. Ledger entries classified as BUSINESS with IVA-rate data are not aggregated into the `ledger_iva_aggregation` bindings. The binding `borrador_capable=False` may be the cause — it is unclear from the CLI what this means for calculation readiness.
Severity: MAJOR — even if MIXED were unblocked, the ledger→modelo pipeline does not currently produce non-zero output from ledger data.

**Bug 4 — MAJOR**
Command: `aeat app ledger view <id>` after `aeat app ledger allocate --id <id> --business-pct 0.40`
Expected: View shows the stored business-use percentage (e.g. `uso_profesional: 40%`).
Actual: View output is identical before and after allocate — no confirmation that the value was persisted. There is no way for the operator to verify that `allocate` had any effect.
Severity: MAJOR — silent persistence of a key tax parameter with no operator-visible confirmation.

**Bug 5 — MAJOR**
Command: `aeat app modelo work calculate <130-work-unit>`
Expected: Ledger income/expense entries classified as BUSINESS contribute to IRPF casillas 01 (ingresos) and 02 (gastos deducibles).
Actual: All casillas 01–12 are zero. Casilla 13 (100.00) and derived negatives appear to be hardcoded minimums unrelated to ledger data.
Severity: MAJOR — Modelo 130 income/expense ledger pipeline is not wired to the calculation engine.

**Bug 6 — MINOR**
Command: `aeat config profile create ... --tax-residence-community cataluna`
Expected: Accepted or better error like "use --tax-residence-ccaa".
Actual: `No such option: --tax-residence-community Did you mean --tax-residence-ccaa?`
Severity: MINOR — the error message is actually helpful, but `--tax-residence-community` is a plausible alias that could be added to reduce friction for Spanish taxpayers unfamiliar with CCAA abbreviation.

**Gap 1 — MAJOR**
There is no way to discover valid category IDs from the CLI. `ledger classify --category-id` accepts a text value but there is no `category list` or similar command. A non-expert user has no idea what to pass here.

**Gap 2 — MINOR**
`ledger status` does not show how many entries have had `allocate` called on them, nor what the stored percentages are. After the `allocate` workflow there is no summary surface showing "3 entries with mixed-use allocation: car 40%, electricity 30%, phone 70%".

## Recommendations

- Unblock `MIXED` classification: investigate the validation rule that refuses it and expose the specific field constraint in the error message.
- Fix the import graph: resolve the `DisenoCompletenessCasilla` / `DerivedManifestCasilla` symbol rename across all call sites in `aeat.domain.calculations.registry`.
- Wire the `ledger_iva_aggregation` binding resolver to pull from classified ledger entries; confirm what `borrador_capable=False` means for the calculation path.
- Surface stored `business_pct` in `ledger view` output so the operator can confirm allocation was persisted.
- Add a `category list` or `ledger categories` discovery command so users know what valid category IDs exist.
