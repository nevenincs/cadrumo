---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-briefs-audit]]'
---

# Live IVA compensation wallet W04 persona testimonials

Date: 2026-05-21

Environment: disposable local CLI state under `.tmp/w04-persona-cli`.

Safety boundary: no live AEAT command was executed. No real taxpayer secret was entered. The live wallet persona inspected help and local history only.

## Commands and redacted outputs

### First-run autónomo persona

Commands:

- `uv run aeat config profile create persona-autonomo --quiet --accept-defaults --tax-id <synthetic-taxpayer-ref> --name Persona --surnames Autonomo --iva-regime GENERAL --tax-residence-ccaa madrid`
- `uv run aeat config profile create persona-autonomo --quiet --accept-defaults --tax-id <synthetic-taxpayer-ref> --name Persona --surnames Autonomo --activity consultoria --iva-regime GENERAL --tax-residence-ccaa madrid`
- `uv run aeat app modelo work create --modelo 303 --year 2026 --period 1T --revision 2009-y-siguientes --by persona-autonomo`
- `uv run aeat app modelo work calculate <work-unit-id> --by persona-autonomo`

Observed:

- Profile creation refused the first attempt because `activity` was still required under `--quiet --accept-defaults`.
- The successful create output showed `next aeat app modelo work create`.
- Modelo 303 work-unit creation returned a work-unit id.
- Calculation succeeded with all IVA values at zero before any accepted ledger evidence existed.

Testimonial:

"The profile setup told me the next command, which helped. The friction was that `--accept-defaults` still needed `activity`, and the Modelo 303 calculation looked successful even though I had not entered usable ledger evidence."

### Returning accountant persona

Commands:

- `uv run aeat app ledger add --date 2026-02-10 --amount 121.00 --direction INCOMING --description "Persona sale" --classification BUSINESS --business-pct 1 --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00 --category-id ventas --actor persona-autonomo`
- `uv run aeat app ledger categories`
- `uv run aeat app ledger add --date 2026-02-10 --amount 121.00 --direction INCOMING --description "Persona sale" --classification BUSINESS --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00 --actor persona-autonomo`
- `uv run aeat app ledger preflight --period 2026Q1`
- `uv run aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing`
- `uv run aeat app modelo readiness --modelo 303 --revision-id 2009-y-siguientes --year 2026 --period 1T`
- `uv run aeat app modelo work calculate <work-unit-id> --by persona-autonomo`

Observed:

- `--category-id ventas` was rejected and the CLI correctly pointed to `aeat app ledger categories`.
- `--business-pct 1` was rejected for `classification BUSINESS`; the message explained that `business_pct` is only valid for `MIXED`.
- A ledger row without `category_id` was accepted.
- `ledger preflight --period 2026Q1` reported `ready false` with `missing_category`.
- `modelo readiness` still reported `ready True` for Modelo 303.
- Re-running Modelo 303 calculation after the ledger row still returned the existing zero-valued draft revision.

Testimonial:

"The ledger preflight correctly found the missing category, but Modelo readiness did not inherit that blocking state. I would not know that the zero Modelo 303 draft is unsafe unless I remembered to run ledger preflight separately."

### Live-wallet reviewer persona

Commands:

- `uv run aeat app live iva-wallet --help`
- `uv run aeat app live iva-wallet pull --help`
- `uv run aeat app live iva-wallet history`

Observed:

- The live wallet group describes itself as read-only capture.
- `pull` requires `--year` and `--period`; `--taxpayer-nif` is optional.
- Local history returned `row_count=0`.
- No live `pull` command was run.

Testimonial:

"The help text says read-only, which is good. The safer boundary would be even clearer if `pull --help` stated that representation-gate submission is refused and that no form choices are posted to AEAT."

### Multiyear compensation reviewer persona

Commands:

- `uv run aeat app live iva-wallet history --help`
- `uv run aeat app live iva-wallet capture-history --help`
- `uv run aeat app modelo work revisions --work-unit-id <work-unit-id>`
- `uv run aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing`

Observed:

- `iva-wallet history` help states that it lists secure local compensation history, but the command output for an empty store is only `row_count=0`.
- The Modelo 303 bindings list shows `modelo-303-compensacion-pendiente-anteriores` as `previous_filing`, but does not show source-period age or authority decision state.
- No CLI output currently exposes carry-forward lot age, expiry review state, or wallet/local/override authority-source records.

Testimonial:

"I can see that prior compensation is a previous-filing binding, but I cannot inspect the source-year/source-period lot, age, remaining amount, or authority decision from the CLI."

## Safety observations

- No CLI dry-run contacted AEAT.
- No live wallet pull was executed.
- `modelo work file` help explicitly says it marks an internal filing and does not submit to AEAT.
- `modelo export` help explicitly says local-only and never contacts AEAT, but export remains legally sensitive because it creates a submission-ready local artifact.
