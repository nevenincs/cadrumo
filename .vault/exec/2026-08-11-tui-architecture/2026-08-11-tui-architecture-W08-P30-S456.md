---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:29f9008476b9e247bffdc142e57cce8d8b8307140a9b155e33ee99028679ba9d'
step_id: 'S456'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Read the dynamic namespace a screen declares by selecting a prefix from a table, and register the bounded spaces rather than tolerating them, since the workspace helpers append an enum member value to a prefix chosen by class name so the f-string head is an interpolation and no namespace was declared at all

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/_fstring_registry.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 293 -> 188. Missing stays 2, and those two are the blocked
`direction` collision recorded in S455 -- nothing else is missing.

BLIND SPOT 7. The namespace rule required the f-string's HEAD to be the dotted
literal. A workspace that renders every public enum through one helper does not
write the prefix at the call site:

    _LABEL_PREFIXES = {"AeatSyncCensusStatus": "tui.aeat_sync.census_status", ...}
    prefix = _LABEL_PREFIXES.get(type(value).__name__)
    return aeat_sync_copy(f"{prefix}.{value.value}")

The head is an interpolation, so the module declared NO namespace and every key
the helper builds read as an orphan. `_interpolated_head_prefixes` reads the
shape by requiring the segment after the interpolation to begin with the dot --
that is what proves the name is used AS a prefix and keeps the rule off any
f-string that merely starts with a variable.

`"tui"` joins `_DYNAMIC_TRANSLATION_ROOTS`. The allowlist's stated criterion is
a tail "fully enumerable from the domain model", which an enum member value
meets verbatim. It is not a blanket grant: 26 markers result, every one a
concrete prefix written down in source (`census_status`, `work_state`,
`calendar.legal`, ...), 15 from the new rule and 11 from the literal-head rule
that was already written and only withheld by the root check.

REGISTERED RATHER THAN TOLERATED. The coverage gate demands each marker be a
bounded FStringKeyRegistration or a reasoned open-ended entry, and that is the
better half of this change: 73 AEAT Sync keys and 50 declarations keys now
expand concretely, so a new enum member arrives as a missing catalogue entry
instead of vanishing under a wildcard. Exactness COST 17 extras -- 188 against
the 171 a wildcard would have shown -- because keys shipped under a registered
namespace that no enum member produces are now reported instead of concealed.
That is the honest number and the reason to register.

`tui.home.reason` is the one genuine open-ended entry. The reason code travels
on a projected item rather than an importable enum, and the call site already
renders the key, compares the result against it, and falls back to the generic
line, so an unregistered code degrades to honest copy rather than a leaked
identifier.

Teeth: two defects, each restored by copy. Dropping the dot requirement admits
`f"{greeting} and welcome"` as a namespace and fails the gate; removing the
`"tui"` root withholds the marker and fails it. All 15 scanner gates pass.

## Notes

TARGET 2 REMAINS OPEN at 188 extras, and its missing side is still BLOCKED on
the `tui.ledger.reconciliation.direction` ownership decision recorded in S455.

Residue: 30 full-literal, 60 tail-only, 98 no-trace. The next full-literal shape
is a row table reaching the translator through a PARAMETER and a subscript index
(`_COLUMNS` -> `_fit_columns` -> `column[1]` -> `aeat_sync_copy`), which needs
interprocedural index tracking rather than another one-line widening.

Unchanged and not from this step: `test_committed_catalogues_*` (three) still
fail on em dashes and on the same `direction` collision, from the concurrent
TUI/sync commits. The suite run for this step reports exactly the four failures
that preceded it -- no new breakage.
