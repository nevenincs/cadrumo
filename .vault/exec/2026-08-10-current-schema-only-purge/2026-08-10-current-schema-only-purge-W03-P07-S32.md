---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:2cf4bf84a6343b0b6fbb8c5d481f72146677f5ed988e676d6a6ae5b3f4546b61'
step_id: 'S32'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Decide whether the carry gate should admit an operator-manual observation

## Scope

- Read-only. No production file changed.

## Description

- Read the gate's load key rather than its filter.
- Establish how many observation slots exist per modelo and period.
- Test whether a read-side filter could protect anything the strict validator does not.
- Follow the exposure to the end that owns it.

## Outcome

Closed on measurement. No source-kind filter was built, and one must not be.

The question was aimed at the wrong end. Observations are keyed naturally by
modelo and filing period, so there is exactly ONE slot per period, and the
strict carry validator already refuses any provenance that is not official-AEAT
or app_filing. Since the laundering fix landed, an admitted operator-manual row
blocks rather than laundering. So filtering the read would change which refusal
fires, not whether the taxpayer is protected -- a change with an uncounted
population bought for no safety.

The exposure is at the WRITE. Because there is one slot, and because the
operator write path performs no read-before-write, no existing-row check and no
provenance precedence, a later operator-manual write to a period that already
holds official or app_filing evidence takes the slot. A read-side filter cannot
help there: by the time the gate reads, the row it would have preferred is no
longer under that key. That is rowed separately rather than folded in, because
its severity turns on a fact this pass did not establish.

## Notes

The row's disconfirming clause -- whether any legitimate flow depends on the
gate reading a non-official observation -- was never reached, and none was
found in passing. It is recorded as unreached rather than as answered, because
the question stopped being load-bearing once the exposure moved to the other
end, and an unreached clause quietly recorded as satisfied is how a row looks
more settled than it is.

This is the second row in this campaign whose framing survived measurement only
by moving: the first assumed a screen belonged at an envelope boundary and it
belonged at the call site, and this one assumed a filter belonged on a read and
the exposure was on the write. Both were rowed from the symptom rather than from
the mechanism.
