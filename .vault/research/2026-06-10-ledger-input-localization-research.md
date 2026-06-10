---
tags:
  - '#research'
  - '#ledger-input-localization'
date: '2026-06-10'
related: []
---



# `ledger-input-localization` research: `Ledger CLI amount and date input format parsing`

This research inventories how the manual ledger CLI entry boundary parses
operator-typed monetary amounts and dates, and where locale-variant or
ambiguous input is silently misparsed instead of refused. The scope is the
*manual entry* boundary only — the `aeat app ledger ...` and
`aeat app ledger invoice ...` commands where a human types `--amount`,
`--taxable-base`, `--invoice-date`, and similar values. The bank-statement CSV
import path is a separate adapter with its own (stronger) numeric guards and is
referenced only as the canonical pattern to mirror. The motivating concern is
that a Spanish-locale operator who types `1.000` meaning one thousand euros, or
`1.234,56` meaning one thousand two hundred thirty-four point five six, gets a
silently wrong number or an unhelpful refusal at a boundary that should be the
operator's first instructive surface.

## Findings

### F1 — CRITICAL: silent thousands-separator misparse on the amount boundary

The manual amount parser `_parse_decimal` (and its required-value wrapper
`_parse_required_decimal`) in `src/aeat/entrypoints/cli/_ledger.py:122` does a
bare `Decimal(raw.strip())` with no format validation:

```
return Decimal(raw.strip())
```

The consequence is locale-dependent silent corruption. A Spanish-convention
operator who types `1.000` to mean one thousand produces `Decimal('1.000')`,
which equals `1.0` — a one-euro transaction with no error raised. The mistake is
invisible: the value persists, the ledger balances against a wrong figure, and
no surface ever told the operator the input was interpreted differently from
what they meant. Conversely `1.234,56` (Spanish full grouping + decimal comma)
raises `InvalidOperation` and is rejected, but with an error that gives no hint
about the accepted format (see F5). The boundary is neither permissive in a
defined way nor instructive on refusal — it is silently wrong on one shape and
opaquely refusing on another.

### F2 — non-finite literals are accepted on the amount boundary

`Decimal("NaN")`, `Decimal("Infinity")`, and `Decimal("1e3")` all construct
successfully. Because `_parse_decimal` has no `is_finite()` guard and no regex,
the strings `NaN`, `Infinity`, `-Infinity`, and scientific notation `1e3` are
all accepted and flow into the ledger. `NaN` in particular poisons every
downstream comparison and aggregation. This is the same class of defect the
financial CSV adapter already defends against: `parse_amount_value` in
`src/aeat/adapters/inbound/financial/providers/_base.py:495` raises
`FinancialValidationError` on `not amount.is_finite()`, with an inline comment
calling it defence-in-depth against non-finite values entering the ledger. The
manual CLI boundary — the one a human drives directly — has no equivalent guard.

### F3 — the canonical enforcement pattern already exists, on a different path

The `--set KEY=VALUE` declaration-edit path already enforces a canonical decimal
shape: `src/aeat/application/review/_edit.py:51` defines
`_DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")` and rejects malformed decimals
before the constructor. This regex is exactly the canonical form the amount
boundary should adopt: dot decimal separator, no thousands grouping, no
scientific notation, no `NaN`/`Infinity`. The pattern is in the codebase; it is
simply not wired to the `--amount` / `--taxable-base` entry path. The two paths
have drifted: one enforces, six do not.

### F4 — `_parse_decimal` / `_parse_required_decimal` is duplicated six times

The identical unguarded helper pair is copy-pasted across six CLI modules:

- `src/aeat/entrypoints/cli/_ledger.py:122`
- `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py:50`
- `src/aeat/entrypoints/cli/_ledger_evidence_cli.py:258`
- `src/aeat/entrypoints/cli/_ledger_inventory_cli.py:39`
- `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py:66`
- `src/aeat/entrypoints/cli/_ledger_ratios_cli.py:34`

Every copy is the same bare `Decimal(raw.strip())`. A fix applied to one site
leaves the other five unguarded, so the defect cannot be closed without a
consolidation. There is no single owning helper; the shared CLI helper module
`src/aeat/entrypoints/cli/_common.py` is the natural home (it already owns the
date helper, see F6).

### F5 — date input: the ISO helper is safe, but `invoice_date` bypasses it

The shared date helper `_parse_iso_date` in
`src/aeat/entrypoints/cli/_common.py:319` delegates to `date.fromisoformat()`.
This is *safe by construction*: `fromisoformat` accepts only `YYYY-MM-DD`, so it
rejects `15/01/2026`, `01-15-2026`, and `2026/01/15`, and the DD/MM-vs-MM/DD
ambiguity can never arise — an ISO date has an unambiguous field order. The
`--date` flow that routes through this helper is sound.

The defect is that `invoice_date` does **not** route through it. On the business
invoice and evidence commands, `invoice_date` is a raw `str` Typer option passed
straight to the service:

- `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py:180, 281, 398, 503`
- `src/aeat/entrypoints/cli/_ledger_evidence_cli.py:98, 197`

The domain model does not validate the *format* — the invoice model normalises
dates through `_normalise_invoice_dates` in
`src/aeat/domain/invoices/_models.py:144` only for an `issued_at` field, and the
raw `invoice_date` string is accepted as-is subject only to a length bound.
Consequently `15/01/2026` (exactly ten characters) persists verbatim as a
non-ISO string. The operator gets no refusal and a downstream consumer that
expects ISO will misparse or fail later, far from the input site.

### F6 — shared ISO date infra exists at the core layer, unused by the CLI

`src/aeat/core/parsing/_dates.py` exposes `parse_iso8601_date` (public alias
`parse_date`, `fmt="iso8601"`), a no-I/O core-layer parser that raises
`ValueError` with an actionable `expected YYYY-MM-DD` message. The CLI does not
consume it; it has its own `_parse_iso_date`. Either is acceptable as the
canonical ISO gate — the point is that one ISO gate must front *every*
date-typed CLI input, including `invoice_date`, not just `--date`.

### F7 — locale catalogue defects (the error messages are not actionable)

Three localisation gaps weaken the refusal surface. All must be fixed through
the `aeat.locales` CLI (never by hand-editing the `.yml` files, per the
`aeat-locales-cli` rule):

- `cli.common.errors.invalid_iso_date` carries the `%{label}` and `%{raw}`
  interpolations only in Spanish (`es.yml:1942`). English (`en.yml:1808`),
  Catalan (`ca.yml:1915`), and Hungarian (`hu.yml:1866`) drop both — the
  operator is told "invalid date format" with no echo of *which* field or *what*
  they typed. The four locales are out of parity on this key's content.

- `cli.ledger.errors.invalid_decimal` echoes the label and raw value in all four
  locales (`en.yml:2453`, `es.yml:2629`, `ca.yml:2594`, `hu.yml:2558`) but
  states no expected format. The operator who typed `1.000` and got a number
  silently changed (F1), or who typed `1.234,56` and got a refusal (F5), is
  never told that the accepted form is a dot decimal separator with no grouping.

- The amount help strings lack a format example. `cli.ledger.add.amount_help`
  (`en.yml:2297` "Signed transaction amount in the bucket currency") gives no
  example, whereas the sibling `correct_amount_help` (`en.yml:1417`) models the
  right pattern: "Corrected carry-forward balance amount in EUR (decimal, e.g.
  1200.50)." The amount help and invoice-date help strings should carry an
  explicit example so the accepted shape is visible before the operator ever
  hits a refusal.

### F8 — applicable rules and prior audit coverage

- `aeat-architecture-boundaries`: the CLI gate is "the operator's first
  instructive surface"; a refusal must list the accepted set and "never make it
  a silent black hole." F1 (silent misparse) and F5 (silent non-ISO persist)
  both violate this directly; F7 (no expected-format hint) violates the
  instructive-refusal half.
- `aeat-locales-cli`: locale fixes go through the CLI, maintaining four-locale
  parity, not hand edits.
- `aeat-quality-gates` / `no-tautological-calculation-tests`: the fix's tests
  must be real-behavior boundary tests (parse rejects/accepts), not mocks, and
  not tautological.
- `no-legacy-compatibility`: this is the locked operator decision — enforce the
  canonical form and reject locale variants; do NOT add multi-separator
  locale-aware parsing at the manual entry boundary.
- The `2026-05-30-security-input-validation-swarm-audit` finding F3 covered the
  CSV-adapter NaN guard but did not reach this manual-CLI boundary; this research
  extends that line to the manual entry surface.

### F9 — secure-storage gate

Parsing happens *before* persistence, so the per-profile encrypted
bucket-scoped `SecureObjectRepository` invariant is not directly exercised by
this surface. The relevant assertion is downstream-of-parse: once the boundary
has validated and constructed a `Decimal` (or an ISO `date`), that value lands
in the encrypted store unchanged. The fix must not introduce any re-coercion
between the validated boundary value and persistence — the canonical `Decimal`
the regex admits is the exact value stored. No new plaintext or alternate write
path is created; the validators sit upstream of the existing single-writer
ledger persistence.

### F10 — cross-cluster coordination

- **C1 (`ledger-amount-direction`)**: a concurrent feature establishes an
  absolute-amount + direction-authority convention for ledger amounts (the
  amount becomes a non-negative magnitude with direction carried separately).
  The canonical amount regex must coordinate: for genuinely signed fields the
  form is `^-?\d+(\.\d+)?$`, but for a ledger amount that C1 makes a
  non-negative magnitude the form should drop the leading sign to `^\d+(\.\d+)?$`
  so a typed `-` is itself a refusal. The shared helper should therefore expose
  both a signed and a non-negative variant, and the call sites choose per field.
  This dependency must be sequenced with C1's landing.
- **C4 (invoice command)**: the `invoice` command's `invoice_date` and amount
  inputs must consume these same shared validators rather than re-deriving their
  own — F4's duplication is precisely the anti-pattern C4 must avoid repeating.
