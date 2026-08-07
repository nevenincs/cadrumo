---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9dd5502f01575cce24bd4477d4550b80063fe1be376467bc0e741f21a13e25fe'
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
    16 passed in 14.92s

Collected 16, zero deselected. Ruff clean after formatting; basedpyright reports zero errors, warnings and notes.

Mutation at each hop, every one driven from a throwaway plugin on the interpreter path outside the repository, with nothing inside the tree edited.

Breaking the shape probe reds two, both routing assertions. Dropping the identifier at extraction reds five: the extraction census and, downstream, confirm, storage and the terminus, which shows the chain is genuinely connected rather than each hop independently re-deriving the value. Silencing the closure check reds three. Dropping the identifier at the confirm projection reds four. Widening the invoice-source set reds exactly one, the terminus assertion.

Three of those mutations initially passed and were NOT reported as unaccounted hops. Each had targeted a private module while the gate binds the name through a package facade, so the patch never reached the site under test; retargeted at the facade, all three bit. A mutation that fails to mutate is a harness fault and says nothing about the gate, and treating it as a result would have understated the gate in one direction or overstated it in the other.

The ingest hop is deliberately NOT claimed as mutation-proven. Its assertion is over the constructor's own contract, and the helper that performs the ingest is the test's own, so no production seam exists there for a mutation to break. As written the assertion is close to tautological. The real ingest path resolves evidence bytes out of the encrypted attachment store, and driving that path is what would make the hop genuinely accountable; it is recorded here as the one hop this gate does not yet hold.

## Notes

Two production defects were found and neither was repaired here, because both live in modules held by other lanes: the recargo double-count spans the extraction and closure modules, and the Modelo 303 terminus is a registry question. Both are reported for routing rather than fixed in place.

The census literals were wrong on the first draft, taken from a neighbouring test that asserted a different field. They were corrected by measuring the fixture rather than by adjusting until the suite went green, which is what surfaced the recargo disagreement in the first place.
