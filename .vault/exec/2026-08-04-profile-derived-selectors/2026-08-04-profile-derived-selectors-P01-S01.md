---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:cf5c830de182e028c88a9189155a3635a1b943958151bcf4bafe2b95e52011a2'
step_id: 'S01'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-derived-selectors with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-08-04-profile-derived-selectors-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Prove with a real failing test that an operator-stored value at a derived aggregate path suppresses the Art. 58 computation on the live calculate path, and record the red run before flipping it and ## Scope

- `src/cadrumo/application/modelo/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove with a real failing test that an operator-stored value at a derived aggregate path suppresses the Art. 58 computation on the live calculate path, and record the red run before flipping it

## Scope

- `src/cadrumo/application/modelo/tests/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

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

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
