---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:42144cbbbbdb7a3e4f9fcaac9f7e4273a5c6a2701d1e96707c6650ab57810148'
step_id: 'S09'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Emit a Notice through the shared envelope spine naming the unreached-evidence reason when an enrollment call finds an artefact but saves nothing

## Scope

- `src/cadrumo/application/live/_filed_observation_persistence.py (persist_filed_justificante_metadata and enroll_filed_justificante_evidence)`

## Description

The reasons had to reach an operator through the typed `Notice` channel, never a
bespoke advisory field on a result payload.

## Outcome

Added a projection onto `cadrumo.core.json_contract.Notice` at `WARNING`
severity under the code `live.filed.justificante_unreached`, with the modelo,
filing year, period, expediente id and reason in `context`. Both enrollment entry
points accumulate them: the evidence-enrollment function returns them on its
existing result, and the metadata-persistence function now returns a
`FiledJustificanteMetadataResult` carrying its CSVs alongside its notices. The new
public types and the notice code are promoted through the `application/live`
facade as a precondition of any consumer.

## Verification

`test_each_unreached_justificante_outcome_reports_its_own_reason` asserts the
severity, code, context and reason per case;
`test_an_enrollment_that_saves_evidence_raises_no_unreached_notice` asserts the
channel stays empty on the success path, so a change emitting the notice
unconditionally cannot pass. Gate proven to bite under `-n0` by collapsing the
reason to a single member from outside the repo.

## Notes

The notices stop at the application boundary. Forwarding them onto the CLI
envelope requires changing the filed-capture return shape, which a concurrent
campaign is actively extending with its own advisories, and putting `Notice`
objects inside the report payload is what the CLI contract forbids. That hop is
NOT landed here and `P02.S10` stays open for it.
