---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:41717a08c6a4ecc7553edadd7f63601d2681ff72c9c64bec6854a670c3165631'
step_id: 'S70'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the end-to-end waist gate: an exact-parse fixture travels ingest, transcription, extraction, grounding, confirm, Invoice and the Modelo 303 observation with per-hop field accounting and no model in CI, proven by mutation at each hop

## Scope

- `src/cadrumo/application/ledger/tests`

## Description

- Drive one bundled structured e-invoice through the real chain: ingest, routing, exact extraction, deterministic grounding, confirm, persisted invoice, and the Modelo 303 terminus.
- Account per hop rather than on the outcome: every assertion names its hop, so a lost field is attributed to the hop that lost it.
- Assert the two cross-hop transformations as transformations, naming both forms, rather than accepting whichever the code emits.
- Record two live cross-hop defects found by the accounting, as passing assertions pinning current behaviour.
- Mutation-prove each accounted hop from outside the repository.

## Outcome

Sixteen assertions across the chain, all passing, no model reached at any point. The fixture is an exact-parse record, so the route is deterministic by construction rather than by configuration; that is the routing control the decision record specifies, not a testing convenience.

### The accounting found two cross-hop defects

Neither is visible to any single-hop test, which is the whole argument for this gate.

**The recargo is counted twice.** Extraction writes the scalar tax amount as cuota plus recargo; the closure check reads that same field as cuota alone and adds the recargo again. The bundled document is arithmetically perfect at 100,00 base, 21,00 cuota, 5,20 recargo and 126,20 total, and it is reported inconsistent by exactly the recargo. Every recargo de equivalencia invoice therefore raises a spurious blocking finding at the confirm boundary, and that regime is common rather than exotic. Neither hop is wrong alone: the per-band figure is the printed cuota and the scalar is the total tax, and both readings are defensible until they meet. The gate pins the current behaviour, proves the document's own arithmetic does close, and proves the check falls silent once the two meanings are aligned, so the defect is attributed rather than merely observed. The fix belongs to the two modules that own the hops.

**Modelo 303 is not invoice-fed.** The Step names a hop from the confirmed invoice to the Modelo 303 observation. Measured against the registry, that hop does not exist: the revision declares twenty-three ledger-aggregation bindings and no invoice-source binding whatsoever. An invoice reaches 303 only as evidence attached to a ledger movement, and the ledger row is what declares. Rather than assert a hop that is not built, or stop silently at the invoice and let the gate read as complete, the terminus is asserted as that structural fact and keyed on the registry, so the day 303 grows an invoice-source binding this class fails and forces the accounting to be extended.

### Two transformations, asserted as transformations

The document states the tax identifier in its VAT form with a country prefix and the catalogue stores the bare national form; and the draft calls the base one name while the persisted invoice calls it another. Both are renames or normalisations rather than losses, and both are asserted with both forms named. An assertion written against only the output form would pass through a silent change of stored form, and the identifier is what the tax authority reconciles a counterparty declaration against.

### The transcription hop, honestly

The Step's hop list places transcription between ingest and extraction. On the exact-parse route that hop does not exist, and its absence is the control rather than a gap: a document that never becomes text for a model cannot be prompt-injected. The gate asserts the bypass itself, which is a stronger statement than a fabricated transcription assertion would have been.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_waist_end_to_end_accounting.py -n 0
    17 passed in 16.91s

Collected 17, zero deselected. Sixteen at first landing; seventeen once the ingest hop was rebuilt on the real path. Ruff clean after formatting; basedpyright reports zero errors, warnings and notes.

Mutation at each hop, every one driven from a throwaway plugin on the interpreter path outside the repository, with nothing inside the tree edited.

Breaking the shape probe reds two, both routing assertions. Dropping the identifier at extraction reds five: the extraction census and, downstream, confirm, storage and the terminus, which shows the chain is genuinely connected rather than each hop independently re-deriving the value. Silencing the closure check reds three. Dropping the identifier at the confirm projection reds four. Widening the invoice-source set reds exactly one, the terminus assertion.

Three of those mutations initially passed and were NOT reported as unaccounted hops. Each had targeted a private module while the gate binds the name through a package facade, so the patch never reached the site under test; retargeted at the facade, all three bit. A mutation that fails to mutate is a harness fault and says nothing about the gate, and treating it as a result would have understated the gate in one direction or overstated it in the other.

The ingest hop was initially not claimed as mutation-proven: its assertion ran over the constructor's own contract with the test's own helper performing the ingest, so no production seam existed for a mutation to break. That has since been closed in a follow-up row. The hop now stores the fixture through the real attachment store into a real encrypted bucket and resolves it back through the production resolver, and a mutation on that hop reds exactly the byte-identity assertion.

Finding the sound mutation took three attempts, and the two rejected ones are worth recording because both would have passed for the wrong reason. Truncating the store read reds, but at the content-address guard during construction, before any assertion runs. Moving the manifest digest with the bytes to defeat that guard also reds, because the store validates the manifest against the real stored blob on read as well as on write. Both would have been reported as proof while establishing only that the product's own integrity check works. The sound mutation is on the hop under test, the resolver projecting bytes other than the ones it read, and it is the only one of the three whose red is attributable to this gate.

The general form: a mutation that reds tells you something failed, not that your gate is what failed it. It is the mirror of the fully-green tell, where an ineffective patch is indistinguishable from a well-covered site, and both are invisible from the exit code alone.

## Notes

Two production defects were found and neither was repaired here, because both live in modules held by other lanes: the recargo double-count spans the extraction and closure modules, and the Modelo 303 terminus is a registry question. Both are reported for routing rather than fixed in place.

The census literals were wrong on the first draft, taken from a neighbouring test that asserted a different field. They were corrected by measuring the fixture rather than by adjusting until the suite went green, which is what surfaced the recargo disagreement in the first place.
