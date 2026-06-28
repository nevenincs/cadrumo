---
tags:
  - '#adr'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-04-20-classification-harmonization-adr]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - '[[2026-06-04-cross-domain-continuity-research]]'
---


# `cross-domain-continuity` adr: `ledger-classification-rule-engine` | (**status:** `accepted`)

## Problem Statement

`aeat app ledger classify` is a single-transaction verb. Operators with hundreds
of recurring transactions (subscription tools, regular vendor invoices, payroll
lines) must apply the same classification repeatedly. Two features address this:
S96 adds `--from-csv` for batch one-shot classification; S97 adds a persisted
rule set so that future imports are classified automatically without operator
intervention.

S97 requires decisions that the existing codebase does not pin: which pattern
engine to use, where rules are stored, how conflicts are resolved, and how
rule-applied decisions interact with manually-applied ones. This ADR fixes those
decisions so the implementation is unambiguous.

The `classified_by` field on `Transaction` already validates the shape
`rule:<rule-id>` (enforced by `_validate_classified_by_shape` in `_models.py`),
confirming the provenance slot was designed for this use case. The
`classification_confidence: Decimal | None` field on `Transaction` was introduced
by issue `#236` (now merged) and is the authority for expressing rule-engine
confidence. The classification-harmonization ADR (`2026-04-20`) authorized this
direction; the `#236` blocker it cited has since cleared.

## Considerations

### Pattern engine options

Three candidates were evaluated:

**(A) Regex only.** Single engine, well-understood semantics, Python standard
library (`re`), composable. Operators can express substring match as `.*keyword.*`,
prefix/suffix as `^keyword.*` / `.*keyword$`, and word-boundary as `\bkeyword\b`.
The existing `classified_by` convention uses `rule:<id>` identifiers, which implies
opaque rule IDs — a regex engine generates stable content-addressed IDs naturally
(SHA-256 of the serialized rule fields).

**(B) Substring + glob + regex.** Three engine kinds discriminated by a
`pattern_kind` enum. Lowers the barrier for operators who are not comfortable
with regex. Adds branching in the engine and three test surfaces instead of one.

**(C) Glob only.** Simple but cannot express alternation (`pattern1|pattern2`),
anchoring, or word boundaries without multiple rules.

### Storage location options

**(A) Profile-scoped `SecureBoundRepository[LedgerClassificationRule]`.** Follows
the established pattern for `IvaCompensationHistoryRepository` (namespace
`aeat.calculations.iva_compensation.history`, sensitivity `AUDIT`). Rules are
part of the profile's tax-accounting intent; losing them on profile deletion is
expected. Encrypted at rest, consistent with the secure-persistence ADR.

**(B) Flat JSON embedded in the `UserProfileFact` record.** No additional
repository class, but rules live in the profile record blob, making them
opaque to the secure-object storage query layer and harder to paginate.

**(C) Shared global file outside the profile.** Breaks the per-profile isolation
model; rules from one taxpayer profile could bleed into another's automation.

### Conflict policy options

**(A) Priority integer, lower value wins; ties broken by `created_at` ascending
(earlier rule wins).** Deterministic, operator-controllable, simple to reason
about.

**(B) Last-write wins.** Simple but non-deterministic when two rules match;
cannot be reasoned about without inspecting insertion order.

**(C) First-match wins, no priority.** Requires operators to manage insertion
order as a proxy for priority, which is opaque in storage.

### `rule apply` scope options

**(A) ACTIVE + `NOT_YET_PROCESSED` only.** Respects the pipeline's intent: a
rule engine should not silently re-classify rows that an operator has already
touched. The `NOT_YET_PROCESSED` lifecycle state is specifically designed as the
rule-engine entry gate.

**(B) All ACTIVE regardless of classification state.** Would silently overwrite
manual classifications; violates the provenance contract.

### Reaffirm interaction

**(A) Rule apply skips any row where `classified_by == "manual"` unless
`--reaffirm` is passed.** Matches the existing `reaffirm` flag semantics on
`ledger classify --id`. The operator's explicit manual classification is the
authority; a rule pass-over cannot revoke it without explicit consent.

**(B) Rule apply always overwrites.** Eliminates operator trust in manual decisions.

## Constraints

- Must use the existing `classified_by` field shape `rule:<rule-id>` — no new
  provenance fields on `Transaction`.
- `classification_confidence` for rule-applied rows must be `None` unless the
  rule declares an explicit confidence; rule-engine decisions are deterministic
  (pattern either matches or not), so confidence is inapplicable in the typical
  case.
- `LedgerClassificationRule` is a domain entity — it belongs in
  `src/aeat/domain/transactions/` and must not carry application or adapter
  imports.
- The rule repository belongs in `src/aeat/application/ledger/` — application
  layer, not domain.
- The CLI sub-app `rule` is a sub-command group under `aeat app ledger`, not a
  new root command (preserving the two-root `config` / `app` constraint from
  `aeat-architecture-boundaries`).
- No shims, no compatibility aliases, no deprecation paths per project policy.

## Implementation

### D1 — Pattern engine: regex only

Option A is chosen. A single `re`-module regex engine with case-insensitive
matching by default (`re.IGNORECASE`). Operators who want literal substring
matching write `.*keyword.*`; this is documented in the CLI help text. Glob and
substring alternatives are deferred; if operator demand materializes they can be
added as a `pattern_kind` discriminator in a future ADR without breaking stored
rules (regex rules round-trip cleanly if a `pattern_kind` field with default
`"regex"` is added later).

### D2 — Domain model: `LedgerClassificationRule`

A frozen pydantic model in `src/aeat/domain/transactions/_classification_rule.py`:

```
rule_id: str          # SHA-256 hex of (description_pattern + classification + category_id); 64 chars
description_pattern: str   # regex string; applied case-insensitively against transaction.raw.description
classification: BusinessClassification   # target classification
category_id: str | None    # optional spending category to apply alongside classification
priority: int              # lower value = higher priority; default 100
created_at: datetime
actor: str                 # operator or agent identifier
```

`rule_id` is content-addressed: `sha256(f"{description_pattern}|{classification}|{category_id or ''}")`.
This makes rule creation idempotent — adding the same rule twice produces the
same ID and the repository's `save` overwrites the prior entry.

### D3 — Storage: profile-scoped `SecureBoundRepository`

Option A is chosen. `LedgerClassificationRuleRepository` in
`src/aeat/application/ledger/_rule_repository.py`:

```
namespace  = "aeat.ledger.classification.rules"
sensitivity = SensitivityClass.AUDIT
payload_type = LedgerClassificationRule
```

`extract_identifier` returns `rule_id`. Rules are loaded via `iter_records()`
sorted by `(priority, created_at)` ascending for deterministic ordering.

### D4 — Actions: `add_classification_rule` + `apply_classification_rules`

Both actions in `src/aeat/application/ledger/_actions.py`.

`add_classification_rule(bucket_id, pattern, classification, *, category_id, priority, actor, rule_repository)`:
- Validates the regex compiles (`re.compile(pattern)` — raises `ValueError` on
  invalid syntax before persistence).
- Computes `rule_id`, constructs `LedgerClassificationRule`, saves to repository.
- Returns the saved rule.

`apply_classification_rules(bucket_id, *, transaction_repository, rule_repository, reaffirm, actor)`:
- Loads rules sorted by `(priority, created_at)` ascending.
- Iterates ACTIVE transactions where `business_classification is NOT_YET_PROCESSED`.
  If `reaffirm=True`, also includes ACTIVE transactions where
  `classified_by == "manual"`.
- For each transaction, evaluates rules in priority order; the first match applies.
  Match is `re.search(pattern, transaction.raw.description, re.IGNORECASE)`.
- On match: calls `update_manual_transaction_fields` with
  `classified_by=f"rule:{rule_id}"`, `business_classification=rule.classification`,
  `category_id=rule.category_id`, `source_command="aeat app ledger rule apply"`.
- Returns `ApplyRulesResult` with `matched`, `skipped`, `no_match` counts.

### D5 — Conflict policy: priority integer, ties by `created_at` ascending

Option A is chosen. `priority` defaults to 100. Operators who need a rule to
fire before all others use a lower number (e.g., 1). Among same-priority rules
the earliest-created rule wins. This is explicit, operator-controlled, and
reproducible.

### D6 — Rule apply scope: ACTIVE NOT_YET_PROCESSED only (unless `--reaffirm`)

Option A is chosen. The `reaffirm` flag on `apply_classification_rules` mirrors
the existing `--reaffirm` flag on `ledger classify --id`. Its semantics: passing
`--reaffirm` signals explicit operator consent to overwrite prior decisions. A
rule pass-over without `--reaffirm` never touches a row that a human has touched.

### D7 — CLI surface: `aeat app ledger rule add` + `aeat app ledger rule apply`

Two commands under a new `rule` sub-app of `ledger`:

- `aeat app ledger rule add --description-pattern "..." --classification BUSINESS
  [--category-id <id>] [--priority <n>] [--actor <name>]`
- `aeat app ledger rule apply [--reaffirm] [--dry-run] [--actor <name>]`
- `aeat app ledger rule list` — list stored rules ordered by priority

`rule list` is added in the same step (S97) so the operator can inspect what is
stored before running `rule apply`.

### D8 — `apply_classification_rules` result model

`ApplyRulesResult(BaseModel)` in `src/aeat/application/ledger/_models.py`:

```
rules_evaluated: int
transactions_scanned: int
matched: int
skipped_already_classified: int
no_match: int
applied: tuple[ApplyRulesAppliedRow, ...]
```

where `ApplyRulesAppliedRow` carries `transaction_id`, `matched_rule_id`, and
`classification`.

## Rationale

Regex-only (D1) avoids feature-flag branching in the engine and a three-way test
matrix while still expressing all operator use cases. Content-addressed `rule_id`
(D2) makes creation idempotent without explicit upsert logic. Profile-scoped
`SecureBoundRepository` (D3) matches every other audit-sensitivity artifact in the
application and follows the established pattern without exception. Priority-ordered
conflict resolution (D5) is the only option that gives operators explicit,
documented control without relying on opaque insertion order. The `reaffirm` gate
(D6) is consistent with the existing flag on `ledger classify`; operators who
understand the concept already know how it works.

## Consequences

- Positive: operators can automate classification of recurring transactions
  without scripting; the rule engine fires at `ledger rule apply` or can be
  wired into the import pipeline in a follow-on step.
- Positive: `classified_by = "rule:<id>"` provenance is already validated by
  `Transaction`; no schema migration required.
- Positive: `LedgerClassificationRuleRepository` follows the same
  `SecureBoundRepository` pattern as `IvaCompensationHistoryRepository`; no new
  storage abstraction is introduced.
- Negative: operators must write regexes for complex patterns; literal-substring
  and glob aliases are not available in this first version.
- Negative: `apply_classification_rules` is a full-scan over ACTIVE transactions;
  for large catalogues (thousands of rows) this is acceptable since it is an
  operator-triggered batch action, not a hot path.
- Future: if glob or substring pattern kinds are demanded, a `pattern_kind`
  discriminator field with default `"regex"` can be added to
  `LedgerClassificationRule` without breaking stored rules (the existing rules
  remain valid regex rules).
