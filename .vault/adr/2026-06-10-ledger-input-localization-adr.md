---
tags:
  - '#adr'
  - '#ledger-input-localization'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - "[[2026-06-10-ledger-input-localization-research]]"
---



# `ledger-input-localization` adr: `Enforce canonical amount and date input with localised actionable rejection` | (**status:** `accepted`)

## Problem Statement

The manual ledger CLI entry boundary silently misparses locale-variant monetary
input and admits ill-formed dates. As inventoried in the companion research, the
amount parser `_parse_decimal` does a bare `Decimal(raw.strip())` with no format
validation: a Spanish-convention operator who types `1.000` meaning one thousand
gets `Decimal('1.000')` = `1.0`, a one-euro transaction, with no error
(research F1); `NaN`, `Infinity`, and scientific `1e3` are all accepted because
there is no `is_finite()` guard (F2); and the `invoice_date` flag is passed raw
to the service, so `15/01/2026` persists as a non-ISO ten-character string (F5).
This violates `aeat-architecture-boundaries` — the CLI gate is the operator's
first instructive surface and must never be a silent black hole. The canonical
enforcement already exists for one path (`_DECIMAL_RE` on `--set`, F3) but is
absent from the six duplicated `_parse_decimal` sites (F4). This ADR settles how
the manual entry boundary must validate, refuse, and localise. It is the
input-parsing cluster (C3) of the wider ledger localisation campaign and
coordinates with the absolute-amount convention (C1) and the invoice command
(C4).

## Considerations

The operator-stated decision is locked: **enforce** canonical input formats and
**reject** ambiguous or locale-variant input with explicit, localised,
actionable error messages. The boundary must NOT grow locale-aware
multi-separator parsing — an operator who means one thousand types `1000`, not
`1.000` or `1,000`. This is deliberate: a parser that tries to *guess* whether
`1.000` is one thousand or one-point-zero is the silent-corruption surface the
research found; the only safe boundary is one canonical form, enforced, with a
refusal that teaches the form. `no-legacy-compatibility` applies — there is no
released data and no caller to keep compatible, so no tolerance path for the old
unguarded shapes is carried.

The canonical pattern is already in the codebase twice over: `_DECIMAL_RE`
(`r"^-?\d+(\.\d+)?$"`) on the declaration-edit path, and the `is_finite()` guard
plus `FinancialValidationError` in the financial CSV adapter. The decision is to
unify the manual boundary onto that same shape, not to invent a new one. For
dates, `date.fromisoformat()` (already used by the safe `_parse_iso_date`
helper, and mirrored by the core `parse_iso8601_date`) is the canonical gate; it
rejects every non-ISO ordering by construction and the DD/MM-vs-MM/DD ambiguity
never arises.

## Constraints

This decision depends on the C1 `ledger-amount-direction` feature, whose ADR is
authored concurrently and establishes a non-negative absolute-amount +
direction-authority convention. The amount regex therefore has two variants and
the dependency must be sequenced: a *signed* field uses `^-?\d+(\.\d+)?$`; a
ledger amount that C1 makes a non-negative magnitude uses `^\d+(\.\d+)?$` (no
leading sign), so a typed `-` is itself a refusal. The shared helper must expose
both variants and each call site selects per field. If C1 lands first, the
ledger `--amount` site adopts the non-negative form immediately; if this lands
first, the ledger amount site uses the signed form until C1 retracts the leading
sign. This coordination is the only cross-feature blocker; both the locale CLI
and `date.fromisoformat` are stable, in-tree, and carry no frontier risk.

The locale work is constrained to the `aeat.locales` CLI surface
(`aeat-locales-cli`): the four catalogues must stay in key parity and the
honesty ratchet must not be bypassed by hand edits.

## Implementation

The decision has four parts, layered boundary-first.

**Canonical amount form.** Adopt the existing `_DECIMAL_RE` shape as the single
accepted amount grammar: dot decimal separator, no thousands grouping, no
scientific notation, no `NaN`/`Infinity`. The parser validates the raw string
against the regex *before* constructing `Decimal`, then asserts `is_finite()` as
defence-in-depth (mirroring the financial adapter). `1.000`, `1.234,56`, `1e3`,
`NaN`, and `Infinity` all refuse. The helper exposes a signed variant
(`^-?\d+(\.\d+)?$`) and a non-negative variant (`^\d+(\.\d+)?$`); ledger amount
fields use the non-negative variant once C1 lands (see Constraints), genuinely
signed fields use the signed variant.

**Single shared helper.** Consolidate the six duplicated `_parse_decimal` /
`_parse_required_decimal` copies into one owning helper in
`src/aeat/entrypoints/cli/_common.py` (which already owns `_parse_iso_date`),
enforcing the regex + finite guard exactly once. The six modules import the
shared helper rather than re-deriving it; per `service-imports-via-top-level-reexports`
and the architecture-boundary rules, the canonical helper has one home and is
consumed, not copied.

**ISO date everywhere.** Route every date-typed CLI input through the shared ISO
gate, including `invoice_date` on the business-invoice and evidence commands,
which today bypass it (research F5). After the change, `15/01/2026` refuses at
the CLI boundary for both `--date` and `--invoice-date`, before the value
reaches the service or the domain length check.

**Localised, actionable refusals (via the `aeat.locales` CLI only).** Three
catalogue changes, applied with `python -m aeat.locales set ...` to keep
four-locale parity:

- `cli.common.errors.invalid_iso_date` — add the `%{label}` and `%{raw}`
  interpolations to the EN, CA, and HU strings so they match the ES content
  (which already carries them); every locale must echo which field and what the
  operator typed.
- `cli.ledger.errors.invalid_decimal` — append an expected-format hint to all
  four locales (e.g. EN "use a dot decimal separator with no thousands grouping,
  e.g. 1234.56"); the message must name the accepted form, not just declare the
  input invalid.
- `cli.ledger.add.amount_help` and the invoice-date help strings
  (`cli.app.ledger.payable_invoice.invoice_date_help`,
  `cli.app.ledger.collectible_invoice.invoice_date_help`,
  `cli.app.ledger.evidence.invoice_date_help`) — add a format example, modelled
  on the existing `correct_amount_help` ("decimal, e.g. 1200.50"), so the
  accepted shape is visible before any refusal.

**Boundary ownership.** Validation happens at the CLI boundary in the shared
`_common.py` helpers, before pydantic and before the service call. The validated
`Decimal` / `date` is the exact value persisted; no re-coercion sits between the
boundary and the existing single-writer encrypted ledger store, so the value
that lands in the per-profile `SecureObjectRepository` is the one the boundary
admitted (research F9).

**Verification (real-behavior, non-tautological).** Boundary tests assert the
parser *refuses* `1.000`, `1.234,56`, `NaN`, `Infinity`, `-Infinity`, and `1e3`;
*accepts* `1000`, `1234.56`, and `0`; refuses `15/01/2026`, `01-15-2026`, and
`2026/01/15` for both the `--date` and `--invoice-date` inputs; and that the
localised error payload carries the label, the raw value, and the
expected-format hint in each of the four locales. No mocks, no skips, no
tautology — these exercise the real CLI parse path and the real catalogue.

## Rationale

The locked decision (enforce one canonical form, refuse variants with an
instructive message) is the only design that closes the silent-corruption
surface. A locale-aware multi-separator parser would have to *guess* the
operator's intent for `1.000`, and any guess is wrong half the time — the
research F1 defect is precisely that the current bare parser already guesses
(dot = decimal) and guesses wrong for the Spanish operator. Enforcement plus an
instructive refusal moves the cost from a silent wrong filing to a loud,
correctable parse error at the input site, satisfying
`aeat-architecture-boundaries`. Reusing the in-tree `_DECIMAL_RE`,
`is_finite()`, and `date.fromisoformat()` patterns (research F3, F2, F5) means
the boundary converges on shapes the codebase already trusts rather than
introducing a novel grammar. Consolidating the six duplicates (F4) is a
precondition, not a nicety: the defect is un-closable while five copies remain
unguarded.

## Consequences

Gains: the silent thousands-separator misparse and the non-finite admission are
eliminated at the boundary a human drives; `invoice_date` can no longer persist
a non-ISO string; the error surface becomes instructive and locale-complete; and
six divergent parsers collapse to one owned helper, removing the drift surface.

Honest difficulties: this is a behavioural break for any operator who relied on
the old tolerance — `1.000` now refuses where it previously (wrongly) became
`1.0`. Because the project is unreleased with no stored data, that break is
acceptable and `no-legacy-compatibility` forbids a tolerance path. The C1
sequencing is a real coupling: the ledger amount regex variant is not final
until the absolute-amount convention lands, so the executing plan must either
sequence after C1 or ship the signed variant with a follow-up to tighten to
non-negative. The locale changes touch four catalogues and must go through the
`aeat.locales` CLI; a hand edit would trip the parity and honesty gates.

Pathways opened: a single owned amount/date validation surface that C4 (the
invoice command) and any future manual entry command consume directly, ending
the copy-paste-parser pattern.

## Codification candidates

- **Rule slug:** `cli-manual-input-canonical-formats`.
  **Rule:** Every manual CLI entry-boundary numeric input must validate against
  the canonical decimal grammar (dot separator, no thousands grouping, no
  scientific notation) with an `is_finite()` guard, and every date input must
  pass `date.fromisoformat()` ISO validation, through a single shared
  `_common.py` helper — never a per-command bare `Decimal(...)` or raw-string
  pass-through; refusals must name the field, echo the raw value, and state the
  accepted format in all four locales.
