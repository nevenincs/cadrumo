---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:9234b3543ee6141a03bf746ab901daee3f579644e4412efaac3c6665bb768e47'
step_id: 'S449'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give the reconciliation direction column a header key that is not also a namespace, and gate the shape. The code declared tui.ledger.reconciliation.direction as a leaf and as the parent of its two enum values, which a mapping cannot satisfy, so the catalogue kept the namespace and the column header had nothing to resolve to every time the table drew. Move the enum values to a sibling namespace in the house style, author the header, and add a check for a declared key that is also a prefix of another.

## Scope

- `src/cadrumo/locales/*/common.yml`
- `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`
- `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `dev/locales/tests/test_no_key_shadows_a_namespace.py`

## Changes

Locale parity missing keys: 1 -> 0. The last one was not a scanner artefact like
the four before it. It was a live rendering bug the gate had been reporting
correctly the whole time.

The code declared `tui.ledger.reconciliation.direction` AND
`tui.ledger.reconciliation.direction.invoice_only`. A catalogue is a mapping, so
that key is either a string or the namespace holding the other; it cannot be
both. The catalogue resolved it the only way it could, keeping the namespace,
which left `reconciliation.py` asking for a column header that has no value --
every time the inconsistencies table draws.

That is why this one earns its own gate rather than a translation. Authoring a
value for the shorter key is impossible, not merely undone, and no gate that
compares key sets can see the difference: it reports one missing key among
hundreds, indistinguishable from a key someone forgot to translate.

The enum values moved to `direction_state.*`, matching how this catalogue
already names enumerations (`tui.aeat_sync.source_state.*`,
`tui.declarations.work_state.*`), so the header keeps the natural name. The
`move` verb carried all 8 leaves with nothing overwritten, and the header was
authored in four locales.

Teeth: reintroducing the shadowing in the declared key list fails the new gate,
naming `tui.ledger.reconciliation.direction` exactly. Restored by copy;
86 passed across the new gate, the scanner module and the whole Ledger TUI
suite.

## Notes

PARITY'S MISSING SIDE IS NOW EMPTY, from 228 when the loop was written and 189
when it was first measured live. Four causes in the end, and only one was a
missing translation: 156 help leaves the label writes never created, 7 keys a
module rename left behind, 24 identifiers the scanner claimed from a mapping's
lookup tokens, 4 command keys it claimed from a guard table's prose column, and
this one impossible key.

454 extras remain and are untouched. They are a different problem -- keys the
catalogue holds that no scanner site claims -- and pruning them with scaffold
would delete enum-driven keys the runtime builds by concatenation. That needs
the dynamic namespaces declared, which is a decision about which prefixes are
legitimately dynamic rather than a mechanical fix.
