---
tags:
  - '#audit'
  - '#ledger-input-localization'
date: '2026-06-12'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
  - "[[2026-06-10-ledger-input-localization-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ledger-input-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ledger-input-localization` audit: `Ledger input-localization C3 execution closure`

## Scope

Execution-closure audit for cluster C3 of the ledger localisation campaign: the
canonical CLI decimal/date parser, the `is_finite()` / Spanish-thousands refusal,
the `invoice_date` pass-through gating, and the localised refusal payloads. The
audit verifies the plan's stated work against `HEAD` of the shared
`chore/eliminate-shims` worktree, runs the plan's verification gates, and records
whether the child plan can be closed. Scope was held to C3 input-localisation;
sibling ledger-hardening work (C1 amount/direction help-text, the `emit_help_text`
boundary helper) carried as uncommitted peer WIP was inspected only to bound the
seam, never modified.

## Findings

The C3 implementation is already landed at `HEAD`; no new production code was
written by this pass. The findings below record the verified state.

### Completed input-localization plan items

- **P01 (shared validator consolidation)** — landed. The canonical
  `parse_decimal_amount(raw, *, label, signed=True)` and
  `parse_optional_decimal_amount(...)` live in `src/aeat/entrypoints/cli/_common.py`
  with the dot-decimal regex (`_DECIMAL_RE` non-negative, `_SIGNED_DECIMAL_RE`
  signed, two-digit fractional cap), an `InvalidOperation` guard, and an
  `is_finite()` defence-in-depth check, all routing the localised
  `cli.ledger.errors.invalid_decimal` refusal. Both are exported via `__all__`.
  The six previously-duplicated `_parse_decimal`/`_parse_required_decimal` copies
  were reconciled onto the peer-extracted `_ledger_support.py` home (peer refactor
  `f27a480c2`), where they now survive **only as zero-logic delegators** to the
  `_common.py` canonical pair. `_parse_iso_date` gates the `invoice_date`/`date`
  inputs in the business-invoice, evidence, inventory, lifecycle, and ratios CLI
  modules.
- **P02 (locale catalogue)** — landed and gate-clean. `cli.common.errors.invalid_iso_date`
  carries `%{label}` and `%{raw}` in all four locales; `cli.ledger.errors.invalid_decimal`
  carries the accepted-form hint ("dot decimal separator, no thousands grouping")
  in all four; `amount_help` and the three `invoice_date_help` keys carry a format
  example (`e.g. 1200.50` / `e.g. 2026-01-15`) in all four. Authored through the
  `aeat.locales` CLI per the locale-authority rule, not by hand-editing `.yml`.
- **P03 (real-behavior boundary tests)** — landed. `test_common_decimal_parser.py`,
  `test_common_date_parser.py`, and `test_localised_parser_errors.py` drive the real
  validators (no mocks/skips/xfail) across the accept/reject matrix and the
  four-locale payload assertions.

### Deviation from plan text (non-blocking)

The plan's Verification criterion "`rg _parse_decimal|_parse_required_decimal`
finds zero surviving definitions outside `_common.py`" is **literally unmet but
satisfied in intent**: two delegators remain in `_ledger_support.py`. They contain
no parsing logic — each is a one-line call into the `_common.py` canonical helper —
so there is a single authoritative implementation, which is what the criterion
exists to guarantee. The divergence is the documented reconciliation onto the
peer-landed `_ledger_support` home (commit `aab1b534e` reconciliation note), not a
re-duplication. No remediation required; the criterion wording predates the peer
extraction.

### Locale files / keys touched (at HEAD)

- Files: `src/aeat/locales/{en,es,ca,hu}.yml`.
- Keys: `cli.common.errors.invalid_iso_date`, `cli.ledger.errors.invalid_decimal`,
  `cli.ledger.add.amount_help`, `cli.app.ledger.payable_invoice.invoice_date_help`,
  `cli.app.ledger.collectible_invoice.invoice_date_help`,
  `cli.app.ledger.evidence.invoice_date_help`.

### Code / tests touched (at HEAD)

- Code (commit `aab1b534e`): `_common.py` (canonical helpers),
  `_ledger_support.py` (delegators + `_parse_amount_magnitude`),
  `_ledger_business_invoice_cli.py`, `_ledger_evidence_cli.py`,
  `_ledger_inventory_cli.py`, `_ledger_ratios_cli.py`, `_ledger_lifecycle_cli.py`.
- Tests (commit `aab1b534e`): `tests/test_common_decimal_parser.py`,
  `tests/test_common_date_parser.py`, `tests/test_localised_parser_errors.py`.

### Tests / checks run by this closure pass

- `pytest` over the three C3 boundary test files — **51 passed**, no skip/xfail.
- `python -m aeat.locales scaffold --check` — **ok** for all four locales (zero drift).
- `python -m aeat.locales audit` — **ok** for all four locales (parity + honesty clean).
- `rg` sweep confirming the only non-delegating `parse_decimal_amount` definition
  is in `_common.py`.

### Dependencies on sibling clusters

- **C1 (`ledger-amount-direction`)** — **landed** (commit `3695a1b93`; rule
  `ledger-amount-is-absolute-direction-is-authority` active). The plan's sequencing
  note (use the signed variant for `--amount` until C1, then tighten to non-negative)
  is resolved: the non-negative `_DECIMAL_RE` is the canonical magnitude variant, and
  `_parse_amount_magnitude` (already committed in `_ledger_support.py`) enforces the
  non-negative magnitude with a localised `negative_amount` refusal. The remaining
  wiring of `ledger_update`'s `--amount` onto `_parse_amount_magnitude` is carried as
  uncommitted **peer C1 WIP** in `_ledger.py` (sibling hardening scope) — intentionally
  left to the C1 campaign, not touched here.
- **filter-period (`ledger-filter-period`)** — **no dependency**. C3 governs only
  per-field amount/`invoice_date` parsing; period-window selection is the separate
  `Period.contains()` authority (rule `period-filter-single-boundary-authority`).
  The shared `_parse_iso_date` gate is parsing infrastructure, not a period boundary,
  so the two clusters do not couple.

## Recommendations

- **Plan closure:** this child plan **can be closed**. All three phases are
  implemented at `HEAD`, every Verification gate is green (modulo the documented,
  intent-satisfying delegator deviation), and both sibling dependencies are resolved
  or correctly delegated. Per `plan-closure-requires-exec-records`, mark the P01–P03
  steps `[x]` only alongside a matching exec record (or a one-line carry-forward note
  citing commit `aab1b534e`); do not check steps on code inspection alone.
- **Optional tidy (defer):** when the C1 peer WIP in `_ledger.py` lands and the
  non-negative magnitude convention is final across every `--amount` call site, the
  two `_ledger_support.py` delegators can be inlined and the plan's literal
  "zero-definitions-outside-`_common.py`" criterion met exactly. Low value; not a gate.
- **Scope hygiene:** leave the uncommitted peer locale/`_common.py`/`_ledger.py`
  changes untouched — they belong to the C1 and help-text campaigns.

## Codification candidates

None. The single-canonical-parser and locale-CLI-authority lessons are already
codified (`aeat-locales-cli`, `aeat-architecture-boundaries` instructive-refusal,
`ledger-amount-is-absolute-direction-is-authority`). This execution surfaced no new
cross-session, constraint-shaped, project-bound lesson — an empty section here is the
expected, positive outcome.
