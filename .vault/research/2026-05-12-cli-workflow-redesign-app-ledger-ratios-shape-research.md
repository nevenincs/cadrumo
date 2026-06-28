---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `app ledger ratios shape`

## Topic

Design `aeat app ledger ratios` for proportional deduction usage ratios.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §4.2, the
ledger-transaction-management ADR, the 2026-04-21 usage-ratios ADR,
`domain/usage_ratios`, the old financial profile ratio CLI, root CLI mount
state, and the IVA prorrata functional gap.

## Rewrite Scope

This research supports a child ADR that locks the `aeat app ledger ratios`
grammar, retires old financial-profile ratio UX, normalizes verb-noun grammar,
and explicitly separates proportional deduction usage ratios from IVA prorrata
under LIVA arts. 101-103.

## Findings

Apex §4.2 places `usage_ratios` under `app ledger ratios`, with the verb set
still unresolved. The financial root is retired.

The ledger transaction ADR requires ledger mutations to be bucket-scoped and
evented. Mixed-use rows need `business_pct` or equivalent proportionality
context before modelo calculation consumes them.

The usage-ratios ADR chose category-keyed persisted ratios, CLI-only family
aliases, bounds `[0,1]`, pure `resolve_user_ratio`, and legacy `set-ratio` /
`unset-ratio` commands.

The current domain package is `src/aeat/domain/usage_ratios`. Eligible
categories are derived from `CATEGORY_PROFILES_2025` where proportionality kind
is `USAGE_RATIO_HOME_AREA` or `USAGE_RATIO_PERSONAL`. Persistence writes
encrypted secure object namespace `aeat.domain.usage_ratios`, key `profile`,
version `1`; path is ignored.

The current CLI is stale and unmounted under `aeat financial profile`, with
nested `ratios list` plus top-level `set-ratio` and `unset-ratio`. Current
`app ledger` has no `ratios` group.

The backend-boundary reference marks usage-ratio CLI behavior as an application
API gap: alias resolution, suggestions, parse diagnostics, and atomic profile
load/save need an application service.

Apex separates prorrata: usage ratios are proportional deduction, not legal IVA
prorrata. There is currently zero prorrata code. Modelo 303 needs prorrata
later; Modelo 130 needs proportional deduction via ledger-to-renta aggregation.

## Proposed Grammar

Canonical surface:

```text
aeat app ledger ratios list [--format json|text]
aeat app ledger ratios set KEY VALUE [--format json|text]
aeat app ledger ratios unset KEY [--format json|text]
```

Optional read helpers if needed later:

```text
aeat app ledger ratios show KEY [--format json|text]
aeat app ledger ratios eligible [--format json|text]
```

Grammar rules:

- Use verb-noun normalization under noun group `ratios`.
- Retire `set-ratio` and `unset-ratio`; do not preserve aliases.
- Preserve `KEY` semantics from the implemented domain: concrete
  `SpendingCategory.value` or CLI-only family alias.
- Keep aliases CLI/application-layer only; do not persist alias names.
- Reserve `prorrata` wording. Help/output says "usage ratios",
  "proportional deduction", or "business/personal split coefficient", not
  "IVA prorrata".

## Output And Event Contract

`ratios list` text output renders category, proportionality kind, user ratio,
statutory/default ratio, and source.

`ratios list` JSON output includes `bucket_id` and a `ratios` array.

`ratios set KEY VALUE` JSON output includes `bucket_id`, operation
`ledger.ratios.set`, key, ratio, updated categories, and `event_id`.

`ratios unset KEY` is idempotent for missing values, but still reports whether
any category changed.

Persisted mutation bucket events:

- `ledger.ratios.set`
- `ledger.ratios.unset`

Minimum event payload: schema version, bucket id, actor/source command, raw
key, resolved category ids, previous ratio presence/value per category if
non-secret, new ratio for set, outcome, timestamp, and target object ref
`aeat.domain.usage_ratios/profile`.

## Rejected Shapes

- `aeat financial profile ...`
- `aeat app ledger profile ratios ...`
- `aeat app ledger set-ratio ...`
- `aeat app ledger ratios set-ratio`
- `aeat app modelo ratios ...`
- `aeat app ledger prorrata ...`

IVA prorrata under LIVA arts. 101-103 is a separate Modelo 303/390 gap.

## Clean-Refactor Rule

No compatibility shims. Remove old `financial profile` command
registration/import paths from public CLI discovery when `app ledger ratios`
lands. Any data migration is backend/internal only.

Tests should prove the old financial ratio surface is absent, the new
app-ledger surface works, and set/unset writes both the secure profile state
and the required bucket event.
