---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:144efd271990cf1bcc430f6c82cff0d54ace1d734e9bfac505b427b076447007'
step_id: 'S08'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace release-pipeline-full-automation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Add the fail-closed precondition refusing an orchestration when a claimed host-extension channel has no operator-minted claude evidence release, naming the emit_real_client_evidence capture command in the refusal, and never attempting to produce those four rows because the emit honesty guard refuses SDK-driven runs by design and defeating it would make the evidence a lie about what was installed, gate: uv run --no-sync pytest dev/packaging/tests -q -k precondition passes covering the unclaimed-channel pass, the claimed-and-supplied pass, and the claimed-and-absent refusal carrying the capture command in its message and ## Scope

- `dev/packaging/publication_inputs.py`
- `dev/packaging/tests/test_publication_inputs.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the fail-closed precondition refusing an orchestration when a claimed host-extension channel has no operator-minted claude evidence release, naming the emit_real_client_evidence capture command in the refusal, and never attempting to produce those four rows because the emit honesty guard refuses SDK-driven runs by design and defeating it would make the evidence a lie about what was installed, gate: uv run --no-sync pytest dev/packaging/tests -q -k precondition passes covering the unclaimed-channel pass, the claimed-and-supplied pass, and the claimed-and-absent refusal carrying the capture command in its message

## Scope

- `dev/packaging/publication_inputs.py`
- `dev/packaging/tests/test_publication_inputs.py`

## Description

Added `host_extension_precondition_refusal(descriptor, *, claude_evidence_release)` to `dev/packaging/publication_inputs.py`: refuses when a claimed host-extension channel (`claude-plugin`, `mcpb`) has no operator-minted claude evidence release, naming the exact `EMIT_REAL_CLIENT_EVIDENCE_COMMAND` (`uv run --no-sync python -m dev.packaging.emit_real_client_evidence`) capture verb in the refusal text. This is a standalone orchestration-ENTRY precondition, kept separate from the publish-dispatch `refusals()` demand machinery: it is meant to run before the bump or any other stage so the whole chain stops before a version is burned. Never attempts to produce the four claude-* rows itself — the honesty guard in `distribution_evidence_emit.py` refuses SDK-driven runs by design, and defeating it would make the evidence a lie about what was installed.

## Outcome

Gate green: `uv run --no-sync pytest dev/packaging/tests -q -k precondition` — 6 passed. Coverage: unclaimed host-extension channel passes regardless of the evidence-release value (including whitespace-only); claimed-and-supplied passes; claimed-and-absent refuses naming both the capture command and the claimed channel id; whitespace-only release treated as absent; both host-extension channels claimed together are both named in one refusal; a non-host-extension claim (scoop) never trips this precondition. Full-file selector `-k publication_inputs` also green: 23 passed.

## Notes

No incidents.
