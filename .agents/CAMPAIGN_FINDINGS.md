# Documentation persona campaign — verified findings ledger

Running ledger of findings surfaced by per-document naive-user personas and
**confirmed against HEAD** by the coordinator. Persona testimonials live in
`.agents/testimonials/<doc>.md`. Severity: BLOCKER / MAJOR / MINOR / NIT.
Status: `confirmed` (coordinator-reproduced) · `reported` (persona only, not yet re-run).

## Confirmed bugs (APP)

- **[BLOCKER][APP] `config profile history --since/--until` crashes** — `TypeError: can't
  compare offset-naive and offset-aware datetimes` at
  `src/aeat/entrypoints/cli/_config/_bucket_history.py:178`
  (`event.occurred_at < since_dt`). Emits a raw traceback and a misleading
  `repair integrity` hint. The filter is documented in `profile-setup.md`.
  Repro: `aeat config profile history <name> --since 2026-01-01 --until 2026-03-31`.
  Source: profile-setup persona. **confirmed**.

- **[MINOR][APP] `ledger import <missing-file>` dumps a traceback** — a non-existent
  import path raises `FileNotFoundError` (full stack) plus a spurious
  `pdf_n26_provider: failed to parse PDF` ERROR log line before the friendly
  `auto-detection failed` message. Repro: `aeat app ledger import ./statement.csv
  --provider auto --dry-run` with no such file. Source: quickstart + import. **confirmed**.

## Confirmed UX / message issues (APP)

- **[MAJOR][APP] calculate's missing-binding remediation misleads** — calculate tells the
  user to pass `--binding KEY=VALUE` for every missing binding, but ledger-aggregation
  bindings reject `--binding` (`Los bindings de agregación derivados del bucket entran en
  conflicto...`). Only `previous_filing` bindings accept `--binding`. The error should
  distinguish ledger-sourced (add ledger rows) from previous_filing (pass `--binding`/file
  prior). Source: quickstart. **confirmed**.

- **[MAJOR][BOTH] profile addressed by display-name, not the positional token** — after
  `profile duplicate X Y --display-name "Ana copy"`, the profile is addressable only as
  `"Ana copy"`, so the doc's own next command `profile delete ana-copy --yes` fails with
  `Unknown profile: ana-copy`. Source: profile-setup. **reported** (high-confidence).

## Documentation gaps (DOC)

- **[BLOCKER→DOC] quickstart linear path breaks for a real first-timer** — step 2 import has
  no sample CSV/format; step 4 `overview agenda` errors on the minimal step-1 profile; step 6
  calculate needs ledger income + prior-filing bindings; steps 7–9 hit blocking
  `cross_period_dependency_unclean` (needs activity-start date / evidence). Source: quickstart. **confirmed**.

- **[MAJOR][DOC] no sample `statement.csv` / CSV format** on quickstart and import pages — the
  single thing a new importer most needs. `--provider auto` works with a real BBVA CSV
  (`Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda`). Source: quickstart + import. **confirmed**.

- **[MAJOR][DOC] English doc vs Spanish runtime messages** — profile-setup prints refusal text in
  English ```text``` blocks, but the app emits Spanish; an English-only reader can't match them.
  Pervasive (CLI help + notices are Spanish; output keys English). Source: profile-setup. **reported**.

- **[MINOR][DOC] master-key passphrase never documented** — no page warns that a passphrase is
  required; interactive users are prompted, scripted users hard-blocked
  (`AEAT_SECRET_PASSPHRASE is not set`). Source: quickstart + profile-setup. **confirmed**.

- **[MINOR][DOC] `duplicate`/`import` silently switch the active profile** — not stated. Source: profile-setup.
- **[MINOR][BOTH] `profile history` needs an active bucket session** even with an explicit name; doc
  orders `logout` before `history`, so a literal reader hits `No hay una sesión de bucket activa`. Source: profile-setup.

## Backend capability — POSITIVE confirmations

- Modelo 130 1T calculates correctly from real ledger income: casilla 07 = 2000.00 (20% of 10 000
  rendimiento), box 13 minoración 100.00, casilla 19 = 1900.00. **confirmed**.
- verify gate is robust + well-grounded: carries `legal_refs`/`source_refs`, blocks unevidenced
  cross-period dependencies and missing activity-start date, gives concrete remediation. **confirmed**.
- export/file correctly refuse a draft (non-verified) revision. **confirmed**.
- Full ledger surface (import auto-detect, add, list, view, classify, update, history, export,
  rule add/apply, preflight) works end-to-end with a realistic bank CSV. **confirmed**.
- profile create/show/validate/edit/rename/duplicate/export/import/logout all function; foral-CCAA
  refusal is legally grounded; unencrypted-export warning is appropriately blunt. **confirmed** (persona).
