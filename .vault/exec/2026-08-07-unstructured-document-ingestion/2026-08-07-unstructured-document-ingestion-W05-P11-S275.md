---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:27bcf5804d645392a71865af3d0be1d9510e7a33ead91aa68294219801ae2276'
step_id: 'S275'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Route the audit payload transport through the shared derivation

## Scope

- `src/cadrumo/application/ledger/_llm_classification.py`

## Description

This is a LANDING-VERIFICATION record, not a claim of authorship. Like the sibling record in this batch, the scaffold committed for this row on 2026-08-08 carried every body section EMPTY, so the row had a matching record that recorded nothing. This fills it from HEAD.

- Re-read the row premise against HEAD and find the hand-rolled split already gone. `_transport_from_provenance` delegates to the shared `provenance_stamp_transport` derivation rather than splitting the stamp itself.
- Confirm the glued-together failure the row names is what the site now documents: a bare colon split returned the transport and the reader glued together, because the stamp second segment is itself a transport-and-reader pair. That is the exact shape the row predicted would appear once a consented off-host read landed, and it is now handled by the one derivation rather than by each caller own parsing.
- Confirm the malformed-stamp fallback is deliberate and not a silent default: an unreadable stamp echoes the whole stamp rather than being labelled with any transport, because a stamp that cannot be read is not evidence of a local read. Labelling it would assert a transport nobody established.
- Confirm the bound on the fallback: the echoed stamp is shortened to fit one bucket-event payload value, so the malformed case cannot overflow the audit record it is written into.
- Confirm one canonical home rather than two. The CLI surface reads the same derivation, so the operator-facing label and the audit payload cannot disagree about which transport read a document.

## Outcome

The audit payload transport axis is derived in one place. A later reader asking which transport actually read a given document gets the same answer from the audit record and from the CLI, and that answer degrades to an explicit unreadable rather than to a plausible local.

**What this excludes.** The row asked for the derivation to be routed through the shared function AND for a red-green proof over an off-host stamp. The routing is delivered. The off-host stamp it is proven against is a CONSTRUCTED one in the singularity suite, not one produced by a real consented cloud read, because no consented read path is live at HEAD: the consent gate is this wave own subject and the measured lane owns every model-bearing figure. So the proof establishes that the derivation distinguishes a local stamp from a cloud one, and does NOT establish that a real off-host read stamps what this code expects. That second claim waits on a consented read actually landing and must not be read into this record.

## Verification

Read directly from HEAD `ac219c97e8`:

    return provenance_stamp_transport(provenance) or provenance
                                        application/ledger/_llm_classification.py:183
    docstring naming the glued transport-and-reader shape
                                        application/ledger/_llm_classification.py:151-183
    _bounded_transport_label            application/ledger/_llm_classification.py:189
    canonical derivation                core/_provenance_stamp.py:107
    same derivation on the CLI surface  entrypoints/cli/_ledger_llm_cli.py:163

Implementing commit, by another lane:

    6900455af7  2026-08-08 13:09  feat(cadrumo): land the in-flight source work

a sweeper subject naming no Step, which is why this row is closed on the measurement rather than on the commit message.

Shipped coverage found beside it, not authored here:

    src/cadrumo/llm/tests/test_provenance_stamp_singularity.py

asserting a local stamp and a cloud stamp derive different transports, which is the discriminating half rather than a shape check.

Gate run requested from the single test-run authority rather than executed here.

## Notes

Both empty scaffolds in this batch were committed by sweeper commits whose subjects name no Step. A sweeper cannot tell an empty record from a written one, so the scaffold-then-fill-later pattern is load-bearing on the author returning, and twice this week the author did not.
