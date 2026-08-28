---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:199685e93aa35fdd67ab6babccf50900d7f9671641327874c5ca6b66f89837b6'
related:
  - "[[2026-08-28-tui-architecture-m303-prorrata-percentage-dormancy-audit]]"
---

# `tui-architecture` audit: `No computed casilla is a silent dead end; export_refs is not the export signal`

## Scope

## Findings

## Recommendations

## The question

A computed casilla that reaches neither a formula nor the export record is a dead
end. If it carries a liability figure that should print on the return, the amount
never reaches AEAT -- an under-declaration. The M303 prorrata percentage recorded
alongside this is one such case, and it prompted the general sweep.

## The result

Every computed casilla in the registry that no formula consumes is accounted for:

| disposition | count |
|---|---|
| addressed by a fixed-width export record | **140** |
| revision declares no fixed-width layout at all | 41 |
| declares an `export_exemption_reason` | 22 |
| `internal_only` | 14 |
| **unaccounted** | **0** |

There is no silent dead end.

## The trap, which is the part worth keeping

A first pass measured export reachability with `casilla.export_refs` and reported
**237 undeclared dead ends**, 233 of them modelo 100. That number was wrong, and
the production code says why in its own refusal message:

> this scan is casilla-keyed and sees neither a BINDING-kind export field (so a
> value the export really does write at a declared offset looks identical here to
> one AEAT never prints) nor a value injected by application code through
> `bound_inputs_by_casilla_id`

**`export_refs` is not the export signal.** A casilla can be written at a declared
offset through a binding-kind field while carrying no `export_refs` of its own.
The registry answers the real question with
`derive_export_layouts_from_bindings` plus `fixed_width_record_casilla_ids`,
wrapped as `_fixed_width_addressed_casillas`. Re-measured through that fold, 140
of the supposed dead ends are addressed by a record and the residue falls to zero.

Anyone sweeping export coverage from casilla fields alone will reproduce the same
237-row false positive.

## The existing validator already adjudicates this

`_validate_export_exemption.py` requires a manifest casilla that would be caught by
the fichero-BOE completeness gate to declare either `internal_only` or an
`export_exemption_reason`, and refuses `feeds_addressed_casilla` when no chain
actually reaches an addressed box. Its message enumerates the ways a casilla-keyed
scan can be fooled, including the one this sweep fell into.

The axis is therefore not merely clean but *already guarded*, and no new gate is
warranted. Recording the measurement and the trap is the whole value here.

## Consistency with the prorrata finding

The six M303 prorrata rows fall in the `export_exemption_reason` bucket
(`record_block_not_modelled`), which is what the companion audit reported: dormant
and declared, not dormant and hidden. Re-measuring with the correct fold does not
move them.

No production code, registry data or test was changed by this audit.
