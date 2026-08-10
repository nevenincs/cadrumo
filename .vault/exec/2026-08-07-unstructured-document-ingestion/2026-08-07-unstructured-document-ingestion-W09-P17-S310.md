---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:a6d0386d0e4eacfbb4ceb7c91ac4638d1a599eadbf0a148d77475e05fdec2a05'
step_id: 'S310'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Route the ledger evidence batch streamed progress line through the shared CLI redaction funnel, so text mode cannot emit a document name the same command's envelope arms redact

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Route the streamed progress line through the renderer the closing envelope already uses for its text arm, rather than hand-calling the redaction primitive.
- Consult the same reveal-identifiers resolver as the envelope, so the two channels cannot disagree in either direction.
- Keep the stream a progress channel rather than promoting it to a second envelope: no schema spine, no notices, no sandbox banner.
- Promote the new primitive to the module facade, since a second caller in another package already needs it.
- Land in a contended file through the index rather than the working tree, and reconcile the working copy afterwards.

## Outcome

A long-running batch reported per-item progress straight to standard output while the same command's closing envelope redacted both of its arms. The progress channel was therefore the one operator-facing success surface reaching the terminal unfiltered, and it carried document source names — for a directory source, the full local path — plus any resolved action binding value.

**The fix routes the stream through the same renderer as the envelope's text arm**, so both channels apply one redaction pass and consult one reveal resolver. That direction matters twice over: an operator cannot be shown a raw value the envelope would have masked, and cannot be shown a masked one they explicitly opted to reveal. A hand-called primitive would have satisfied the first and silently broken the second.

**The comment above the defect is the best evidence for how it survived.** It reasons carefully about the single-document contract and about refusing a second progress channel, and not one sentence concerns redaction. A considered decision that examined one axis and never saw the other is far harder to find than carelessness, because the visible evidence of thought argues for the code.

## Verification

Behavioural, run against the landed helper rather than against the intention:

    path carrying a national identifier      masked
    filename carrying an account number      masked
    ordinary invoice filename                unchanged

**The third line is the control and it is the half that is usually omitted.** A change that masked everything would also have passed a leak test, so the benign case staying untouched is what distinguishes a fix from a blunt instrument.

No gate run is claimed. This confirmation is a direct call against the primitive, not a suite result, and the single test-run authority had not run anything against the change at the time this record was written.

## Notes

**The commit message overstates what the funnel does, and the error is the coordinator's.** It describes the leaked material as full local paths and calls them exactly what the funnel exists to mask. Measured, the funnel does not mask filesystem paths at all; it masks embedded tax identities and opaque record identifiers, and the surrounding path survives. The leak is real and the fix is correct, but the stated rationale claims a protection that does not exist, in the direction that makes the finding sound worse. A separate row corrects it, because a commit message outlives the conversation that produced it.

**The worker that landed this died to a session limit immediately after committing**, so no report survived it and nothing it claimed was ever received. Everything above was verified independently afterwards, from the commit and from the running code.

**The stale-working-copy hazard was checked rather than assumed in either direction.** Landing through the index never touches the working tree, so the copy should have read as a revert of the fix. It did not, because the reconciliation completed before the session ended. That was confirmed by reading the line out of both the working file and the committed object, not by trusting a quiet diff — a diff showing nothing at a site looks identical whether the site is correct or the instrument is pointed at the wrong place.

**The property this fix restores was already gated, and the gate was red and unrun for the defect's entire lifetime.** That is recorded against the sibling row, which found it.
