# Doc-fix-agent brief — correct user-facing pages against the live CLI

You fix assigned documentation page(s) so a naive user following them literally reaches
the documented outcome. Ground every change in the LIVE CLI and the audit findings.

Repo: `Y:\code\aeat-worktrees\chore-476-restructure-execution`. Audit with all findings:
`.vault/audit/2026-06-18-aeat-user-docs-hardening-audit.md` (read the findings for YOUR page).

## Rules
- NO destructive git (see the fix brief's list). `git diff -- <page>` / `git log -1 -- <page>`
  before editing; abort on peer WIP. Edit ONLY your assigned page(s). Do NOT commit.
- Style: `aeat-user-docs-hardening` (simple, singular, imperative steps; taxpayer-general
  terms — NIF/CIF/DNI/NIE, not "autónomos"); `aeat-documentation-workflow` tone. No
  self-praise. Keep prose minimal and concrete.
- VERIFY every command you keep/add against the live CLI in an isolated runtime:
  `cd <repo> && source .agents/persona_env.sh /tmp/doc-<slug> && uv run --no-sync aeat …`
  (the harness sets the passphrase + isolates state). Quote real output; never invent a flag.

## Systemic fixes to apply where your page touches them
- **Passphrase (S-PASS):** state once that the tool needs a master-key passphrase (prompted
  interactively, or `AEAT_SECRET_PASSPHRASE` non-interactively).
- **Prerequisites (S-PREREQ):** if a command needs an active profile and/or a work unit,
  give the runnable command inline (don't only link away). Profile-create examples MUST
  include `--quiet` for the non-interactive form (S-QUIET) — a bare `profile create NAME`
  enters an interactive wizard.
- **JSON is a GLOBAL flag (S-DRIFT):** machine-readable output is `aeat --format json <cmd>`
  (the flag goes BEFORE the subcommand). `aeat <cmd> --format json` does NOT exist. Fix any
  such citation (e.g. `config check --format json` → `aeat --format json config check`).
- **Nonexistent commands/flags (S-DRIFT):** replace any cited command/flag that the live CLI
  rejects with the real one (verify with `--help`).
- **Spanish runtime (S-LANG):** the CLI emits Spanish help/messages; if your page quotes a
  refusal in English ```text``` blocks, either show the real Spanish or note runtime is Spanish.
- **Live-AEAT auth (S-AUTH):** live `pull` verbs refuse when AEAT auth is unconfigured;
  describe that (not just "log in").

## The proven from-nothing → BOE chain (canonical reference — verified working)
A first-period filer reaches a `.boe` from an empty store like this (303 shown; 130 differs
only at calculate — see below):
```
aeat config profile create me --quiet --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" \
  --activity "consultoria" --activity-start-date 2026-01-01
aeat app ledger add --date 2026-02-10 --amount 1210 --direction INCOMING --description "venta" \
  --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210
aeat app ledger add --date 2026-02-11 --amount 605 --direction OUTGOING --description "compra" \
  --classification BUSINESS --category-id material_oficina --taxable-base 500 --iva-rate 0.21 --iva-amount 105
aeat app modelo work create --modelo 303 --year 2026 --period 1T
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T
aeat app modelo work verify --modelo 303 --year 2026 --period 1T      # completeness complete / granted true
aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./m303.boe   # writes the .boe
```
Load-bearing facts a page must not omit:
- The profile MUST carry `--name` and `--surnames` or `export` refuses ("requires the operator name").
- `--activity-start-date` scopes out the prior-period cross-period dependency for a first period.
- For **Modelo 130**, `calculate` additionally needs `--casilla 02=0` (gastos, required even at 0)
  and the first-period prior bindings `--binding modelo-130-resultados-negativos-anteriores=0
  --binding modelo-130-pagos-fraccionados-anteriores=0 --binding
  irpf.previous_year_economic_activity_net_income=0`.
- `ledger add --amount` is the GROSS (taxable_base + iva_amount); expense rows need `--category-id`.

## Verify before finishing
- Re-run your page's commands end-to-end in the isolated runtime; they must succeed/refuse as written.
- Run the doc conformance gates and keep them green:
  `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration -q`
  and `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_educational_docs_conformance.py -q`.
- Report (≤15 lines): page(s) changed, the key corrections, the e2e commands you re-verified,
  gates green, any peer-WIP abort.
