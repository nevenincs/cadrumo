---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3bb23f395f38056acd4880dca14b8800bfe6d2e64702ef93373b5bb29199ccf3'
step_id: 'S42'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add `--off-host-provider` and `--acknowledge-off-host` to the extract verb, both absent meaning LOCAL with no token and behaviour unchanged.
- Mint through the sole constructor, passing the single production reading of the per-profile eligibility bar; surface `LLMConsentError` as a localised refusal.
- Refuse each incomplete way of asking: either flag alone, a provider naming the on-host default, an attachment-only read, and a record carrying no content address.
- Widen the application entry point and thread the pair to BOTH model-bearing stages, constructing the extractors directly and leaving the pinned wrappers untouched.
- Record the authorisation once per read on the extract payload and enrol the pair in the projection gate's declared reference set.
- Correct `_state().settings` on the two sibling consent verbs, which raises `AttributeError`.
- Give the on-host re-derivation reader the transcription rather than its text, and type it as the protocol.
- Add the consent verb suite, whose positive control genuinely transmits.

## Outcome

The consent lifecycle closes. The gate, its ledger, the eligibility bar and the
withdrawal verb had all shipped, but nothing could mint a token, so in
production every off-host evidence read refused. That is the correct default and
an incomplete lifecycle; an operator can now authorise one read.

Nothing about the posture moved. Both flags are per-invocation with no stored
counterpart -- no config key, no profile field -- because a stored
acknowledgement is the standing enablement the default-off posture exists to
prevent. The refusal still lives below the wrapper: the convenience functions
keep their LOCAL pin untouched and the consented path constructs the extractors
directly, so the reach-around gate keeps its target.

The consent reaches stage ONE as well as stage two. On a scan-only document the
pixels are the evidence, so covering only the semantic stage would take an
acknowledgement and then leave the read on-host -- a consent prompt that changes
nothing, which is worse than not asking.

Two live defects were found while wiring it, both invisible because this surface
carries no tests. `_state().settings` raises `AttributeError`: `WorkflowState`
has no such attribute, so the consent survey and the withdrawal verb both crash
outright. And the re-derivation reader still called the semantic stage with the
signature that changed when stage two began taking the transcription artefact,
which would have raised `TypeError` in an operator's hands. The reader's return
was annotated `object`, which is what let the checker see nothing.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_evidence_extract_consent_verb.py -n0 -p no:cacheprovider -q -m integration
    7 passed in 45.48s

Run against a clean `git archive HEAD` export rather than the working tree,
because the tree carries several peers' in-flight work and could not give a
reading about what landed.

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -n0 -p no:cacheprovider -q -m integration
    515 passed, 1 warning in 37.13s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/llm/tests src/cadrumo/entrypoints/cli/tests -n0 -p no:cacheprovider -q -m unit
    1 failed, 1948 passed, 2967 deselected, 1 warning in 466.20s

    uv run --no-sync pytest src/cadrumo/tests/test_parity.py -n0 -p no:cacheprovider -q -m unit
    33 passed in 161.75s

The single failure is the CLI module-size budget naming `_app_live.py` at 1501
lines against 1445. That file is clean in the working tree, so it is over budget
at HEAD and reproduces without any change here.

The positive control is the load-bearing case. Every refusal assertion in the
suite passes equally against a path that refuses always -- including one that
can no longer dispatch at all -- so the control mints a real token through the
sole constructor and drives a real request into a real loopback endpoint,
asserting both that the body arrived and that the reply reached the draft. Its
negative twin differs in exactly one variable, the token, and asserts the queue
stayed empty.

## Notes

The control had to move to the integration lane, and the reason is a production
guard rather than a preference: a consented dispatch writes a consent-ledger
entry, and the ledger refuses outright when no profile bucket session is open,
because a transmission leaving no audit trail must not happen. Proving the path
therefore needs a real bucket runtime.

The content address is read through the exported service rather than the
confirm path's private helper, because promoting that helper needs a facade edit
and the facade was contended throughout. The two resolutions agree today -- both
read the evidence record's own `source_sha256` -- but they are separate call
sites, and the durable fix is to promote the helper once the facade is free.

A lost update was caught and repaired here. An edit built from a working copy
that had been read before a peer wrote to it silently reverted their
deterministic-findings call on the structured path; the unfiltered diff showed
it as a removed line, and the file was rebuilt from HEAD bytes with only the
intended hunks re-applied. A later inspection showed HEAD had since become
internally consistent without one of those hunks, so that hunk was withdrawn
rather than landed as a gratuitous loosening.

Seven operator strings were set in all four catalogues through the locale CLI
one leaf at a time, never through `scaffold`, which is tree-wide and reads the
registry and would have baked several peers' uncommitted TOMLs into every
catalogue. Values beginning with a flag name need `--` to terminate option
parsing, or the CLI reads them as unknown options.

The Hungarian catalogue took twenty-two attempts across four runs to accept two
of them: an atomic rename onto `hu.yml` fails with a Windows access-denied error
while a peer holds the file open. Both eventually landed. Two of those keys had
been left as the forbidden self-referencing placeholder by an earlier scaffold,
and a presence check would have hidden it -- the coverage count read 7/7 while
the values were still the key strings, so the values themselves had to be
inspected.
