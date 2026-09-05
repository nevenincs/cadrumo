---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:4952841651540c982da167f718c43c4fae1c2e216bf6273ff9bb0e9b3731125e'
step_id: 'S442'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Restore the casilla help keys the label writes dropped, and establish why the rest of the locale parity drift must not be scaffolded away. Every casilla in the catalogue carries a help leaf beside its label; the labels written across this campaign carried none, so 156 keys the codebase references went missing. The remaining drift is not the same kind of problem: the 463 keys the scanner calls extra include enum-driven ones the runtime builds dynamically, and the scaffold verb prunes exactly that set, so running it would delete live keys.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`

## Changes

Locale parity missing keys: 189 -> 33. The 463 extras are untouched, and this
records why touching them with the obvious tool would break the product.

A REGRESSION OF MINE. Every casilla in the catalogue carries a `help` leaf
beside its `label` -- 3173 of 3329 did, and the 156 exceptions were exactly the
casillas this campaign labelled. `set-batch` writes the key it is given, so
writing only `.label` left no `.help` sibling, and the scanner counts a
referenced key with no leaf as missing. The gate that caught it is parity, not
any of the label gates, because a missing help leaf is invisible to all of
them: the runtime treats help as optional and resolves it to None.

Fixed by writing the 156 help leaves as null in all four locales, which is what
every other casilla carries. Parity's missing count falls by exactly 156.

THE REMAINING DRIFT IS NOT THE SAME KIND OF PROBLEM, and the tool that looks
right is dangerous here. `dev.locales scaffold` reconciles both halves -- it
adds missing keys AND prunes extra ones -- and its prune keeps only keys covered
by a declared dynamic namespace. The 463 extras are by definition not covered,
so scaffold would delete all of them.

Some of those are live. `tui.destination.home`, `tui.home.reason.*`,
`tui.declarations.work_state.*` are enum-value keys the runtime builds by
concatenation, and the static scanner sees no literal call site for them. The
production declaration for the destination keys is a `type X = Literal[...]`
alias in entrypoints/tui/navigation.py, which the scanner cannot see at all: it
walks `ast.Assign` nodes, and a PEP 695 type alias is an `ast.TypeAlias`. So
the keys are real, the code that uses them is real, and both are invisible to
the scanner that would authorise their deletion.

## Notes

STILL OPEN, and deliberately not guessed at:

33 missing keys remain. Seven are adapters.outbound.storage._factory.errors.*,
which appear in BOTH the missing and the extra lists -- the signature of a
module rename where the locale subtree kept the old path. The rest are
operator.* action ids and workbench.* route identities; whether those are locale
keys at all or scanner false positives is the question, and it decides whether
the fix is to add entries or to stop the scanner claiming them.

463 extras remain. The right fix is to make the scanner see the declarations it
is missing -- the TypeAlias shape at minimum -- or to declare the dynamic
namespaces, NOT to prune. That is the same machinery target 4 names
(flows.progress.required not collected by scan_source_tree), so the two share a
root and should be taken together.
