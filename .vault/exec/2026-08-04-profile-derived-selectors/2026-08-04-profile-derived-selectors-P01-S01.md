---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:c81efd3a396b2ba7c6a11a147755a7f82d417678433f92e0eb6fdb95c941bdb7'
step_id: 'S01'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Prove with a real failing test that an operator-stored value at a derived aggregate path suppresses the Art. 58 computation on the live calculate path, and record the red run before flipping it

## Scope

- `src/cadrumo/application/modelo/tests/`

## Description

## Outcome

The override is DEMONSTRATED, not refuted. The campaign premise holds and the
remaining Steps proceed.

A throwaway reveal probe, since deleted, ran the same production entry point twice over
the same two eligible descendants and reported `computed=5100.00` against
`overridden_with_777.11=777.11`. The `5100.00` is the real Art. 58 aggregate for that
pair under the 2024 tranches. With a sentinel stored at
`renta_family.descendientes_minimos_aggregate_2024`, casilla `0513` returns the sentinel
verbatim and the Art. 58 computation never runs. No refusal, no notice, no diagnostic on
any surface.

The reveal used a different sentinel from the one the committed test asserts, so the
casilla is shown to track whatever is stored rather than coinciding with a single chosen
constant. That is the discrimination check the Step required.

The write door accepts the path because the schema declares it an ordinary optional
decimal field. Nothing judges path legitimacy, which is precisely the gap the ADR closes.

Two tests landed in one file, both green at HEAD and docstringed as pinning a defect that
later Steps invert: one proving the write door accepts a value at the derived path and
reads it back through the real repository, one proving the stored value suppresses the
computation. Real encrypted storage root, real registration and write doors, real
calculate entry point, every repository left to default so the active bucket resolves as
in production. Nothing monkeypatched, which also avoids the tuple-built resolver mesh
that would have made patching inert.

The test is non-tautological. No Art. 58 formula is recomputed and no euro figure is
hand-derived. It asserts the computed value is positive and differs from the sentinel
BEFORE asserting the override, so it cannot pass against an already-zero computation nor
by coincidence.

Coordinator verification of the executor's own self-flagged risk: the caller-zero binding
set was read directly and contains exactly three unrelated profile bindings, with both
mínimo bindings excluded and a comment stating why. Caller-supplying either would have
decided the question the probe asks. The set is not widened and the probe is valid.

One escalation from the executor was NOT accepted. It reported that eight shipped test
files seed the derived path and inferred each would need its expected figures re-derived
once the computation stops being suppressed. Measurement contradicts the inference: those
profiles declare zero descendants and carry no per-descendant rows, so there is nothing to
compute a non-zero from and the injector re-derives zero from genuine absence. The seeds
are redundant rather than load-bearing, and the later conversion Step remains a deletion.
The executor's underlying observation still stands and is recorded: the codebase was
already relying on this channel, which is evidence for the ADR rather than against it.

## Notes
