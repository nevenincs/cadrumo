# Persona testimonial harness — proven CLI recipe

This is the **verified** end-to-end recipe the coordinator confirmed on 2026-06-18
against the live `aeat` CLI on branch `chore/eliminate-shims`. Follow it exactly;
deviate only where your persona's task differs, and record every deviation.

## 0. Golden rules
- Run **every** command with `uv run --no-sync aeat ...` from the repo root
  `Y:/code/aeat-worktrees/chore-476-restructure-execution`.
- You operate the **real backend**. No mocks, no fakes. Report what actually happened.
- **NEVER** run destructive git (`stash`/`reset`/`checkout <path>`/`clean`/`rebase`).
  You do not need git at all. Touch only your own isolated storage root + your testimonial file.
- **Never** perform live AEAT submission. Local export to `.boe` only.
- Be concise in tool calls. Use `2>&1 | tail -N` to keep output small.
- If a command errors, read the error, adjust, retry. The CLI errors are instructive
  and usually name the exact flag/binding/casilla you must supply.

## 1. Per-persona isolation (MANDATORY — set in EVERY bash call)
Each persona gets its own storage root AND its own secret-store dir, or you will
collide with peers and hit "passphrase does not open the master key".

```bash
cd "Y:/code/aeat-worktrees/chore-476-restructure-execution"
ROOT="$(pwd)/tmp/personas/<YOUR-SLUG>"
export AEAT_LOCAL_STORAGE_ROOT="$ROOT"
export AEAT_SECRET_STORE_DIR="$ROOT/secrets"      # CRITICAL: default var/secrets is GLOBAL
export AEAT_SECRET_STORE_BACKEND=file             # encrypted-file custody under your root
export AEAT_SECRET_PASSPHRASE="<YOUR-CUSTOM-PASSWORD>"   # >= 12 chars
export AEAT_ACTIVE_PROFILE=<your-profile-name>
```
Re-export these in **every** Bash tool call (shell env does not persist between calls).
Start clean once: `rm -rf "$ROOT"; mkdir -p "$ROOT"` (only your own root, never anyone else's).

## 2. Create the profile with a custom password
```bash
uv run --no-sync aeat config profile create <profile> --quiet --accept-defaults \
  --tax-id <NIF> --name "<Name>" --surnames "<Surnames/RazonSocial>" \
  --activity "<actividad>" --entity-type <natural_person|legal_entity|attribution_entity> \
  --activity-start-date <YYYY-01-01>
uv run --no-sync aeat config profile status        # expect identity/activity populated
```
- `--entity-type` values: `natural_person` (autónomo/individual), `legal_entity` (SL/SA company),
  `attribution_entity` (CB/SC).
- `--activity-start-date` is what scopes out prior-year cross-period dependencies for a
  first-year filer. Set it to the start of your first declared year unless your persona
  explicitly has prior-year history (then you must supply prior evidence instead).
- For companies add `--legal-entity-form` and `--incn-prior-12-months` as your task needs;
  run `aeat config profile create --help` to see the full flag set.

## 3. Prepare & import financial data
CSV is **semicolon-separated, Spanish headers**, comma decimals, dd/mm/YYYY dates.
Positive Importe = income (INCOMING), negative = expense (OUTGOING).
```
Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda
15/01/2024;15/01/2024;Cobro factura F-2024-001;5000,00;5000,00;EUR
10/03/2024;10/03/2024;Pago asesoria fiscal;-300,00;4700,00;EUR
```
```bash
uv run --no-sync aeat app ledger import "$ROOT/stmt.csv" --provider auto --dry-run
uv run --no-sync aeat app ledger import "$ROOT/stmt.csv" --provider auto
uv run --no-sync aeat app ledger list        # capture the short 8-char ids
```

## 4. Classify (preflight needs fiscal facts on EVERY tx)
Preflight/verify require `taxable_base`, `iva_rate`, `iva_amount` on each transaction.
A €5000 gross invoice at 21% = base 4132.23 + IVA 867.77 (gross = base × 1.21).
```bash
# income
uv run --no-sync aeat app ledger classify <id> --classification BUSINESS \
  --taxable-base 4132.23 --iva-rate 0.21 --iva-amount 867.77 --iva-category domestic_general_21
# expense (needs a deductible category-id from `aeat app ledger categories`)
uv run --no-sync aeat app ledger classify <id> --classification BUSINESS --category-id asesoria_fiscal \
  --taxable-base 247.93 --iva-rate 0.21 --iva-amount 52.07 --iva-category domestic_general_21
uv run --no-sync aeat app ledger preflight --year <YYYY> --period <P>   # want issues 0, ready true
```

## 5. Modelo lifecycle
```bash
uv run --no-sync aeat app modelo work create   --modelo <M> --year <YYYY> --period <P>
uv run --no-sync aeat app modelo work calculate --modelo <M> --year <YYYY> --period <P> [--binding K=V ...] [--casilla NN=VALUE ...]
uv run --no-sync aeat app modelo work revision  --modelo <M> --year <YYYY> --period <P>   # read the casilla table
uv run --no-sync aeat app modelo work verify    --modelo <M> --year <YYYY> --period <P>   # want granted_verificado_completo true
uv run --no-sync aeat app modelo export         --modelo <M> --year <YYYY> --period <P> --output "$ROOT/<file>.boe"
```
- If calculate errors "la vinculación X no tiene valor asignado", supply `--binding X=VALUE`.
  Discover all needed bindings: `aeat app modelo bindings list --modelo <M> --year <YYYY> --period <P> --missing`.
- If verify reports `missing_required_casilla NN` (blocking), re-calculate adding `--casilla NN=VALUE`.
- `advisory`/`warning` findings do NOT block export; only `blocking` findings do.
- Export refuses a draft revision — verify must grant first.

## KNOWN BACKEND BEHAVIOURS (already confirmed by coordinator — confirm or refute, don't re-discover for hours)
- **F2 expense drop**: M130 does NOT auto-aggregate deductible OUTGOING expenses into casilla 02
  (Gastos). Income aggregates into casilla 01; expenses are dropped with an `AVISO`. You must
  declare gastos manually via `--casilla 02=<sum of expense bases>`. Note whether your modelo
  shows the same gap.
- **F3 cross-period gate**: prior-period bindings (e.g. M130's previous_year net income from
  M100) block verify unless evidence exists or `activity-start-date` scopes the pre-activity
  dependency out.
- **F1 isolation**: default secret-store custody is global (`var/secrets`); the `AEAT_SECRET_STORE_DIR`
  override above is what makes each persona independent.

## TESTIMONIAL — write to `.agents/testimonials/<YOUR-SLUG>.md`
Use first-person persona voice for the narrative, then a factual section. Include:
1. **Persona** — who you are, what you needed to file.
2. **What worked** — steps that succeeded first try.
3. **Friction / breakage** — every error, what it said, how many tries, whether the message
   was actionable. Call out anything confusing, mis-ordered, or that a real taxpayer would
   fail at.
4. **Input → Output reconciliation** — a table: each input number (income bases, expense
   bases, IVA) and the resulting casillas. State expected vs actual and whether they match.
   For cross-period: show that each period's "prior payments" casilla equals the sum of
   earlier periods' results.
5. **Final artefact** — the `.boe` path, byte_size, file_sha256 from the export output.
6. **Findings** — numbered list of bugs/gaps with severity (CRITICAL/HIGH/MEDIUM/LOW) and the
   exact command + output that proves each. Distinguish "works as designed but confusing" from
   "wrong number / data loss".
7. **Verdict** — did you reach a compliant `.boe`? Would a real persona of your type succeed
   unaided?

Return a SHORT summary as your final message (the coordinator reads that): verdict, the .boe
sha256, headline reconciliation result, and your top 1-3 findings. The full detail goes in the file.
