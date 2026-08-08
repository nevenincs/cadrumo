---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c6b9f326bd9b7054457d28ead6b28e8aa68d3a42935c40fb0388120979ded4ba'
step_id: 'S53'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Route every degradation refusal through a typed remediation naming the provision verb, never auto-falling back to the cloud route, gated by a test proving a local outage cannot reach a cloud dispatch without a consent token

## Scope

- `src/cadrumo/llm`

## Description

- Attach the provisioning remediation to an on-host degradation at the dispatch point, naming the verify verb first and the pull verb second, and naming no off-host alternative.
- Preserve the failure's own type and message, and leave any nearer layer's more specific suggestion in place.
- Add the behavioural and structural gates proving a local outage cannot become a cloud dispatch.

## Outcome

A local outage now reaches the operator with the verb that resolves it. The remediation leads with verify because this layer cannot tell an absent model from a stopped runtime from a slow load, and verify reports which of the three it is, while pull would be wrong advice in two of the three cases and would start a multi-gigabyte download in one.

The remediation names no cloud route, though the governing decision permits it. This CLI's operator is an agent that follows the next step it is given, so a mention would read as the offered action and would turn an outage into an off-host read of a taxpayer document that nobody chose. The consent gate would still refuse an evidence-marked request, but a refusal is the wrong last line of defence for a suggestion that should not have been written, and an unmarked request never meets that gate at all.

The remediation is attached rather than wrapped. The failure's type is the transport's honest answer and callers dispatch on it; replacing it to add a string would trade a true classification for a presentational one.

## Verification

uv run --no-sync pytest src/cadrumo/llm/tests/test_no_cloud_fallback_on_degradation.py -m unit -p no:randomly -q
    7 passed in 32.20s

The behavioural cases run a real local outage against a port bound and released so the refusal is deterministic, with the cloud route fully usable: a key present and the vendor endpoint pointed at a loopback recorder. They assert on what the cloud received, which is nothing, because asserting on the raised exception alone cannot distinguish an absent fallback from a fallback that also failed. The reach-around case covers an unmarked request, the path where a fallback would run with no consent gate in front of it at all. A positive control pins the same endpoint deliberately and observes the consent refusal, so the empty recorder is not merely a broken route.

The two structural detectors carry their own green control: the same functions run over a module written to contain a planted fallback and a planted reroute, and find both.

Proven by mutation. Installing a real cloud fallback turned three cases red, including both recorder assertions; removing the remediation turned exactly one red.

## Notes

The anti-fallback gates are stated as properties over every failure handler in the package rather than as a count of dispatch sites, so a recovery path reaching for a second provider reds them even in a module that does not exist yet.
