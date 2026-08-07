---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:227a8abc3496cf913bfd724a0c2ea07a1fb16d36b0a5a082e78af0e2daa22423'
step_id: 'S20'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S20

## Outcome

**Not reproduced in-tree, and not fixed.** Recorded as still open in substance rather than closed, because the run that would settle it needs an artefact this pass did not have.

## What was measured

Driving the real console entry point in-process:

    sys.argv = ["aeat", "--help"]; main()
    -> SystemExit 0, 2627 characters of help, no database refusal, clean stderr

So the in-tree help path does not construct `Settings` far enough to reach the former-product database refusal. The defect as stated — help needing database access and leaking a traceback — does not occur here.

## Why that is not the same as fixed

The Step names the **installed-console** help path. An installed wheel's console script is a different entry: it runs against the packaged tree with its own resolved paths and settings root, which is the specific condition under which the refusal was seen. Reproducing it requires acquiring the built cohort, which is `W05.P07.S32`'s surface and the `open-work-consolidation` plan's operator-gated publication work.

Declaring it fixed on an in-tree green would be the false-negative this campaign keeps finding: an absence of the failure under conditions that differ from the ones that produced it.

## Disposition

Left unchecked. The two halves of the Step's requirement are separable and only the first is settled:

- Help must never need database access — the in-tree path already satisfies this.
- The refusal must route through the translated error boundary instead of leaking a traceback — untested here, and the general mechanism for it landed for a neighbouring case under `W05.P07.S23`.

Whoever holds an installed cohort can settle this in one run.
