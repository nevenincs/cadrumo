# Testimonial — Prepare a Modelo 303 IVA filing

- Doc path: `docs/how-to/modelo-303.md`
- Persona: a first-time user preparing a quarterly IVA return (Modelo 303) end to end — create work unit, add ledger rows with IVA, calculate, review repercutido/soportado/resultado, verify, export.
- Date: 2026-06-18
- Environment: `BASE=/tmp/persona-303-fg`, CLI via `uv run --no-sync aeat`, passphrase pre-set, all commands non-interactive (`</dev/null`).

## Walkthrough

### Pre-step (not on page but forced): create a profile
- **Command:** `aeat app modelo work create --modelo 303 --year 2026 --period 1T` (the page's FIRST documented command, run with no profile)
- **Expected:** The page's first command should work, or the page should tell me to create a profile first with a concrete command.
- **Actual:** `Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.`
- **Verdict:** DOC-ISSUE, MAJOR — the page's "Before you create the draft" section only *links* to `profile-setup.md`; it never prints a runnable create command, so the very first documented command refuses for a naive user. (The CLI refusal itself is graceful and instructive — APP OK.)
- Workaround used: `aeat config profile create persona303 --quiet --accept-defaults --tax-id 12345678Z --activity "Servicios de consultoria"`.

### 1. `aeat app modelo work create --modelo 303 --year 2026 --period 1T`
- **Expected:** Create or reuse the work unit.
- **Actual:** `status created`, `revision_id 2023-y-siguientes`, plus a `recargo`/overdue advisory (`days_overdue 59`, `AVISO: plazo voluntario vencido`).
- **Verdict:** OK. Idempotency claim plausible; the overdue advisory is helpful and unprompted.

### 2. `aeat app modelo work status --modelo 303 --year 2026 --period 1T`
- **Expected:** Show the saved work unit.
- **Actual:** Full status block, same ids, same overdue advisory.
- **Verdict:** OK.

### 3. `aeat app ledger preflight --year 2026 --period 1T` / `aeat app ledger status --year 2026 --period 1T`
- **Expected:** Check the ledger window before calculating.
- **Actual (empty ledger):** preflight `checked 0, issues 0, ready true`; status `Filas 0 ... Preparado True`.
- **Verdict:** OK. (Empty ledger is trivially "ready" — reasonable.)

### 4. `aeat app modelo work calculate --modelo 303 --year 2026 --period 1T` (empty ledger)
- **Expected:** Calculate a draft.
- **Actual:** Saved a borrador revision with every casilla 0.00.
- **Verdict:** OK. Calculation works with no rows.

### 5. Add ledger rows (persona task)
- **Command (from brief, verbatim):** `aeat app ledger add --date 2026-02-10 --amount 1000 --direction INCOMING --description "venta" --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210`
- **Expected:** Add a sale row with IVA.
- **Actual:** Refused — `taxable_base + iva_amount must equal the gross to the cent: 1000 + 210 = 1210.00 != 1000.00`. The error also dumped a ~30-line raw pydantic `RawTransaction(...)` repr to the operator.
- **Verdict:** APP-ISSUE, MINOR (BOTH on the brief's example) — the model requires `--amount` to be the GROSS (= base + IVA). The brief's example is internally inconsistent; the page never shows a ledger-add example at all, so a naive user has no template. The raw-pydantic dump is poor error ergonomics for an operator.
- Re-run with coherent gross: `--amount 1210 --taxable-base 1000 --iva-amount 210` → added OK (id `cd74...`, `Estado de revisión reviewed`).
- Added an OUTGOING purchase: `--amount 605 --taxable-base 500 --iva-rate 0.21 --iva-amount 105` → added OK (id `bac9...`).

### 6. Re-run preflight after adding rows
- **Actual:** `ready false`, issue `bac9... missing_category ... deductible-expense ledger transaction has no category_id`.
- **Verdict:** OK (app correctly enforces the page's "needs enough IVA detail" promise). DOC gap: the page never tells the user that expense rows additionally need a `--category-id`, nor how to set it. Discovered only via `aeat app ledger categories` (a command the page doesn't mention).

### 7. Calculate with an unready ledger
- **Actual:** `Error. ledger preflight blocks modelo calculation: transaction bac9... missing_category: %{detail}. Run aeat app ledger preflight --period 2026 1T before calculating.`
- **Verdict:** APP-ISSUE, MINOR — (a) the locale placeholder `%{detail}` leaked unrendered into the operator message; (b) the inline suggested command `--period 2026 1T` is malformed (year stuffed into `--period`), while the structured `-> Run aeat app ledger preflight --period 1T --year 2026` line below it is correct. Two conflicting forms confuse a naive reader.

### 8. Fix category, recalculate
- `aeat app ledger classify bac9... --classification BUSINESS --category-id material_oficina --taxable-base 500 --iva-rate 0.21 --iva-amount 105` → OK; preflight `ready true`.
- `aeat app modelo work calculate ...` → saved borrador revision.
- **IVA coherence check (the core persona goal):**
  - `iva.cuota-devengada-total = 210.00` (repercutido general 210) ✓
  - `iva.cuota-deducible-total = 105.00` (soportado interiores 105) ✓
  - `iva.resultado-regimen-general = 105.00` (210 − 105) ✓
  - casilla 27 (devengada) = 210.00, casilla 64 (suma resultados) = 105.00 ✓
  - **BUT casilla 66 = 0.00, `iva.resultado` = 0.00, casilla 71 (Resultado final) = 0.00.**
- **Verdict:** APP-ISSUE, MAJOR — the repercutido/soportado/intermediate result are coherent (210/105/105), but the FINAL official result casilla 71 reads 0.00 for a 105 EUR liability. Root cause: casilla 65 "Porcentaje atribuible a la Administración del Estado" resolves to 0 (binding `modelo-303-profile-state-attribution-ratio` shows under `bindings list --missing`), so casilla 66 = [64]×[65]/100 = 0, cascading 69→71 to 0. For an ordinary peninsular taxpayer this percentage should default to 100. As-is, the headline result a user reads (casilla 71 = 0) contradicts the key-figure summary (resultado-regimen-general = 105) — exactly the kind of silent zero a filer could trust. Also: casilla 46 ("Resultado régimen general") is referenced by casilla 64's formula but is absent from the calculate output entirely.

### 9. Review revisions / revision
- `aeat app modelo work revisions ...` → 2 borrador revisions listed. OK.
- `aeat app modelo work revision ...` → key-figure summary surfaces the same contradiction (resultado-regimen-general 105.00 next to casilla 71 / iva.resultado 0.00). OK as a view; the contradiction is the §8 finding.

### 10. iva-wallet commands
- `aeat app modelo iva-wallet balance --as-of-year 2026` → `total_balance 0`. OK.
- `aeat app modelo iva-wallet seed --filing-year 2024 --period 4T --amount 0 --confirm` → `status seeded`. OK.
- **Verdict:** OK individually, but see §11 — the page seeds **2024 4T**, while verification actually demands **2025 4T** (the immediately previous period). The documented seed does not satisfy the dependency the verify step raises.

### 11. `aeat app modelo work verify --modelo 303 --year 2026 --period 1T`
- **Expected:** Verify the draft against the verified-complete contract; export next.
- **Actual:** `completeness_status blocked`, `granted_verificado_completo false`, 3 blocking `cross_period_dependency_unclean` findings for `modelo=303 year=2025 period=4T` (missing observation / current filing record). Third finding instructively suggests recording an activity-start date if this is the first period of activity.
- **Verdict:** BOTH, MAJOR — the page presents verify→export as the closing happy path and only mentions seeding the wallet for "a true first Modelo 303 period," but verification blocks on the **previous period's** filing evidence regardless, and the page's seed example (2024 4T) targets the wrong period (needs 2025 4T). A naive user following the page cannot reach a verified draft.

### 12. Follow the finding: set activity-start date, recalc, reverify
- `aeat config profile edit persona303 --quiet --activity-start-date 2026-01-01` → updated.
- recalc → reused content-equivalent revision.
- reverify → `Refused. Draft f6984f7888321b07 not ready: status=BORRADOR` / `abort_code: DRAFT_HAS_ERRORS` / `stage: ABORTED`.
- **Verdict:** APP-ISSUE, MAJOR — after taking the finding's own suggested remedy, verify now fails with an OPAQUE error (`DRAFT_HAS_ERRORS`) that lists no findings, contradicting the page's promise that verify "exposes... findings with legal/source references." The detailed-findings path (§11) and the bare-abort path (§12) are inconsistent.

### 13. `aeat app modelo export ... --output ./modelo-303.boe` and `aeat app modelo work file ...`
- **Actual:** export → `Invalid value: current revision is still draft; verify it before exporting`. file → `... is in state 'borrador'; filing requires a verified-complete revision`.
- **Verdict:** OK (graceful, instructive refusals), but the documented end-to-end flow terminates here: with verify unreachable, export and file are unreachable too.

## Findings

1. **[MAJOR][DOC]** The page's first documented command (`work create`) refuses with "No hay un perfil activo" because the "Before you create the draft" section only links to profile-setup instead of printing a runnable `aeat config profile create ...` command. Repro: run the first code block with no profile. Fix: add a concrete create command (or an explicit "you must have created a profile" precondition with the command inline).

2. **[MAJOR][APP]** Final result casilla 71 = 0.00 for a clearly positive liability (devengada 210, deducible 105, resultado-regimen-general 105). Cause: casilla 65 "% atribuible a la Administración del Estado" (binding `modelo-303-profile-state-attribution-ratio`) defaults to 0, so casilla 66 and the 69→71 chain zero out. Repro: §8 above. Fix: default the state-attribution ratio to 100 for ordinary (non-foral) profiles, or surface it as a required missing input that blocks rather than silently zeroing the headline result. (Touches `no-silent-under-declaration`.)

3. **[MAJOR][BOTH]** verify→export happy path is unreachable. Verify blocks on the previous period (2025 4T) cross-period dependency; the page's only carry-forward guidance is `iva-wallet seed --filing-year 2024 --period 4T`, which targets the wrong period. Repro: §10–§11. Fix: either document that verify requires the immediately-prior-period filing/evidence (and how to satisfy it for a fresh setup), or correct the seed example to the prior period and explain the activity-start-date scope-out.

4. **[MAJOR][APP]** After applying the verify finding's own remedy (recording activity-start date), reverify returns an opaque `Refused ... DRAFT_HAS_ERRORS` with no findings list — inconsistent with the detailed-findings verify path and with the page's promise that verify exposes findings. Repro: §12. Fix: make the `DRAFT_HAS_ERRORS` abort enumerate the underlying draft errors.

5. **[MINOR][APP]** `calculate` blocked-by-preflight error leaks an unrendered locale placeholder `%{detail}` and prints a malformed inline command `aeat app ledger preflight --period 2026 1T` (year inside `--period`) alongside a correct structured `-> Run` line. Repro: §7. Fix: render `%{detail}`; drop or correct the malformed inline command.

6. **[MINOR][DOC]** The page says rows need "enough IVA detail" but never mentions that deductible-expense rows additionally require a `--category-id`, nor the `aeat app ledger categories` command to discover valid ids. A naive user hits `missing_category` at preflight with no documented next step. Repro: §6. Fix: note the category requirement for expense rows and link the categories command.

7. **[MINOR][APP]** `aeat app ledger add` validation failure dumps a ~30-line raw pydantic `RawTransaction(...)` repr to the operator instead of a one-line message. Repro: §5. Fix: surface only the human-readable `TransactionValidationError` text.

8. **[NIT][DOC]** The page never warns that a master-key passphrase is required (per brief, that itself is a finding). A naive user in a non-interactive shell would be blocked at first secure-storage access. Fix: add a one-line passphrase note or link.

9. **[NIT][APP]** `aeat config profile` with no subcommand prints help, but the overview/help text implies it "inspects the active profile." Minor inconsistency for a newcomer; the real inspect is `aeat config profile status`.

## Testimonial (first person)

Getting started tripped me immediately: the very first command on the page refused because I had no profile, and the page only linked elsewhere instead of giving me the command — so I was stuck before step one. Once I had a profile, the core IVA mechanics actually felt solid: I added a sale and a purchase, preflight caught a genuinely missing expense category, and calculation produced coherent repercutido (210), soportado (105), and régimen-general result (105). But the moment I looked at the official final box (casilla 71) it read 0.00 — the headline result silently contradicted the 105 I'd just seen, which would have badly misled me. And I could never finish: verification blocked on a previous-period dependency the page's wallet-seed example didn't address, and when I followed verify's own suggested fix it degraded to an opaque `DRAFT_HAS_ERRORS` with no findings. The refusals were polite, but the page's promised end-to-end "calculate → verify → export" never completed.

## Scorecard
- Doc clarity: 2 / 5
- App capability: 3 / 5
- Findings by severity: BLOCKER 0, MAJOR 4, MINOR 3, NIT 2 (total 9)
